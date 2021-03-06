import sys

from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect, HttpResponseNotFound, HttpResponse
from django.core.urlresolvers import reverse
from django.template import RequestContext

from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect

from taskmanager.models import Patient, Process, TaskTemplate, TaskInstance

import datetime, time
import parsedatetime.parsedatetime as pdt
import parsedatetime.parsedatetime_consts as pdc

# for parsing argument lists
import json, urllib

# merges in the variables for this context
# call this right before you render to response
def merge_contextuals(context, request, patientid):
    # update our context if it isn't already
    request.session['context'] = 'patients'

    context.update({
        'context': 'patients',
        'selected_patientid': patientid,
        'current_page': request.path,
        'patients': Patient.objects.all(),
        'contact_pref_choices': Patient.CONTACT_PREF_CHOICES,
        'page_args': ('', '?' + request.META['QUERY_STRING'])[len(request.META['QUERY_STRING'].strip()) > 0]
        })

@csrf_protect
@login_required
def processes(request, patientid):
    field_vars = {
        'section': 'processes',
        'tasktemplates': TaskTemplate.objects.filter(schedulable=True),
        'pending_processes': Process.objects.get_pending_processes().filter(patient__id=patientid).order_by('add_date'),
        'current_processes': Process.objects.get_current_processes().filter(patient__id=patientid).order_by('add_date'),
        'completed_processes': Process.objects.get_completed_processes().filter(patient__id=patientid).order_by('add_date'),
        'selected_patient': Patient.objects.get(pk=patientid)
        }
    
    merge_contextuals(field_vars, request, patientid)
    return render_to_response('dashboard/contexts/patients/processes.html', field_vars, context_instance=RequestContext(request))

@csrf_protect
@login_required
def tasks(request, patientid):
    field_vars = {
        'section': 'tasks',
        'tasktemplates': TaskTemplate.objects.all(),
        'pending_tasks': TaskInstance.objects.get_pending_tasks().filter(patient__id=patientid).order_by('schedule_date'),
        'current_tasks': TaskInstance.objects.get_current_tasks().filter(patient__id=patientid).order_by('add_date'),
        'completed_tasks': TaskInstance.objects.get_completed_tasks().filter(patient__id=patientid).order_by('add_date'),
        }
    
    merge_contextuals(field_vars, request, patientid)
    return render_to_response('dashboard/contexts/patients/tasks.html', field_vars, context_instance=RequestContext(request))

@csrf_protect
@login_required
def history(request, patientid):
    field_vars = {
        'section': 'history',
        'patient': Patient.objects.get(pk=patientid)
        }

    # gather up all the processes for this user initially
    patient_processes = Process.objects.filter(patient__id=patientid)
        
    if 'from' in request.GET:
        # parse at least the from field, and preferably the to field as well
        p = pdt.Calendar()
        from_clean = urllib.unquote(request.GET['from'].replace('+',' '))
        from_time = p.parse(from_clean)
        from_datetime = datetime.datetime.fromtimestamp(time.mktime(from_time[0]))

        field_vars['from'] = from_clean
        if 'custom' in request.GET: field_vars['custom'] = 'true'

        if 'to' not in request.GET or request.GET['to'].strip() == "":
            # use only the from field
            patient_processes = patient_processes.filter(add_date=from_datetime)
        else:
            # attempt to parse to, since it's here
            to_clean = urllib.unquote(request.GET['to'].replace('+',' '))
            to_time = p.parse(to_clean)

            field_vars['to'] = to_clean
            
            if (to_time[1] > 0):
                # it was parseable, make the range reflect this
                to_datetime = datetime.datetime.fromtimestamp(time.mktime(to_time[0]))
                field_vars['processes'] = patient_processes.filter(add_date__gte=from_datetime,add_date__lte=to_datetime)
            else:
                # it was unparseable, just use from
                field_vars['processes'] = patient_processes.filter(add_date__gte=from_datetime)

    # order by add date descending after we have a list
    field_vars['processes'] = patient_processes.order_by('-add_date')
    
    merge_contextuals(field_vars, request, patientid)
    return render_to_response('dashboard/contexts/patients/history.html', field_vars, context_instance=RequestContext(request))

