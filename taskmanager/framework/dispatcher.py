"""
This module will contain the definition of the
dispatcher class, which maintains a list of currently
running tasks and their associated users. When a message
is received, this class will decide first which user
and then which task for that user the message is intended for,
and will invoke the handle() event on that task instance.
"""

import json, string, pickle
from django.db.models import Count

from collections import defaultdict

from rapidsms.log.mixin import LoggerMixin
from taskmanager.models import Patient, Task, Process, TaskInstance, LogMessage
from taskmanager.tasks.base import BaseTask, TaskCompleteException
from utilities import KeepRefs

class TaskDispatcher(KeepRefs, LoggerMixin):
    def __init__(self, app):
        # dict of active session machines, keyed by session id
        # the user provides two pieces of information that will help
        # us resolve which session machine should receive the message:
        # 1) the user's address, which is always present
        # 2) a unique prefix/format/etc. that may or may not be present
        # since #1 is always there, we can always resolve it to a particular patient
        # but #2 is trickier...for now, we're going with a prefix given
        # by the task that the user must include in their response
        self.dispatch = {}
        
        # a reference to the app, so we can send messages to the user
        # w/o first receiving a message
        self.app = app

        # load up the machines when we first start
        self._load_machines()

    # ==============================
    # == callbacks, invoked by App
    # ==============================
    
    def execute(self, instance):
        # the app calls this when a request to start a task
        # has been received from the scheduler.
        # all we have to do is load the task, start it,
        # and add it to the dispatch table so that we can
        # later route messages + timeouts to it

        # promote the instance to 'running'
        instance.mark_running()
        
        # create a new machine instance which we'll use to handle the interaction
        machine = self.machines[instance.task.id](self, instance)
        
        # add the new session/machine to the dispatch so we can route messages to it later
        self.dispatch[instance.id] = {
            'instance': instance,
            'machine': machine
            }

        # and finally start the machine
        try:
            machine.start()
        except TaskCompleteException:
            # remove it from the list as soon as it was born :\
            del self.dispatch[instance.id]
            # and mark the instance complete
            instance.mark_completed()
    
        return True # i guess this means it succeeded? perhaps we shouldn't return anything

    def handle(self, msg):
        # hold on to the msg text in case we need it later
        # (e.g. for handling the entire message rather than the message sans the prefix)
        original_text = msg.text
        
        # determine which of our tasks, if any, should
        # receive notifications for the message
        # if we can't find any, return false

        # =============================
        # == STEP 1. find the patient
        # =============================

        # using the given backend, find the patient to whom this message corresponds
        backend = msg.connection.backend.name

        try:
            if backend == u'sms' or backend == u'clickatell':
                patient = Patient.objects.get(address=msg.connection.identity)
            elif backend == u'email' or backend == u'jabber':
                patient = Patient.objects.get(email=msg.connection.identity)
            elif backend == u'irc':
                patient = Patient.objects.get(handle=msg.connection.identity)
            else:
                # unrecognizable backend...what now?
                raise Exception("Unrecognizable backend")
        except Patient.DoesNotExist:
            msg.respond("You're not a recognized user")
            return False
        except Exception as e:
            msg.respond(e.message)
            return False

        # keep a reference to the list of taskinstances for this patient
        patient_taskinstances = TaskInstance.objects.get_running_tasks().filter(patient=patient)

        # =============================
        # == STEP 2. find the task based on a prefix
        # =============================

        # before we begin, we have to ensure that we can uniquely refer
        # to each task by its prefix.
        # this is a hack, but if there's a collision we append a number
        # to each task's prefix to avoid it.
        # this applies until the task sets its prefix again.
        d = defaultdict(list)
        for m in [self.dispatch[instance.id]['machine'] for instance in patient_taskinstances]:
            d[m.prefix.rstrip(string.digits)].append(m)

        # look through our dictionary of machine prefixes for collisions
        for k in d:
            if len(d[k]) > 1:
                # multiple elements mapped to the same key means there's a collision
                # we have to renumber the prefixes, then
                for i in xrange(0, len(d[k])):
                    # only renumber tasks that haven't already been renumbered
                    if not d[k][i].prefix[-1].isdigit():
                        d[k][i].prefix = k + str(i+1)
        
        # we're a prefix-matching dispatch, so let's strip off the prefix
        parts = msg.text.partition(" ")
        prefix = parts[0]
        msg_content = parts[2]

        # set the message we have to the content part while we do the initial pass
        msg.text = msg_content

        # look through all the running tasks for our current patient
        for instance in patient_taskinstances:
            # look up the corresponding machine so we can examine its prefix
            machine = self.dispatch[instance.id]['machine']

            if machine.prefix.lower() == prefix.lower():
                # it matches, so let's try to run handle on it
                # we only give it the message, not the prefix
                try:
                    if machine.handle(msg):
                        # we handled it, stop looking for new ones
                        return True
                    else:
                        # this is implied, but i'm including it for the sake of clarity.
                        # basically, if this *isn't* the right machine, keep going till
                        # we find one, or run out of sessions for this user
                        continue
                except TaskCompleteException:
                    # this must've been raised from the machine's handle() event
                    # the machine is finished, remove it from the list
                    del self.dispatch[instance.id]
                    # and mark the session complete
                    instance.mark_completed()
                    return True

        # ...

        # =============================
        # == APPENDIX. we were unable to find a matching task for the prefix
        # =============================

        # if we got this far, it means we couldn't find a machine that matched the prefix
        # there are a few strategies from here:
        # 1) if they only have one task, attempt to dispatch it to that one.
        # 2) if they have multiple running tasks, tell them all the prefixes and let them choose
        # 3) if they have no running tasks, then tell them they don't have any(?)
        if patient_taskinstances.count() == 1:
            # 1) execute handle() on this single task
            instance = patient_taskinstances[0]
            machine = self.dispatch[instance.id]['machine']

            # restore the whole message, because we weren't able to find a prefix
            msg.text = original_text
            
            try:
                # attempt to handle it...if we can't, we just drop to 3, the 'no running tasks' message
                # we pass the task the full text, since they apparently didn't include a proper prefix
                if machine.handle(msg): return True
            except TaskCompleteException:
                del self.dispatch[instance.id]
                instance.mark_completed()
                return True
        elif patient_taskinstances.count() > 1:
            # 2) they have multiple tasks and we need them to choose one
            # let them know what's available
            prefixes = [self.dispatch[instance.id]['machine'].prefix for instance in patient_taskinstances]
            msg.respond("Please include one of the following before your message: %s" % (", ".join(prefixes)))
            return True
        elif patient_taskinstances.count() <= 0:
            # only send them "you have no running tasks" if they truly don't
            msg.respond("You have no running tasks right now")

        # 3) if we're here, they don't have any tasks that matched; not sure what we should do...
        return True

    def timeout(self, instance):
        # the App has told us that we have a task that's timed out, so let's give it a poke
        try:
            if instance.id in self.dispatch:
                # clear the timeout
                instance.timeout_date = None
                instance.save()
                # poke the task
                self.dispatch[instance.id]['machine'].timeout()
                # and tell them everything's ok?
                return True
            else:
                # should we just silently ignore this?
                self.debug("Attempted to invoke timeout on instance ID %d, but could not find an associated machine in the dispatch" % (instance.id))
                pass
        except TaskCompleteException:
            # this must've been raised from the machine's timeout() event
            # the machine is finished, remove it from the list
            del self.dispatch[instance.id]
            # and mark the session complete
            instance.mark_completed()
            return True

    # ==============================
    # == machine management
    # ==============================

    def _load_machines(self):
        # loads up all the machines (classes that inherit BaseTask that are listed
        # in the classes db) that we'll be instantiating to handle clients' requests
        self.machines = {}

        for task in Task.objects.all():
            try:
                # first, import the module, i guess :\
                _module = __import__(task.module, fromlist=[task.className])
                self.machines[task.id] = getattr(_module, task.className)
                self.info("Loaded class %s from module %s into machines w/ID %d" % (task.className, task.module, task.id))
            except:
                raise
                self.info("Unable to load class %s from module %s, continuing..." % (task.className, task.module))
        
    def removetask(self, instance):
        # remove the task from the dispatch, if it exists
        if instance.id in self.dispatch:
            del self.dispatch[instance.id]
            
    @classmethod
    def _outer_instance_removed(*args, **kwargs):
        # called right before a TaskInstance model is deleted
        # notify all of our dispatchers (usually just one)
        # that a session was removed
        instance = kwargs['instance']
        print "Removing task ID %d due to instance #%d being removed" % (instance.id, instance.id)
        for dispatcher in TaskDispatcher.get_instances():
            dispatcher.removetask(instance)

    # ==============================
    # == persistent state management
    # ==============================

    def freeze(self):
        """
        Attempts to pickle and store the machine instances
        from the dispatch table into their respective TaskInstances.
        Called prior to the router shutting down.
        """
        for item in self.dispatch.itervalues():
            # pickle the machine into its instance
            item['instance'].machine_data = pickle.dumps(item['machine'])
            item['instance'].save()
            self.info("Pickled machine %s from instance ID %d" % (item['instance'].name, item['instance'].id))

    def thaw(self):
        """
        Scans the TaskInstances for running processes with machine_data
        and attempts to unpickle them into the dispatch table. The
        machine_data is cleared afterward in order to prevent it from
        being possibly restored twice.
        """
        for instance in TaskInstance.objects.filter(status="running",machine_data__isnull=False):
            try:
                # unpickle the machine into the dispatch table
                machine = pickle.loads(str(instance.machine_data))
                # reassociate the dispatch, since this is something that couldn't be pickled
                machine.dispatch = self
                self.dispatch[instance.id] = {
                    'instance': instance,
                    'machine': machine
                }
                # clear the pickled data and save()
                instance.machine_data = None
                instance.save()
                # and tell our parent about this
                self.info("Unpickled machine %s from instance ID %d" % (instance.name, instance.id))
            except Exception as e:
                # hmm, i guess we should just keep moving on
                # but i wonder if we should remove the task? or at least error it out?
                self.info("ERROR: unable to unpickle machine %s from instance ID %d" % (instance.name, instance.id))
                instance.mark_errored("Unable to unpickle associated machine from the machine_data field: %s" % (str(e)))

    # ==============================
    # == helpers for dealing with incoming and outgoing messages
    # ==============================

    def send(self, instance, message, accepts_response=False):
        """
        Wraps the act of sending messages (whether they be replies or not); includes
        the prefix for the machine in the send.

        if accepts_response is True, the "type prefix before your reply" text is added
        to the end of the message.
        """
        # look up the machine and formulate the prefix
        # only append it if they have more than one running task
        if accepts_response and TaskInstance.objects.filter(patient=instance.patient,status="running").count() > 1:
            message += ' Type "%s" before your reply.' % self.dispatch[instance.id]['machine'].prefix
        # and send the message, finally
        LogMessage(instance=instance, message=message, outgoing=True).save()
        self.app.send(instance.patient.get_address(), message, identityType=instance.patient.contact_pref)

    def get_dispatch_table(self):
        """
        Returns the dispatch table in a format that the task manager status page can parse.
        """
        dispatch_table = []
        for instanceid in self.dispatch:
            dispatch_table.append({
                'address': self.dispatch[instanceid]['instance'].patient.address,
                'machine': self.dispatch[instanceid]['instance'].task.name,
                'status': self.dispatch[instanceid]['instance'].status
                })
        return dispatch_table

# =============================================================
# === signal handlers and other miscellanea below...
# =============================================================

# allow us to be notified of any changes to the TaskInstance table
# so that we can clean up our associated instances, etc.
from django.db.models.signals import pre_delete
pre_delete.connect(TaskDispatcher._outer_instance_removed, sender=TaskInstance)
