import sys, os.path
import json, re
from lxml import etree
from parsedatetime import parsedatetime
from datetime import datetime

from django.template.loader import Template, Context

from base import BaseTask, TaskCompleteException
from taskmanager.models import LogMessage, TaskTemplate, TaskInstance, Alert
from taskmanager.framework import utilities

class BaseXmlTask(BaseTask):
    def __init__(self, dispatch, instance):
        super(BaseXmlTask, self).__init__(dispatch, instance)

        # we need a script file from the arguments,
        # so ensure it's there before we begin
        if "script" not in self.params:
            raise Exception("attempted to instantiate BaseXmlTask without 'script' in the arguments collection")

        # create a little queue that stores action items for the current level of scope.
        # each action item consists of a condition for its triggering and the node to
        # expand when it's triggered.
        # we'll be using this in handle() and timeout() to dispatch messages to the
        # concerned node
        self.conditions = []

        # create a little dict for our context that we'll carry around
        # FIXME: figure out when this should be cleared
        self.context = {}

    def start(self):
        print "Beginning execution of %s!" % (self.params['script'])
        
        # read the first-level element (ostensibly interaction)
        self.tree = etree.parse(os.path.join(os.path.dirname(__file__), "scripts", self.params['script']))
        interaction = self.tree.getroot()
        # grab some top-level params which apply to the entire task (unless overridden by a composite tag)
        self.prefix = interaction.get("prefix")
        # and start executing its children
        self._exec_children(interaction)
        
    def handle(self, message):
        # if there aren't any pending conditions, this is a good time to throw a TaskCompleteException
        if not self.conditions:
            raise TaskCompleteException()

        # since there are some conditions, determine if any apply
        # only examine the conditions that have to do with messages
        for condition in [c for c in self.conditions if c.eventtype == "message"]:
            # determine if the condition applies to the current message
            if condition.satisfied(msg=message):
                # log it!
                LogMessage(instance=self.instance, message=message.text, outgoing=False).save()
                # and expand the node associated with this condition
                self._exec_children(condition.node, condition.context)
                return True

        # nothing matched; let's tell our caller that
        return False

    def timeout(self):
        print "Got a timeout, executing..."
        
        # if there aren't any pending conditions, this is a good time to throw a TaskCompleteException
        if not self.conditions:
            raise TaskCompleteException()

        # since there are some conditions, determine if any apply
        # only examine the conditions that have to do with time
        for condition in [c for c in self.conditions if c.eventtype == "time"]:
            # determine if the condition applies to the current situation
            if condition.satisfied():
                # expand the node associated with this condition
                self._exec_children(condition.node, condition.context)
                return True

        # nothing matched; let's tell our caller that
        return False

    def send(self, message, accepts_response=True):
        # little helper for sending messages
        self.dispatch.send(self.instance, message, accepts_response)

    def templatize(self, text, context):
        """
        Helper function that pushes the text through the django templating engine.
        Keep in mind that it does *not* escape text, which is good!
        """
        return Template("{% autoescape off %}" + text + "{% endautoescape %}").render(context)

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
        self.instance.timeout_date = None
        self.instance.save()
        
        # construct a default context for this evaluation
        # and add any parent context info to the dict
        if context: self.context.update(context)
        default_context = Context({'patient': self.instance.patient, 'params': self.params})
        default_context.update(self.context)

        # also copy the prefix attribute (if it exists) into our machine's registered prefix
        if 'prefix' in top.attrib:
            self.prefix = top.attrib['prefix']

        # pre-step: determine if there are any elements that require a response
        # that may be siblings to a <message> element. we need to know this
        # so we know whether to tell them to "type prefix before their response"
        siblings = [node.tag for node in top]
        accepts_response = ("response" in siblings or "link" in siblings)

        # execute all top-level elements
        for node in top:
            # depending on the type of the thing, perform some action
            if node.tag == "message":
                # if there's a condition supplied, evaluate it using the template language
                # only proceed if the string evaluates to a non-empty string.
                # if there's no condition, just send it!
                if (not "condition" in node.attrib) or (self.templatize(node.attrib['condition'], default_context).strip()):
                    # strip node text and collapse whitespace
                    text = " ".join(node.text.strip().split())
                    # apply django's template engine to the text and send the resulting message
                    self.send(self.templatize(text, default_context), accepts_response=accepts_response)
            elif node.tag == "response":
                if node.get('type',None) == "date_time":
                    # it's a parsedatetime condition rather than a regex one
                    self.conditions.append(ParseDateTimeCondition(node))
                else:
                    # it's a regex condition (FIXME: should be a 'regex' type)
                    # add the condition of the response to the action queue
                    print "--> Adding a regex condition in %s" % (top)
                    # angle brackets are mapped to {@ and @} to get around xml's restrictions
                    pattern = node.attrib["pattern"].replace("{@","<").replace("@}",">")
                    self.conditions.append(RegexCondition(node, pattern))
            elif node.tag == "timeout":
                # gather the duration and offset, if specified
                try:
                    duration = node.attrib['delay']
                    offset = node.get('offset', None) # optional; None if not present
                    triggerdate = utilities.parsedt(duration, offset)
                except KeyError as ex:
                    raise XMLFormatException("%s node expects attribute '%s'" % (node.tag, ex.args[0]))

                # FIXME: temporarily overriding the triggerdate to be 2 minutes
                # for the sake of the demo
                # triggerdate = utilities.parsedt("in 30 seconds")
        
                # add the condition of the response to the action queue
                print "--> Adding a timeout condition in %s" % (top)
                self.conditions.append(TimeoutCondition(node, triggerdate))

                # and register us as requiring a timeout
                # only replace the timeout if the new one is more recent than the existing one
                # this is just a nicety to the task writer, since only one timeout
                # will ever trigger...thus, the first one will erase all subsequent ones anyway
                self.instance.timeout_date = triggerdate
                self.instance.save()
            elif node.tag == "schedule":
                # gather the duration and offset, if specified
                try:
                    tasktemplatename = node.attrib['task']
                    date = self.templatize(node.attrib['date'], default_context)
                    offset = node.get('offset', None) # optional; None if not present
                    if offset is not None:
                        offset = self.templatize(offset, default_context)
                        schedule_date = utilities.parsedt(offset, utilities.parsedt(date))
                    else:
                        schedule_date = utilities.parsedt(date)
                except KeyError as ex:
                    raise XMLFormatException("%s node expects attribute '%s'" % (node.tag, ex.args[0]))

                # look up the task template that they specified...
                template = TaskTemplate.objects.get(name=tasktemplatename)
                # grab its default arguments to start out
                new_args = json.loads(template.arguments)
                # and collect any additional arguments (e.g. params) defined in children of this node in <param key="a">value</param> format
                for param in [n for n in node if n.tag == "param"]:
                    # process the values and insert them into the new_args, too
                    new_args[param.attrib['key']] = self.templatize(param.text, default_context)

                # this time we spawn another task rather than continuing execution here
                self.instance.spawn_task(
                    template.task,
                    schedule_date,
                    name=template.name,
                    update_params=new_args
                    )
            elif node.tag == "store":
                # gather the key and value
                try:
                    key = node.attrib['key']
                    value = node.attrib['value']
                except KeyError as ex:
                    raise XMLFormatException("%s node expects attribute '%s'" % (node.tag, ex.args[0]))

                value = self.templatize(value, default_context)

                print "--> Storing '%s' to key '%s'" % (value, key)

                # store these to the persistent params collection and save it
                p = json.loads(self.instance.params)
                p[key] = value
                self.instance.params = json.dumps(p)
                self.instance.save()
            elif node.tag == "alert":
                # gather the key and value
                try:
                    name = node.attrib['name']
                except KeyError as ex:
                    raise XMLFormatException("%s node expects attribute '%s'" % (node.tag, ex.args[0]))

                # collect any params defined in children of this node in <param key="a">value</param> format
                alert_args = {}
                for param in [n for n in node if n.tag == "param"]:
                    # process the values and insert them into alert_args
                    alert_args[param.attrib['key']] = self.templatize(param.text, default_context)
                
                alert_args['url'] = '/taskmanager/patients/%d/history/#session_%d' % (self.instance.patient.id, self.instance.id)
                # alert_args.update(default_context)
                Alert.objects.add_alert(name, arguments=alert_args, patient=self.instance.patient)
            elif node.tag == "abort":
                # remove all pending tasks belonging to the same process
                TaskInstance.objects.filter(process=self.instance.process, status="pending").delete()
                # and immediately conclude execution
                raise TaskCompleteException()
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

                # if everything's good, jump immediately to that node
                # we maintain the context to allow us to pass things that we detected in our present node
                self._exec_children(target, context)
                return # we have to break here, too...

        # if there's nothing left on the condition queue then, once again, we're done
        if not self.conditions:
            print "--> Dying in %s on account of having no conditions left" % (top)
            raise TaskCompleteException()

    # ===========================================
    # === definitions of tag types below
    # ===========================================

    # FAISAL: TBD

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

