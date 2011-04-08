import sys

from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect, HttpResponseNotFound, HttpResponse
from django.core.urlresolvers import reverse
from django.template import RequestContext

from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect

from taskmanager.models import *

from datetime import datetime
import parsedatetime.parsedatetime as pdt
import parsedatetime.parsedatetime_consts as pdc

# for parsing argument lists
import json, urllib

from django.db import models
from django.forms import ModelForm

class ASAPParticipant(models.Model):
    name = models.CharField(max_length=100)
    birth_date = models.DateField(blank=True, null=True)

    def __unicode__(self):
        return self.name

class ASAPForm(ModelForm):
    class Meta:
        model = ASAPParticipant

@csrf_protect
def signupform(request):
    if request.method == 'POST': # If the form has been submitted...
        form = ASAPForm(request.POST) # A form bound to the POST data
        if form.is_valid(): # All validation rules pass
            name = form.cleaned_data['name']
            birth_date = form.cleaned_data['birth_date']
            
            return HttpResponseRedirect('/ASAP/thanks/') # Redirect after POST
    else:
        form = ContactForm() # An unbound form

    return render_to_response('ASAP/signup.html', {
            'form': form,
        }, context_instance=RequestContext(request))
