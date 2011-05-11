import sys

from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect, HttpResponseNotFound, HttpResponse
from django.core.urlresolvers import reverse
from django.template import RequestContext

from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect

from taskmanager.models import *
from ASAP.models import *

from datetime import datetime
import parsedatetime.parsedatetime as pdt
import parsedatetime.parsedatetime_consts as pdc

# for parsing argument lists
import json, urllib

from toolbox.basicauth import logged_in_or_basicauth
from taskmanager.framework import utilities

@csrf_protect
@logged_in_or_basicauth()
def signupform(request):
    if request.method == 'POST': # If the form has been submitted...
        # form = ASAPParticipantForm(request.POST) # A form bound to the POST data
        # if form.is_valid(): # All validation rules pass
        #    subject = form.cleaned_data['subject']

        # create a Patient for them, too
        np = Patient(
            address = "+1" + request.POST['cellphone'],
            first_name = request.POST['firstname'],
            last_name = request.POST['lastname']
            )
        np.save()
        
        # we're assigning all ASAP signups to the ASAP Admin account
        np.clinicians.add(Clinician.objects.get(user=User.objects.get(username='asap_admin')))

        # also create an ASAPParticipant and put all the form data into their instance
        participant = ASAPParticipant(
            patient=np,
            firstname=request.POST['firstname'],
            lastname=request.POST['lastname'],
            cellphone=request.POST['cellphone'],
            email=request.POST['email'],
            age=request.POST['age'],
            zipcode=request.POST['zipcode'],
            questionnaire_pref=request.POST['questionnaire_pref']
            )
        participant.save()
        
        # finally, schedule all of their tasks to run at various times...
        start_date = utilities.parsedt("in 10 minutes")
        
        for goal in [int(id) for id in request.POST['goals_list_hidden'].split(',')]:
            # look up the template first
            template = TaskTemplate.objects.get(pk=goal)
            # then create a taskinstance for this template
            TaskInstance.objects.create_task(
                patient=np,
                task=template.task,
                params=template.arguments,
                schedule_date=start_date,
                creator="asap_admin",
                name=template.name
                )
            # increment the start date by 2 weeks
            start_date = utilities.parsedt("in 30 minutes", start_date)
            
        return HttpResponseRedirect('/ASAP/thanks/') # Redirect after POST
    else:
        form = ASAPParticipantForm() # An unbound form

    return render_to_response('signup.html', {
        'form': form,
        'goal_categories': ASAPGoalCategory.objects.all()
    }, context_instance=RequestContext(request))

def thanks(request):
    return render_to_response('thanks.html', {}, context_instance=RequestContext(request))

# =============================================
# ASAP has a few models it needs to run, detailed here
# =============================================

from django.forms import ModelForm

class ASAPParticipantForm(ModelForm):
    class Meta:
        model = ASAPParticipant
