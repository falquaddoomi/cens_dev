from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.template import RequestContext

from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect

# generalization of AJAX proxying code from AJAX module
import urllib, urllib2
def proxy(request, url):
    try:
        # attempt to fetch the requested url from the
        # backend, and proxy the response back as-sis
        args = [url]
        code = 200
        
        # if this was a POST, included exactly
        # the same form data in the subrequest
        if request.method == "POST":
            args.append(request.POST.urlencode())
        
        out = urllib2.urlopen(*args)
    # the request was successful, but the server
    # returned an error. as above, proxy it as-is,
    # so we can receive as much debug info as possible
    except urllib2.HTTPError, err:
        out = err.read()
        code = err.code
    
    # the server couldn't be reached. we have no idea
    # why it's down, so just return a useless error
    except urllib2.URLError, err:
        out = "Couldn't reach the backend."
        code = 500
    
    # attempt to fetch the content type of the
    # response we received, or default to text
    try:    ct = out.info()["content-type"]
    except: ct = "text/plain"
    
    # whatever happend during the subrequest, we
    # must return a response to *this* request
    return HttpResponse(out, status=code, content_type=ct)

from taskmanager.framework.utilities import parsedt

@csrf_protect
def pdtest(request):
    fieldvars = {}

    if 'incoming_datetime' in request.POST:
        # attempt to parse it
        fieldvars['incoming_datetime_out'] = request.POST['incoming_datetime']
        fieldvars['parsed_datetime'] = parsedt(request.POST['incoming_datetime'])
    
    return render_to_response('pdtest.html', fieldvars, context_instance=RequestContext(request))
