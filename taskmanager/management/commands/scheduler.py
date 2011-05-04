from twisted.web import server, resource
from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from stringprod import StringProducer

import urllib, urlparse

import sys, json
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from taskmanager.models import *

from django.conf import settings

# used by check_schedule() to determine if it can send tasks
# and by showJSONStatus() to let the interface know we're sleeping
def isQuietHours():
    return (not settings.SCHEDULER_QUIET_HOURS is None) and (datetime.now().hour >= settings.SCHEDULER_QUIET_HOURS['start'] or datetime.now().hour <= settings.SCHEDULER_QUIET_HOURS['end'])


# =========================================================================================
# === HTTP interface definition
# =========================================================================================

class HTTPCommandBase(resource.Resource):
    isLeaf = False
    
    def __init__(self):
        resource.Resource.__init__(self)
        
    def getChild(self, name, request):
        if name == '':
            return self
        return resource.Resource.getChild(self, name, request)
    
    def render_GET(self, request):
        print "[GET] /"
        return "scheduler interface"

class HTTPStatusCommand(resource.Resource):
    def __init__(self):
        resource.Resource.__init__(self)
        
    def showJSONStatus(self, all_tasks=True):
        if all_tasks:
            tasks = ScheduledTask.objects.all()
        else:
            tasks = ScheduledTask.objects.get_pending_tasks()

        # apply extra filtering and sorting, regardless of the source
        tasks = tasks.filter(completed=False,active=True).order_by('-schedule_date')

        # stores the list of tasks that we'll be sending to the caller
        tasklist = []

        for task in tasks:
            tasklist.append({
                'id': task.id,
                'target': task.task.name,
                'arguments': json.loads(task.arguments),
                'schedule_date': task.schedule_date.ctime(),
                'completed': task.completed
                })

        return json.dumps({'status': ('running', 'sleeping')[isQuietHours()], 'tasks': tasklist})
    
    def showStatus(self, all_tasks=True):
        out = "<table>"
        out += "<tr class='header'><td>ID</td><td>Target</td><td>Arguments</td><td>Schedule Date</td><td>Completed</td></tr>"
        
        if all_tasks:
            tasks = ScheduledTask.objects.all()
        else:
            tasks = ScheduledTask.objects.get_pending_tasks()

        for task in tasks:
            out += '''
            <tr>
                <td>%(id)s</td><td>%(target)s</td><td>%(arguments)s</td><td>%(schedule_date)s</td><td>%(completed)s</td>
            </tr>''' % {'id': task.id, 'target': task.task.name, 'arguments': task.arguments, 'schedule_date': task.schedule_date, 'completed': task.completed}

        return str('''
        <html>
            <head>
            <style>.header td { font-weight: bold }</style>
            </head>
            <body>%s</body>
        </html>''' % (out))
    
    isLeaf = True
    def render_GET(self, request):
        if 'html' in request.args:
            print "[GET] /status"
            return self.showStatus('alltasks' in request.args)
        else:
            print "[GET] /status (json)"
            return self.showJSONStatus('alltasks' in request.args)


# =========================================================================================
# === task database access methods
# =========================================================================================

def task_finished(response, sched_taskid):
    t = ScheduledTask.objects.get(pk=sched_taskid)
    t.completed = True
    t.result = response.code
    t.completed_date = datetime.now()
    t.save()
    print "- finished %s (%d) w/code %s" % (t.task.name, sched_taskid, str(response.code))

def task_errored(response, sched_taskid):
    t = ScheduledTask.objects.get(pk=sched_taskid)
    t.result = response.getErrorMessage()
    t.save()
    print "- errored out on task %s (%d), reason: %s" % (t.task.name, sched_taskid, response.getErrorMessage())
    response.printTraceback()

def session_timeout_finished(response, sessionid):
    t = Session.objects.get(pk=sessionid)
    print "- timed out %s (%d) w/code %s" % (t.task.name, sessionid, str(response.code))

