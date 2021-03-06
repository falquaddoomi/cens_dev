"""
This module will contain the definition of the
dispatcher class, which maintains a list of currently
running tasks and their associated users. When a message
is received, this class will decide first which user
and then which task for that user the message is intended for,
and will invoke the handle() event on that task instance.
"""

import json, string, pickle, datetime
from django.db.models import Count

from rapidsms.contrib.scheduler.models import EventSchedule

from rapidsms.log.mixin import LoggerMixin
from taskmanager.models import Patient, Task, Process, TaskInstance, TaskEventSchedule, LogMessage
from taskmanager.tasks.base import BaseTask, TaskCompleteException
from utilities import KeepRefs, parsedt

import settings

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
        # we pass it a reference to the dispatch and a reference to its corresponding db entity
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
            ## TODO: should we be sending messages to people who aren't users?
            ## we've had an issue with spammers, so this is disabled for now
            # msg.respond("You're not a recognized user")
            self.info("Ignoring message since the sender is not a recognized user")
            return False
        except Exception as e:
            msg.respond(e.message)
            return False

        # keep a reference to the list of taskinstances for this patient
        patient_taskinstances = TaskInstance.objects.get_running_tasks().filter(patient=patient)

        # =============================
        # == STEP 2. find the task based on a prefix
        # =============================
        
        # we're a prefix-matching dispatch, so let's strip off the prefix
        # fyi: parts[1] contains the separator, in this case a single space
        parts = msg.text.partition(" ")
        prefix = parts[0]
        msg_content = parts[2]

        # hold on to the msg text in case we need it later
        # (e.g. for handling the entire message rather than the message sans the prefix)
        original_text = msg.text

        # set the message we have to the content part while we do the initial pass
        msg.text = msg_content

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # ~~ SUB-STEP 2a. determine if it's a reserved prefix (e.g. "STOP")
        # ~~ also determine if they're trying to interact with us while they're stopped
        # ~~ and tell them that they have to 'resume' to receive messages again
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        if prefix.lower() == "stop":
            # set their status to halted and tell them how to resume
            patient.halted = True
            patient.save()
            msg.respond("You have opted-out of receiving messages. Text back 'resume' to start receiving messages again.")
            return True
        
        if prefix.lower() == "resume":
            if patient.halted:
                # set their status to not halted and thank them for resuming
                patient.halted = False
                patient.save()
                msg.respond("Thank you for opting-in to the system; you will receive messages again.")
                return True
            else:
                msg.respond("You were not opted-out of the system; you will continue to receive messages.")
            return True

        if patient.halted:
            # a halted patient can't interact with the system
            # tell them that they have to send 'resume' to start again
            msg.respond("You are currently opted-out of the system. Text back 'resume' to start receiving messages again.")
            return True

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # ~~ SUB-STEP 2b. find corresponding machine by prefix
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        # look through all the running tasks for our current patient
        for instance in patient_taskinstances:
            # look up the corresponding machine so we can examine its prefix
            machine = self.dispatch[instance.id]['machine']

            if machine.prefix.lower() == prefix.lower():
                # it matches, so let's try to run handle on it
                # we only give it the message, not the prefix
                try:
                    # remove any scheduled message resends for this task before we start
                    instance.taskeventschedule_set.all().delete()
                        
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
                # remove any scheduled message resends for this task before we start
                instance.taskeventschedule_set.all().delete()
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
                # remove any scheduled message resends for this task
                instance.taskeventschedule_set.all().delete()
                # clear the timeout
                instance.timeout_date = None
                instance.save()
                # poke the task
                self.dispatch[instance.id]['machine'].timeout()
                # and tell them everything's ok?
                return True
            else:
                # should we just silently ignore this?
                self.info("ERROR: Attempted to invoke timeout on instance ID %d, but could not find an associated machine in the dispatch" % (instance.id))
                pass
        except TaskCompleteException:
            # this must've been raised from the machine's timeout() event
            # the machine is finished, remove it from the list
            del self.dispatch[instance.id]
            # and mark the session complete
            instance.mark_completed()
            return True
            
    def poke(self, instance):
        # the App has told us that we have a task that needs to be poked, so poke it
        try:
            if instance.id in self.dispatch:
                # remove any scheduled message resends for this task
                instance.taskeventschedule_set.all().delete()
                # clear the poke
                instance.poke_date = None
                instance.save()
                
                # make sure that the poke date has actually be cleared before we trigger the poke
                instance = TaskInstance.objects.get(id=instance.id)
                if instance.poke_date == None:
                    # poke the task
                    self.dispatch[instance.id]['machine'].poke()
                    
                # and tell them everything's ok?
                return True
            else:
                # should we just silently ignore this?
                self.info("ERROR: Attempted to poke instance ID %d, but could not find an associated machine in the dispatch" % (instance.id))
                pass
        except TaskCompleteException:
            # this must've been raised from the machine's poke() event
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
            try:
                # ensure we have the most up-to-date version of the object
                item['instance'] = TaskInstance.objects.get(pk=item['instance'].pk)
                
                # only pickle running machines
                if item['instance'].status != "running":
                    continue
                # pickle the machine into its instance
                item['instance'].machine_data = pickle.dumps(item['machine'])
                item['instance'].save()
                self.info("Pickled machine %s from instance ID %d" % (item['instance'].name, item['instance'].id))
            except Exception as e:
                # ok, we couldn't pickle it...this is likely b/c there's no associated instance
                self.info("ERROR: Couldn't pickle machine %s from instance ID %d: %s" % (item['instance'].name, item['instance'].id, str(e)))
                continue

    def thaw(self):
        """
        Scans the TaskInstances for running processes with machine_data
        and attempts to unpickle them into the dispatch table. The
        machine_data is cleared afterward in order to prevent it from
        being possibly restored twice.
        """
        
        for instance in TaskInstance.objects.filter(status="running",machine_data__isnull=False):
            try:
                # check first for a resurrection string in the machine data
                if str(instance.machine_data).startswith("@@resurrect:"):
                    # if it's there, try to create a machine and run resurrect() on it
                    machine = self.machines[instance.task.id](self, instance)
                    machine.dispatch = self
                    if not machine.resurrect(str(instance.machine_data)[12:]):
                        print "Couldn't resurrect %d for some reason..." % (instance.id)
                        raise Exception("Resurrection failed")
                else:
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
                self.info(
                    "ERROR: unable to unpickle machine %s from instance ID %d :: %s" %
                    ( instance.name, instance.id, (str(e)) )
                )
                instance.mark_errored("Unable to unpickle associated machine from the machine_data field: %s" % (str(e)))

    # ==============================
    # == supports for other parts of the framework
    # ==============================

    def request_prefix(self, patient, desired_prefix):
        """
        Called by a task that's about to associate itself with a prefix; returns
        a prefix that can be unambiguously associated with the task (preferably
        desired_prefix as-is).

        If desired_prefix is not in use, desired_prefix is returned as-is.
        If it is in use, returns an unambiguous form of the prefix, e.g. "appt2".
        """

        patient_taskinstances = TaskInstance.objects.get_running_tasks().filter(patient=patient)

        # add all the prefixes for running machines belonging to the current user to a list
        prefixes = []
        for m in [self.dispatch[instance.id]['machine'] for instance in patient_taskinstances if instance.status == "running"]:
            prefixes.append(m)

        # check our dictionary of machine prefixes for collisions
        # keep trying to find a new prefix until we get a unique one
        new = desired_prefix
        pid = 2
        while new in prefixes:
            new = desired_prefix + str(pid)
            pid += 1

        return new

    def send(self, instance, message, accepts_response=False, resending=False):
        """
        Wraps the act of sending messages (whether they be replies or not); includes
        the prefix for the machine in the send.

        if accepts_response is True, the "type prefix before your reply" text is added
        to the end of the message.
        """
        # save this for scheduling response reminders
        original_msg = message
        
        # look up the machine and formulate the prefix
        # only append it if they have more than one running task
        if accepts_response and TaskInstance.objects.filter(patient=instance.patient,status="running").count() > 1:
            message += ' Type "%s" before your reply.' % self.dispatch[instance.id]['machine'].prefix
        # and send the message, finally
        LogMessage(instance=instance, message=message, outgoing=True).save()
        self.app.send(instance.patient.get_address(), message, identityType=instance.patient.contact_pref)

        # also, if resends are enabled, add a few, and only if the message needs a response
        # don't do this if the message doesn't accept a response, and certainly don't do this
        # if we're already sending a response! (infinite messages are no good)
        try:
            if not resending and accepts_response:
                # formulate all the data we need into a params packet
                params = {
                    'instanceid': instance.pk,
                    'message': original_msg,
                    }

                # for each resend, we create a separate scheduled event...
                start_time = datetime.datetime.now() # start us out at now
                for i in xrange(0, settings.MESSAGE_RESEND_TRIES):
                    # compute the date on which to send the thing
                    # basically increments start_time in units of MESSAGE_RESEND_DELAY
                    start_time = parsedt(settings.MESSAGE_RESEND_DELAY, start_time)
                    
                    # and create a TaskEventSchedule associated with this instance
                    t = TaskEventSchedule(
                        owner=instance,
                        callback="taskmanager.framework.dispatcher.resend_message",
                        minutes='*',
                        callback_kwargs=params,
                        start_time=start_time,
                        count=1)
                    t.save()
        except:
            # FIXME: is it ok to just ignore being unable to schedule message retries?
            raise

    def get_dispatch_table(self):
        """
        Returns the dispatch table in a format that the task manager status page can parse.
        """
        dispatch_table = []
        for instanceid in self.dispatch:
            dispatch_table.append({
                'instance ID': instanceid,
                'patient': str(self.dispatch[instanceid]['instance'].patient),
                'address': self.dispatch[instanceid]['instance'].patient.address,
                'machine': self.dispatch[instanceid]['instance'].task.name,
                'task': self.dispatch[instanceid]['instance'].name,
                'status': self.dispatch[instanceid]['instance'].status,
                'details': self.dispatch[instanceid]['instance'].details
                })
        return dispatch_table

# =============================================================
# === signal handlers and other miscellanea below...
# =============================================================

# allow us to be notified of any changes to the TaskInstance table
# so that we can clean up our associated instances, etc.
from django.db.models.signals import pre_delete
pre_delete.connect(TaskDispatcher._outer_instance_removed, sender=TaskInstance)

# handles dispatching a TaskEventSchedule event into the dispatch, properly
def resend_message(router, instanceid, message):
    app = router.get_app('taskmanager')
    assert (app.router==router)

    # look up the associated instance and die if we can't
    try:
        instance = TaskInstance.objects.get(pk=instanceid)
    except:
        return
    
    print "Retransmitting to patient %s: '%s'" % (instance.patient, message)

    # attempt to resend it now
    app.dispatch.send(instance, message, resending=True)
