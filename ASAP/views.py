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

@csrf_protect
def signupform(request):
    if request.method == 'POST': # If the form has been submitted...
        # form = ASAPParticipantForm(request.POST) # A form bound to the POST data
        # if form.is_valid(): # All validation rules pass
        #    subject = form.cleaned_data['subject']

        # create a Patient for them, too
        np = Patient(
            address = request.POST['cellphone'],
            first_name = request.POST['firstname'],
            last_name = request.POST['lastname']
            )
        np.save()
        
        # we're assigning all ASAP signups to the ASAP Admin account
        np.clinicians.add(Clinician.objects.get(user=User.objects.get(username='asap_admin')))
            
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
