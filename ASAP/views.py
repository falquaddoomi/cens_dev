import sys

from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect, HttpResponseNotFound, HttpResponse
from django.core.urlresolvers import reverse
from django.template import RequestContext

from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect

from django.db import IntegrityError, transaction

from taskmanager.models import *
from ASAP.models import *

from datetime import datetime
import parsedatetime.parsedatetime as pdt
import parsedatetime.parsedatetime_consts as pdc

# for parsing argument lists
import json, urllib

from toolbox.basicauth import logged_in_or_basicauth
from taskmanager.framework import utilities

# for configuring the timeouts
# via ASAP_INITIAL_GOAL_DELAY and ASAP_BETWEEN_GOALS_DELAY
import settings

def is_number(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

@csrf_protect
@logged_in_or_basicauth()
@transaction.commit_on_success
def signupform(request):
    if request.method == 'POST': # If the form has been submitted...
        # form = ASAPParticipantForm(request.POST) # A form bound to the POST data
        # if form.is_valid(): # All validation rules pass
        #    subject = form.cleaned_data['subject']

        processed_phone = request.POST['cellphone']

        # ensure that their phone number is in the correct format
        if not processed_phone.startswith("+1"):
            processed_phone = "+1" + processed_phone
            
        # create a Patient for them, too
        try:
            np = Patient(
                address = processed_phone,
                email = request.POST['email'],
                contact_pref = 'sms',
                first_name = request.POST['firstname'],
                last_name = request.POST['lastname']
                )
            np.save()
	except IntegrityError as ex:
            # either their address or email address is already in use...what to do?
            raise
		
        
        # we're assigning all ASAP signups to the ASAP Admin account
        np.clinicians.add(Clinician.objects.get(user=User.objects.get(username='asap_admin')))

        # also create an ASAPParticipant and put all the form data into their instance
        participant = ASAPParticipant(
            patient=np,
            firstname=request.POST['firstname'],
            lastname=request.POST['lastname'],
            cellphone=request.POST['cellphone'],
            email=request.POST['email'],
            age=request.POST['age'] if is_number(request.POST['age']) else None,
            zipcode=request.POST['zipcode'] if is_number(request.POST['zipcode']) else None,
            questionnaire_pref=request.POST['questionnaire_pref'],
            other_diagnosis=request.POST['diagnosis_other_description']
            )
        participant.save()

        # enumerate their diagnoses and associate them with the user
        for d in request.POST.getlist('diagnoses'):
            participant.diagnoses.add(Diagnosis.objects.get(proper_name=d))
        
        # finally, schedule all of their tasks to run at various times...
        start_date = utilities.parsedt(settings.ASAP_INITIAL_GOAL_DELAY)
        
        for goalid in [id for id in request.POST['goals_list_hidden'].split(',')]:
            try:
                goalid = int(goalid)
            except ValueError:
                # probably a 'no goal' entry, just continue
                continue
            
            # get the goal
            goal = ASAPGoal.objects.get(pk=goalid)
            # add to the patient's list of goals
            participant.goals.add(goal)
            # then create a taskinstance for this template
            TaskInstance.objects.create_task(
                patient=np,
                task=goal.tasktemplate.task,
                params=goal.tasktemplate.arguments,
                schedule_date=start_date,
                creator="asap_admin",
                name=goal.tasktemplate.name
                )
            # increment the start date by 2 weeks
            start_date = utilities.parsedt(settings.ASAP_BETWEEN_GOALS_DELAY, start_date)
            
        return HttpResponseRedirect('/ASAP/thanks/') # Redirect after POST
    else:
        form = ASAPParticipantForm() # An unbound form

    return render_to_response('signup.html', {
        'form': form,
        'goal_categories': ASAPGoalCategory.objects.all()
    }, context_instance=RequestContext(request))

def thanks(request):
    return render_to_response('thanks.html', {}, context_instance=RequestContext(request))

# ajax checking routines

@csrf_protect
def checkphone(request):
    result = False
    if 'cellphone' in request.GET:
        result = 'number already in use' if Patient.objects.filter(address__iendswith=request.GET['cellphone']).exists() else True
        
    return HttpResponse(json.dumps(result), mimetype='application/javascript')

@csrf_protect
def checkemail(request):
    result = False
    if 'email' in request.GET:
        result = 'email already in use' if Patient.objects.filter(email=request.GET['email']).exists() else True
        
    return HttpResponse(json.dumps(result), mimetype='application/javascript')

# =============================================
# ASAP has a few models it needs to run, detailed here
# =============================================

from django.forms import ModelForm

class ASAPParticipantForm(ModelForm):
    class Meta:
        model = ASAPParticipant
