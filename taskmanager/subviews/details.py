import sys

from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect, HttpResponseNotFound, HttpResponse
from django.core.urlresolvers import reverse
from django.template import RequestContext
from taskmanager.models import *
from django.views.decorators.csrf import csrf_protect

from datetime import datetime

@csrf_protect
def process_details(request, processid):
    context = {
        'process': Process.objects.get(pk=processid)
    }
    return render_to_response('dashboard/details/process.html', context, context_instance=RequestContext(request))

def process_command(request, processid):
    if request.method == "POST" and request.is_ajax():
        command = request.POST.get('command')
        process = Process.objects.get(pk=processid)

        # dispatch on different commands
        if command == "deactivate":
            # remove all pending tasks
            process.get_pending_tasks().delete()
            # time out all running sessions
            process.get_current_sessions().update(timeout_date=datetime.now())
            return HttpResponse("REQUIRES_REFRESH")
        elif command == "remove":
            process.delete()
            return HttpResponse("REQUIRES_REFRESH")

        return HttpResponse("CMD_NOT_FOUND")

    # and render the default view
    return process_details(request, processid)

@csrf_protect
def taskinstance_details(request, instanceid):
    context = {
        'instance': TaskInstance.objects.get(pk=instanceid)
    }
    return render_to_response('dashboard/details/taskinstance.html', context, context_instance=RequestContext(request))

def taskinstance_command(request, instanceid):
    if request.method == "POST" and request.is_ajax():
        command = request.POST.get('command')
        instance = TaskInstance.objects.get(pk=instanceid)

        # dispatch on different commands
        if command == "remove":
            instance.delete()
            return HttpResponse("REQUIRES_REFRESH")
        
        # dispatch on different commands
        if command == "timeout":
            instance.timeout_date = datetime.now()
            instance.save()
            return HttpResponse("REQUIRES_REFRESH")

        return HttpResponse("CMD_NOT_FOUND")

    # and render the default view
    return taskinstance_details(request, instanceid)

@csrf_protect
def patient_details(request, patientid):
    context = {
        'patient': Patient.objects.get(pk=patientid)
    }
    return render_to_response('dashboard/details/patient.html', context, context_instance=RequestContext(request))

def patient_command(request, patientid):
    if request.method == "POST" and request.is_ajax():
        command = request.POST.get('command')
        patient = Patient.objects.get(pk=patientid)

        # dispatch on different commands
        if command == "halt":
            # set patient's status to halted
            patient.halted = True
            patient.save()
            return HttpResponse("REQUIRES_REFRESH")
        elif command == "unhalt":
            # set patient's status to un-halted
            patient.halted = False
            patient.save()
            return HttpResponse("REQUIRES_REFRESH")

        return HttpResponse("CMD_NOT_FOUND")

    # and render the default view
    return process_details(request, processid)