def session_timeout_errored(response, sessionid):
    t = Session.objects.get(pk=sessionid)
    print "- errored out on timing out %s (%d), reason: %s" % (t.task.name, sessionid, response.getErrorMessage())
    response.printTraceback()


# =========================================================================================
# === actual scheduling methods
# =========================================================================================

def check_schedule():
    # before we do anything, make sure it's not "quiet hours"
    # if it is, do nothing and run this method later
    if isQuietHours():
        # check again in 30 minutes...this is kind of silly, but hey
        print "*** Quiet hours are in effect (%d:00 to %d:00, currently: %d:00), calling again in 30 minutes..." % (
            settings.SCHEDULER_QUIET_HOURS['start'],
            settings.SCHEDULER_QUIET_HOURS['end'],
            datetime.now().hour
        )
        reactor.callLater(60*30, check_schedule)
        return
    
    tasks = ScheduledTask.objects.get_due_tasks()
    
    for sched_task in tasks[0:1]:
        agent = Agent(reactor)

        # ensure that the user is not halted -- if they are, we can't execute this task :\
        if sched_task.patient.halted:
            # print "ERROR: Cannot execute task: %s (%d), user is in the halt status" % (sched_task.task.name, sched_task.id)
            continue
        
        print "Executing task: %s (%d)" % (sched_task.task.name, sched_task.id)

        payload_dict = {
            'patient': sched_task.patient.id,
            'task': sched_task.task.id,
            'arguments': json.dumps(sched_task.arguments)
            }

        if sched_task.process:
            payload_dict['process'] = sched_task.process.id

        payload = urllib.urlencode(payload_dict)

        d = agent.request(
            'POST',
            settings.SCHEDULER_TARGET_URL,
            Headers({
                    "Content-Type": ["application/x-www-form-urlencoded;charset=utf-8"],
                    "Content-Length": [str(len(payload))]
                    }),
            StringProducer(payload))

        d.addCallback(task_finished, sched_taskid=sched_task.id)
        d.addErrback(task_errored, sched_taskid=sched_task.id)
        
    # run again in a bit
    reactor.callLater(settings.SCHEDULER_CHECK_INTERVAL, check_schedule)

def check_timeouts():
    sessions = Session.objects.get_timedout_sessions()
    
    for session in sessions:
        agent = Agent(reactor)
        
        print "Timing out session: %s (%d)" % (session.task.name, session.id)

        payload_dict = {
            'patient': session.patient.id,
            'session': session.id
            }

        payload = urllib.urlencode(payload_dict)

        d = agent.request(
            'POST',
            settings.SCHEDULER_TARGET_TIMEOUT_URL,
            Headers({
                    "Content-Type": ["application/x-www-form-urlencoded;charset=utf-8"],
                    "Content-Length": [str(len(payload))]
                    }),
            StringProducer(payload))

        d.addCallback(session_timeout_finished, sessionid=session.id)
        d.addErrback(session_timeout_errored, sessionid=session.id)
        
    # run again in a bit
    reactor.callLater(settings.SCHEDULER_CHECK_INTERVAL, check_timeouts)


# =========================================================================================
# === twisted entrypoint and django command definitions
# =========================================================================================

def main(port=8080):        
    # construct the resource tree
    root = HTTPCommandBase()
    root.putChild('status', HTTPStatusCommand())

    print "-- Target URL: %s\n-- Target timeout URL: %s" % (settings.SCHEDULER_TARGET_URL, settings.SCHEDULER_TARGET_TIMEOUT_URL)

    print "Running scheduler on port %d..." % (int(port))
    
    site = server.Site(root)
    reactor.callLater(3, check_schedule)
    reactor.callLater(5, check_timeouts)
    reactor.listenTCP(int(port), site)
    reactor.run()

if __name__ == '__main__':
    main()

# to allow this to be executed as a django command...
class Command(BaseCommand):
    args = '<port>'
    help = 'Runs the scheduler via twisted'

    def handle(self, *args, **options):
        main(*args)

