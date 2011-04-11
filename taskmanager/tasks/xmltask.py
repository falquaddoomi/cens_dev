import sys, os.path
import json, re
from lxml import etree
from parsedatetime import parsedatetime

from django.template.loader import Template, Context

from base import BaseTask, TaskCompleteException
from taskmanager.models import SessionMessage

class BaseXmlTask(BaseTask):
    def __init__(self, app, patient, session, args=None):
        super(BaseXmlTask, self).__init__(app, patient, session, args)

        # we need a script file from the arguments,
        # so ensure it's there before we begin
        if "script" not in args:
            raise Exception("attempted to instantiate BaseXmlTask without 'script' in the arguments collection")

        # create a little queue that stores action items for the current level of scope.
        # each action item consists of a condition for its triggering and the node to
        # expand when it's triggered.
        # we'll be using this in handle() and timeout() to dispatch messages to the
        # concerned node
        self.conditions = []

    def start(self):
        print "Beginning execution of %s!" % (self.args['script'])
        
        # read the first-level element (ostensibly interaction)
        self.tree = etree.parse(os.path.join(os.path.dirname(__file__), "scripts", self.args['script']))
        interaction = self.tree.getroot()
        # grab some top-level params which apply to the entire task
        self.prefixes = [interaction.get("prefix")]
        # and start executing its children
        self._exec_children(interaction)
        
    def handle(self, message):
        # if there aren't any pending conditions, this is a good time to throw a TaskCompleteException
        if not self.conditions:
            raise TaskCompleteException()

        # since there are some conditions, determine if any apply
        for condition in self.conditions:
            # determine if the condition applies to the current message
            if condition.satisfied(msg=message):
                # log it!
                SessionMessage(session=self.session, message=message.text, outgoing=False).save()
                # and expand the node associated with this condition
                self._exec_children(foundCond.node, foundCond.context)
                return True

        # nothing matched; let's tell our caller that
        return False

    def timeout(self):
        pass

    def send(self, message):
        # little helper for sending and logging messages
        SessionMessage(session=self.session, message=message, outgoing=True).save()
        self.app.send(self.patient.get_address(), message, identityType=self.session.mode)

    # ----------------------------------------------------
    # --- dealing with node behaviors below
    # --- this is big and complicated at the moment, but
    # --- it'd be nice to trim it down or make better sense
    # --- of it later.
    # ----------------------------------------------------

    def _exec_children(self, top, context=None):
        print "--> Executing children of %s..." % (top)
        
        # first off, clear all pre-existing conditions
        self.conditions = []
        
        # construct a default context for this evaluation
        # and add any parent context info to the dict
        default_context = Context({'patient': self.patient, 'args': self.args})
        if context: default_context.update(context)

        # execute all top-level elements
        for node in top:
            # depending on the type of the thing, perform some action
            if node.tag == "message":
                # strip node text and collapse whitespace
                text = " ".join(node.text.strip().split())
                # apply django's template engine to the text and send the resulting message
                self.send(Template(text).render(default_context))
            elif node.tag == "response":
                # add the condition of the response to the action queue
                print "--> Adding a condition in %s" % (top)
                # angle brackets are mapped to {@ and @} to get around xml's restrictions
                pattern = node.attrib["pattern"].replace("{@","<").replace("@}",">")
                self.conditions.append(RegexCondition(node, pattern))
            elif node.tag == "link":
                # immediately expand the link with the id specified by target
                # but first we have to find it
                target = self.tree.xpath("//*[@id='" + node.attrib["target"] + "']")

                if len(target) <= 0:
                    raise Exception("Target node for %s couldn't be found!" % ("//*[@id='" + node.attrib["target"] + "']"))

                # take the first element that matches the given id
                # (there should only be one, but we're not validating for that)
                target = target[0]

                # check for some obvious problem conditions
                if target == top or target == node:
                    raise Exception("Aborting, link would lead to infinite recursion")                    

                print "--> Following link from %s to %s" % (top, target)

                # if everything's good, jump immediately to that context
                self._exec_children(target)
                return # we have to break here, too...

        # if there's nothing left on the condition queue then, once again, we're done
        if not self.conditions:
            print "--> Dying in %s on account of having no conditions left" % (top)
            raise TaskCompleteException()


# ==============================================================
# === exception classes
# ==============================================================

class XMLFormatException(Exception):
    def __init__(self, message):
        super(XMLFormatException).__init__(message=message)


# ==============================================================
# === condition classes
# ==============================================================

class Condition(object):
    """
    Represents an abstract condition, which presents both a satisfied() method and a 'context' dict which
    contains the results of the condition being satisfied.
    """

    def __init__(self, node):
        self.node = node
        self.context = {}

    def satisfied(self, **kwargs):
        return False

class RegexCondition(Condition):
    def __init__(self, node, pattern):
        super(RegexCondition, self).__init__(node)
        self.context['pattern'] = pattern
        self.expr = re.compile(pattern)

    def satisfied(self, **kwargs):
        msg = kwargs['msg']
        result = self.expr.search(msg.text)
        if not result: return False

        # otherwise, it matched! stuff our context with useful data and return true
        self.context['message'] = msg.text
        self.context['match'] = result.groupdict()
        return True

class TimeoutCondition(Condition):
    def __init__(self, node, triggertime):
        super(TimeoutCondition, self).__init__(node)
        self.context['triggertime'] = triggertime
        self.triggertime = re.compile(self.context['pattern'])
