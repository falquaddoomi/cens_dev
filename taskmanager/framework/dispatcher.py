"""
This module will contain the definition of the
dispatcher class, which maintains a list of currently
running tasks and their associated users. When a message
is received, this class will decide first which user
and then which task for that user the message is intended for,
and will invoke the handle() event on that task instance.
"""

import json
from django.db.models import Count

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

        # kill all current sessions, since our dispatch is empty at start
        TaskInstance.objects.get_running_tasks().delete()
        # and kill all the resulting hollow processes
        Process.objects.reap_empty_processes()
        
        # a reference to the app, so we can send messages to the user
        # w/o first receiving a message
        self.app = app

        # load up the machines when we first start
        self._load_machines()

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

    def _log(self, instance, text, outgoing):
        entry = LogMessage(instance=instance, message=text, outgoing=outgoing)
        entry.save()
                
    def execute(self, instance):
        # the app calls this when a request to start a task
        # has been received from the scheduler.
        # all we have to do is load the task, start it,
        # and add it to the dispatch table so that we can
        # later route messages + timeouts to it

        # promote the instance to 'running'
        instance.mark_running()
        
        # create a new machine instance which we'll use to handle the interaction
        machine = self.machines[instance.task.id](self.app, instance)
        
        # add the new session/machine to the dispatch so we can route messages to it later
        self.dispatch[instance.id] = {
            'instance': instance,
            'machine': machine
            }

        # and finally start the machine!
        try:
            machine.start()
        except TaskCompleteException:
            # remove it from the list as soon as it was born :\
            del self.dispatch[instance.id]
            # and mark the instance complete
            instance.mark_completed()
    
        return True # i guess this means it succeeded? perhaps we shouldn't return anything

    def handle(self, msg):
        # determine which of our tasks, if any, should
        # receive notifications for the message
        # if we can't find any, return false

        # using the given backend, find the patient to whom this message corresponds
        backend = msg.connection.backend.name

        try:
            if backend == u'sms':
                patient = Patient.objects.get(address=msg.connection.identity)
            elif backend == u'email':
                patient = Patient.objects.get(email=msg.connection.identity)
            elif backend == u'irc':
                patient = Patient.objects.get(handle=msg.connection.identity)
            elif backend == u'tropo':
                patient = Patient.objects.get(email=msg.connection.identity)
            else:
                # unrecognizable backend...what now?
                raise Exception("Unrecognizable backend")
        except NameError as e:
            msg.respond("You're not a recognized user")
            return False
        except Exception as e:
            msg.respond(e.message)
            return False

        # we're a prefix-matching dispatch, so let's strip off the prefix
        

        # now that we ostensibly know the patient, enumerate their sessions
        for instance in TaskInstance.objects.get_running_tasks().filter(patient=patient):
            # invoke the machine associated with this session's handler
            # if it returns true, we're done, otherwise go through all the other sessions, i guess :\
            try:
                if instance.id in self.dispatch and self.dispatch[instance.id]['machine'].handle(msg):
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

        # no task matched! we should probably just tell them that they don't have any existing tasks...
        msg.respond("You have no running tasks right now")
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

    def removetask(self, instance):
        # remove the task from the dispatch, if it exists
        if instance.id in self.dispatch:
            del self.dispatch[instance.id]
            
    @classmethod
    def _outer_session_removed(*args, **kwargs):
        # called right before a TaskInstance model is deleted
        # notify all of our dispatchers (usually just one)
        # that a session was removed
        instance = kwargs['instance']
        print "Removing task ID %d due to session #%d being removed" % (instance.id, instance.id)
        for dispatcher in TaskDispatcher.get_instances():
            dispatcher.removetask(instance)

# =============================================================
# === signal handlers and other miscellanea below...
# =============================================================

# allow us to be notified of any changes to the TaskInstance table
# so that we can clean up our associated instances, etc.
from django.db.models.signals import pre_delete
pre_delete.connect(TaskDispatcher._outer_session_removed, sender=TaskInstance)