class ParseDateTimeCondition(Condition):
    def __init__(self, node):
        super(ParseDateTimeCondition, self).__init__(node)
        self.eventtype = "message"

    def satisfied(self, **kwargs):
        try:
            # see if we have the necessary values
            # if not, this check definitely doesn't apply
            msg = kwargs['msg']
        except KeyError:
            return False

        try:
            result = utilities.parsedt(msg.text, verify_complete=True)
        except ValueError:
            # it was not parseable as a datetime :(
            return False
        
        # it matched! stuff our context with useful data and return true
        self.context['message'] = msg.text
        self.context['parsed_datetime'] = result
        return True

class RegexCondition(Condition):
    def __init__(self, node, pattern):
        super(RegexCondition, self).__init__(node)
        self.context['pattern'] = pattern
        self.expr = re.compile(pattern, flags=re.IGNORECASE)
        self.eventtype = "message"

    def satisfied(self, **kwargs):
        try:
            # see if we have the necessary values
            # if not, this check definitely doesn't apply
            msg = kwargs['msg']
        except KeyError:
            return False

        result = self.expr.search(msg.text)
        if not result: return False
        
        # otherwise, it matched! stuff our context with useful data and return true
        self.context['message'] = msg.text
        self.context['match'] = result.groupdict()
        return True

class TimeoutCondition(Condition):
    def __init__(self, node, triggerdate):
        super(TimeoutCondition, self).__init__(node)
        self.triggerdate = triggerdate
        self.context['triggerdate'] = triggerdate
        self.eventtype = "time"

    def satisfied(self, **kwargs):
        return self.triggerdate <= datetime.now()