@csrf_protect
@login_required
def messagelog(request, patientid, mode='sms'):
    field_vars = {
        'section': 'messagelog',
        'patient': Patient.objects.get(pk=patientid)
        }

    # import the authoritative rapidsms message log
    from rapidsms.contrib.messagelog.models import Message

    # and grab the patient's identity from the Patient object
    if mode:
        address = field_vars['patient'].get_mode_address(mode)
    else:
        address = field_vars['patient'].address
        
    if 'from' in request.GET:
        # parse at least the from field, and preferably the to field as well
        p = pdt.Calendar()
        from_clean = urllib.unquote(request.GET['from'].replace('+',' '))
        from_time = p.parse(from_clean)
        from_datetime = datetime.datetime.fromtimestamp(time.mktime(from_time[0]))

        field_vars['from'] = from_clean
        if 'custom' in request.GET: field_vars['custom'] = 'true'

        if 'to' not in request.GET or request.GET['to'].strip() == "":
            # use only the from field
            field_vars['messages'] = Message.objects.filter(connection__identity=address,date__gte=from_datetime)
        else:
            # attempt to parse to, since it's here
            to_clean = urllib.unquote(request.GET['to'].replace('+',' '))
            to_time = p.parse(to_clean)

            field_vars['to'] = to_clean
            
            if (to_time[1] > 0):
                # it was parseable, make the range reflect this
                to_datetime = datetime.datetime.fromtimestamp(time.mktime(to_time[0]))
                field_vars['messages'] = Message.objects.filter(connection__identity=address,date__gte=from_datetime,date__lte=to_datetime)
            else:
                # it was unparseable, just use from
                field_vars['messages'] = Message.objects.filter(connection__identity=address,date__gte=from_datetime)
    else:
        field_vars['messages'] = Message.objects.filter(connection__identity=address)

    # order by add date descending after we have a list
    # django lazy query evaluation means that nothing is actually happening here
    # the ordering will occur when the page iterates over 'processes'
    field_vars['messages'] = field_vars['messages'].extra(select={'day': """strftime('%%m/%%d/%%Y', date)"""}).order_by('date')
    
    merge_contextuals(field_vars, request, patientid)
    return render_to_response('dashboard/contexts/patients/messagelog.html', field_vars, context_instance=RequestContext(request))

@csrf_protect
@login_required
def calendar(request, patientid):
    field_vars = {
        'section': 'calendar',
        'patient': Patient.objects.get(pk=patientid),
        'processes': Process.objects.filter(patient__id=patientid),
        'tasks':  TaskInstance.objects.filter(patient__id=patientid)
        }
    
    merge_contextuals(field_vars, request, patientid)
    return render_to_response('dashboard/contexts/patients/calendar.html', field_vars, context_instance=RequestContext(request))

@csrf_protect
@login_required
def default(request):
    # add in the list of users so we can draw the user chooser
    field_vars = {}
    
    # and render the full page
    merge_contextuals(field_vars, request, None)
    return render_to_response('dashboard/contexts/patients/main.html', field_vars, context_instance=RequestContext(request))

# =================================================================
# ==== Forms for adding Users, TaskInstances, Processes
# =================================================================

from django import forms

# the custom prefix used for custom argument fields
CUSTOM_FIELD_PREFIX = "_custom_arg_"

@login_required
def add_patient(request):
    if request.method == 'POST':
        np = Patient(
            address = request.POST['address'],
            email = request.POST['email'],
            handle = request.POST['handle'],
            contact_pref = request.POST['contact_pref'],
            first_name = request.POST['first_name'],
            last_name = request.POST['last_name']
            )
        np.save()
        # add at least the creator to the list of clinicians for this patient
        np.clinicians.add(request.user.get_profile())
        
        # return HttpResponseRedirect(reverse('taskmanager.views.scheduler'))
        # we redirect them to the patient's new process page
        return HttpResponseRedirect('/taskmanager/patients/%d/processes/' % (np.id))

