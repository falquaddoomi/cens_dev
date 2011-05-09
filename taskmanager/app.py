import sys, json, re, traceback
from datetime import datetime, timedelta

import rapidsms
from rapidsms.contrib.scheduler.models import EventSchedule, ALL

from taskmanager.models import *

# and the framework handlers, too
from framework import dispatcher

class App(rapidsms.apps.base.AppBase):
    """
    Implements the message handler and passer, which invokes the Task Dispatcher and Executor when necessary.

    This class simply coordinates the efforts of the Task Dispatcher + Executor by routing messages and events to them; it does nothing on its own.
    """

    # =========================================================================
    # === RapidSMS event handlers
    # === (refer to http://docs.rapidsms.org/Apps for message-related events)
    # =========================================================================
    
    def start(self):
        self.debug("TaskManager App :: start() invoked, beginning...")

        # create our default dispatcher
        # it uses the identity of the incoming message + a message prefix
        # to route messages to the list of taskinstances/machines it maintains
        self.dispatch = dispatcher.TaskDispatcher(self)

    def handle(self, message):
        self.debug('in App.handle(): message type: %s, message.text: %s', type(message),  message.text)

        # FIXME: strips out all non-normal ascii characters,
        # which is a decent stopgap till we figure out the issue with the modem
        message.text = "".join([c for c in message.text if ord(c) <= 128])

        # pass the entire message to the dispatch to let it handle it
        result = self.dispatch.handle(message)

        # what do we do if the result isn't ok...? just return true for now, i suppose
        return True # we just handle anything for now, but in the future we'll only handle it if we can

    def default(self, message):
        # this is invoked if no app is able to handle the message (e.g. returns True in the handle() phase)
        # since we're the only important app, it's likely this will get
        # called if we don't return True in handle() ourselves
        pass


    # =========================================================================
    # === AJAX handlers
    # =========================================================================        
                                        
    def ajax_GET_status(self, getargs, postargs=None):
        # this one's invoked from the interface on the Monitor::Task Manager view.
        # we should return some salient details about what tasks we have running,
        # who they're for, and anything else that might be useful to know...
        return {'status':'OK'}

    def ajax_POST_exec(self, getargs, postargs=None):
        # we've received a request from the scheduler
        # to promote a task to the running status
        instance = TaskInstance.objects.get(pk=postargs['instanceid'])
        self.dispatch.execute(instance)
        return {'status': 'OK'}

    def ajax_POST_timeout(self, getargs, postargs=None):
        # sent from the scheduler to 'poke' a running task into taking some action.
        # this is usually a result of the user not responding quickly enough to a message.
        # common things the task might do: resend the original message, silently stop,
        # schedule other reminders, post administrative alerts, etc.
        instance = TaskInstance.objects.get(pk=postargs['instanceid'])
        self.dispatch.timeout(instance)
        return {'status': 'OK'}


    # =========================================================================
    # === Utility methods
    # =========================================================================
    
    def send(self, identity, text, identityType='sms', subject=None):
        """
        Utility method to allow us to send messages by invoking the appropriate backend.

        identity: the email address or phone number of the target
        identityType: a string that identifies the backend ('email' and 'sms' are most common)
        subject: the subject line if the identity type is 'email', otherwise ignored
        """

        # Used to send messages when get a timeout or from init
        # try:
        from rapidsms.models import Backend 
        bkend, createdbkend = Backend.objects.get_or_create(name=identityType)        
        conn, createdconn = rapidsms.models.Connection.objects.get_or_create(backend=bkend, identity=identity)
        message = rapidsms.messages.outgoing.OutgoingMessage(conn, text)
        
        if identityType is 'email':
            # use a default subject line if none was given, or the subject parameter if one was
            message.subject = (subject, 'testing '+ str(self.__class__))[subject is None]

        if message.send():
            self.debug('sent message.text: %s', text)
        # except Exception as e:
        #    self.debug('problem sending outgoing message: createdbkend?:%s; createdconn?:%s; exception: %s', createdbkend, createdconn, e)

    # **** FAISAL: below are from the old app.py, left as an example of using RapidSMS's short-term event scheduler

    # schedules reminder to respond messages
    def schedule_response_reminder(self, d):
        self.debug('in App.schedulecallback(): self.router: %s', self.router)
        cb = d.pop('callback')
        m = d.pop('minutes')
        reps = d.pop('repetitions')
        self.debug('callback:%s; minutes:%s; repetitions:%s; kwargs:%s',cb,m,reps,d)
        
        t = datetime.now()
        s = timedelta(minutes=m)
    
        # for n in [(t + 1*s), (t + 2*s), ... (t + r+s)], where r goes from [1, reps+1)
        #for st in [t + r*s for r in range(1,reps+1)]:
        # MLL: Changed to do one at a time, so resend will schedule the next one
        schedule = EventSchedule(callback=cb, minutes=ALL, callback_kwargs=d, start_time=t+s, count=1)
        schedule.save()
        self.debug('scheduling a reminder to fire after %s at %s, id=%d', s, s+t, schedule.id)

    def clear_response_reminder(self, tnsid, identity):
        # anytime we want to clear out pending timeouts, this will deactivate them
        self.debug('in App.clear_response_reminder(): looking to deactivate tnsid: %s, indetity: %s', tnsid, identity)
        clearlist = []
        for es in EventSchedule.objects.filter(active=True):
            checkdict = es.callback_kwargs
            if checkdict['tnsid'] == tnsid and checkdict['identity'] == identity:
                self.debug('deactivating %i %i', es.id, es.pk)
                es.active=False
                es.save()
        # tried to make this do es.delete() but it did not seem to work!


        
# FAISAL: ??? no idea what this does, but it looks important

def callresend(router, **kwargs):
    from datetime import datetime
    
    app = router.get_app('taskmanager')
    assert (app.router==router)
    
    app.debug('found app/taskmanager:%s', app)
    app.debug('%s', datetime.now())
    app.debug('router: %s; received: kwargs:%s' % (router, kwargs))

    # rapidsms.contrib.scheduler marks each entry with EventSchedule.active=0 after it's fired.
    #app.resend(kwargs['msgid'], kwargs['identity'])
    #app.resend(kwargs['tnsid'], kwargs['identity'])
    app.tm.handle_timeout(kwargs['tnsid'], kwargs['identity'])
