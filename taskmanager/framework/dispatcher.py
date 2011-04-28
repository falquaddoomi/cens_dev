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
from taskmanager.models import Patient, Task, Process, Session, SessionMessage
from taskmanager.tasks.base import BaseTask, TaskCompleteException
from utilities import KeepRefs

class TaskDispatcher(KeepRefs, LoggerMixin):
    @classmethod
    def _outer_session_removed(*args, **kwargs):
        # called right before a Session model is deleted
        # notify all of our dispatchers (usually just one)
        # that a session was removed
        instance = kwargs['instance']
        print "Removing task ID %d due to session #%d being removed" % (instance.id, instance.id)
        for dispatcher in TaskDispatcher.get_instances():
            dispatcher.removetask(instance)
    
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
        Session.objects.get_current_sessions().delete()
        # and kill all the resulting hollow processes
        Process.objects.annotate(num_sessions=Count('session')).filter(num_sessions=0).delete()
        
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
                self.info("Unable to load class %s from module %s, continuing..." % (task.className, task.module))

    def _log(self, session, text, outgoing):
        entry = SessionMessage(session=session, message=text, outgoing=outgoing)
        entry.save()
                
    def exectask(self, task, patient, process, args):
        # the app calls this when a request to start a task
        # has been received from the scheduler.
        # all we have to do is load the task, start it,
        # and add it to the dispatch table so that we can
        # later route messages + timeouts to it

        # create a session and throw a handle to it into the tasks table
        session = Session(patient=patient, task=task, mode=patient.contact_pref, process=process)
        session.save()

        # create a new machine instance which we'll use to handle the interaction
        machine = self.machines[task.id](self.app, patient, session, args)
        
        # add the new session/machine to the dispatch so we can route messages to it later
        self.dispatch[session.id] = {
            'session': session,
            'machine': machine
            }

        # and finally start the machine!
        try:
            machine.start()
        except TaskCompleteException:
            # remove it from the list as soon as it was born :\
            del self.dispatch[session.id]
            # and mark the session complete
            session.mark_complete()
    
        return True # i guess this means it succeeded? perhaps we shouldn't return anything

    def removetask(self, session):
        # remove the task from the dispatch, if it exists
        if session.id in self.dispatch:
            del self.dispatch[session.id]

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

        # now that we ostensibly know the patient, enumerate their sessions
        for session in Session.objects.get_current_sessions().filter(patient=patient):
            # invoke the machine associated with this session's handler
            # if it returns true, we're done, otherwise go through all the other sessions, i guess :\
            try:
                if session.id in self.dispatch and self.dispatch[session.id]['machine'].handle(msg):
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
                del self.dispatch[session.id]
                # and mark the session complete
                session.mark_complete()
                return True

        # no task matched! we should probably just tell them that they don't have any existing tasks...
        msg.respond("You have no running tasks right now")
        return True

# =============================================================
# === signal handlers and other miscellanea below...
# =============================================================

# allow us to be notified of any changes to the Sessions table
# so that we can clean up our associated instances, etc.
from django.db.models.signals import pre_delete
pre_delete.connect(TaskDispatcher._outer_session_removed, sender=Session)