@login_required
def add_scheduled_task(request):
    if request.method == 'POST':
        template = TaskTemplate.objects.get(pk=int(request.POST['task']))

        p = pdt.Calendar()
        parsed_date = p.parse(request.POST['scheduled_date'] + " " + request.POST['scheduled_time'])
        parsed_datetime = datetime.datetime.fromtimestamp(time.mktime(parsed_date[0]))

        TaskInstance.objects.create_task(
            patient = Patient.objects.get(pk=int(request.POST['patient'])),
            task = template.task,
            schedule_date = parsed_datetime,
            params = template.arguments,
            creator = request.user.get_profile(),
            name = template.name)

        # return HttpResponseRedirect(reverse('taskmanager.views.scheduler'))
        return HttpResponseRedirect(request.POST['return_page'])

@login_required
def add_scheduled_process(request):
    global CUSTOM_FIELD_PREFIX
    
    if request.method == 'POST':
        template = TaskTemplate.objects.get(pk=int(request.POST['task']))
        patient = Patient.objects.get(pk=int(request.POST['patient']))

        p = pdt.Calendar()
        command = request.POST['command']

        # check if they chose to run it now or to run it later
        if command == "Schedule":
            parsed_date = p.parse(request.POST['scheduled_date'] + " " + request.POST['scheduled_time'])
            parsed_datetime = datetime.datetime.fromtimestamp(time.mktime(parsed_date[0]))
        elif command == "Run Now":
            parsed_date = p.parse("today now")
            parsed_datetime = datetime.datetime.fromtimestamp(time.mktime(parsed_date[0]))

        # collect the custom arguments into a dict
        custom_args = {}
        for k in request.POST:
            if k.startswith(CUSTOM_FIELD_PREFIX):
                custom_args[k[len(CUSTOM_FIELD_PREFIX):]] = request.POST[k]
        # update the original arguments with the custom ones
        combined_args = json.loads(template.arguments)
        combined_args.update(custom_args)
        # and delete any keys that are still 'templated'
        for k in filter(lambda x: str(combined_args[x]).startswith("?"), combined_args):
            del combined_args[k]

        # create and schedule the process/task
        TaskInstance.objects.create_task(
            patient = patient,
            task = template.task,
            schedule_date = parsed_datetime,
            params = json.dumps(combined_args),
            creator = request.user.get_profile(),
            name = template.name)

        # return HttpResponseRedirect(reverse('taskmanager.views.scheduler'))
        return HttpResponseRedirect(request.POST['return_page'])

# ===================================================================
# === AJAX routine for getting a tasktemplate's custom fields
# ===================================================================

def get_tasktemplate_fields(request, tasktemplateid):
    global CUSTOM_FIELD_PREFIX

    template = TaskTemplate.objects.get(pk=int(tasktemplateid))

    arguments = json.loads(template.arguments)
    response = HttpResponse()

    row_template = "\t<tr><td class=\"label\" style=\"width: 100px;\">%(label)s:</td><td>%(control)s</td></tr>\n"

    response.write("<table class=\"vertical nested_table\">\n")

    # loop through the top-level arguments whose values are prefixed with "?"
    for k in arguments:
        val = arguments[k][1::]
        label = k.replace("_"," ")

        if val == "CheckboxInput":
            response.write(row_template % {'label': label, 'control': '<input type="checkbox" name="%s%s" />' % (CUSTOM_FIELD_PREFIX, k)})
        elif val == "TextInput":
            response.write(row_template % {'label': label, 'control': '<input type="text" name="%s%s" />' % (CUSTOM_FIELD_PREFIX, k)})
        else:
            response.write(row_template % {'label': label, 'control': '%s' % arguments[k]})

    response.write("</table>\n")

    return response
