from twisted.web import server, resource
from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from stringprod import StringProducer

import urllib, urlparse

import sys, json
import datetime

from django.core.management.base import BaseCommand, CommandError
from taskmanager.models import TaskInstance
from django.db.models import Q

from django.conf import settings

if not settings.SCHEDULER_QUIET_HOURS is None:
    QUIET_START_TIME = datetime.time(settings.SCHEDULER_QUIET_HOURS['start'])
    QUIET_END_TIME = datetime.time(settings.SCHEDULER_QUIET_HOURS['end'])

# used by check_schedule() to determine if it can send tasks
# and by showJSONStatus() to let the interface know we're sleeping
def isQuietHours():
    global QUIET_START_TIME, QUIET_END_TIME
    rightnow = datetime.datetime.now().time()
    return (not settings.SCHEDULER_QUIET_HOURS is None) and (rightnow >= QUIET_START_TIME or rightnow <= QUIET_END_TIME)

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
            instances = TaskInstance.objects.all()
        else:
            instances = TaskInstance.objects.get_pending_tasks()

        # apply extra filtering and sorting, regardless of the source
        instances = instances.order_by('-schedule_date')

        # stores the list of tasks that we'll be sending to the caller
        tasklist = []

        for instance in instances:
            tasklist.append({
                'id': instance.id,
                'target': instance.task.name,
                'params': json.loads(instance.params),
                'schedule_date': instance.schedule_date.ctime(),
                'completed': (instance.status == "completed")
                })

        return json.dumps({'status': ('running', 'sleeping')[isQuietHours()], 'tasks': tasklist})
    
    def showStatus(self, all_tasks=True):
        out = "<table>"
        out += "<tr class='header'><td>ID</td><td>Target</td><td>Arguments</td><td>Schedule Date</td><td>Status</td></tr>"
        
        if all_tasks:
            instances = TaskInstance.objects.all()
        else:
            instances = TaskInstance.objects.get_pending_tasks()

        for instance in instances:
            out += '''
            <tr>
                <td>%(id)s</td><td>%(target)s</td><td>%(arguments)s</td><td>%(schedule_date)s</td><td>%(status)s</td>
            </tr>''' % {'id': instance.id, 'target': instance.task.name, 'arguments': instance.params, 'schedule_date': instance.schedule_date, 'status': instance.status}

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

def task_finished(response, instanceid):
    t = TaskInstance.objects.get(pk=instanceid)
    print "- triggered %s (%d) w/code %s" % (t.task.name, instanceid, str(response.code))

def task_errored(response, instanceid):
    t = TaskInstance.objects.get(pk=instanceid)
    # t.mark_errored(response.getErrorMessage()) # uncomment if you don't want the scheduler to retry on error
    print "- errored out on task %s (%d), reason: %s...retrying soon" % (t.task.name, instanceid, response.getErrorMessage())
    response.printTraceback()

def instance_timeout_finished(response, instanceid):
    t = TaskInstance.objects.get(pk=instanceid)
    print "- timed out %s (%d) w/code %s" % (t.task.name, instanceid, str(response.code))

def instance_timeout_errored(response, instanceid):
    t = TaskInstance.objects.get(pk=instanceid)
    print "- errored out on timing out %s (%d), reason: %s" % (t.task.name, instanceid, response.getErrorMessage())
    response.printTraceback()


# =========================================================================================
# === actual scheduling methods
# =========================================================================================

def check_schedule():
    # before we do anything, make sure it's not "quiet hours"
    # if it is, do nothing and run this method later
    if isQuietHours():
        global QUIET_START_TIME, QUIET_END_TIME
        # check again in 30 minutes...this is kind of silly, but hey
        print "*** Quiet hours are in effect (%d:00 to %d:00, currently: %s), calling again in 10 minutes..." % (
            QUIET_START_TIME.hour,
            QUIET_END_TIME.hour,
            datetime.datetime.now().strftime("%H:%M")
        )
        reactor.callLater(60*10, check_schedule)
        return
    
    instances = TaskInstance.objects.get_due_tasks()
    
    for instance in instances:
        agent = Agent(reactor)

        # ensure that the user is not halted -- if they are, we can't execute this task :\
        if instance.patient.halted:
            # print "ERROR: Cannot execute task: %s (%d), user is in the halt status" % (sched_task.task.name, sched_task.id)
            continue
        
        print "Executing task: %s (%d)" % (instance.task.name, instance.id)

        payload_dict = {
            'instanceid': instance.id
            }

        payload = urllib.urlencode(payload_dict)

        d = agent.request(
            'POST',
            urlparse.urljoin(settings.SCHEDULER_TARGET_URL, "exec"),
            Headers({
                    "Content-Type": ["application/x-www-form-urlencoded;charset=utf-8"],
                    "Content-Length": [str(len(payload))]
                    }),
            StringProducer(payload))

        d.addCallback(task_finished, instanceid=instance.id)
        d.addErrback(task_errored, instanceid=instance.id)

        # we only want to process one per iteration, so break
        break
        
    # run again in a bit
    reactor.callLater(settings.SCHEDULER_CHECK_INTERVAL, check_schedule)

def check_timeouts():
    # before we do anything, make sure it's not "quiet hours"
    # if it is, do nothing and run this method later
    if isQuietHours():
        global QUIET_START_TIME, QUIET_END_TIME
        # check again in 30 minutes...this is kind of silly, but hey
        print "*** Quiet hours are in effect (%d:00 to %d:00, currently: %s), calling again in 10 minutes..." % (
            QUIET_START_TIME.hour,
            QUIET_END_TIME.hour,
            datetime.datetime.now().strftime("%H:%M")
        )
        reactor.callLater(60*10, check_timeouts)
        return
    
    instances = TaskInstance.objects.get_timedout_tasks()
    
    for instance in instances:
        agent = Agent(reactor)

        # ensure that the user is not halted -- if they are, we can't execute this task :\
        if instance.patient.halted:
            # print "ERROR: Cannot timeout task: %s (%d), user is in the halt status" % (sched_task.task.name, sched_task.id)
            continue
        
        print "Timing out instance: %s (%d)" % (instance.task.name, instance.id)

        payload_dict = {
            'instanceid': instance.id
            }

        payload = urllib.urlencode(payload_dict)

        d = agent.request(
            'POST',
            urlparse.urljoin(settings.SCHEDULER_TARGET_URL, "timeout"),
            Headers({
                    "Content-Type": ["application/x-www-form-urlencoded;charset=utf-8"],
                    "Content-Length": [str(len(payload))]
                    }),
            StringProducer(payload))

        d.addCallback(instance_timeout_finished, instanceid=instance.id)
        d.addErrback(instance_timeout_errored, instanceid=instance.id)
        
    # run again in a bit
    reactor.callLater(settings.SCHEDULER_CHECK_INTERVAL, check_timeouts)


# =========================================================================================
# === twisted entrypoint and django command definitions
# =========================================================================================

def main(port=8080):        
    # construct the resource tree
    root = HTTPCommandBase()
    root.putChild('status', HTTPStatusCommand())

    print "-- Target URL: %s" % (settings.SCHEDULER_TARGET_URL)

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

