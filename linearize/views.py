from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.template import RequestContext

@csrf_protect
def index(request):
    return render_to_response('index.html', {}, context_instance=RequestContext(request))

@csrf_protect
def formtest(request):
    context = {
        'request': request
        }

    if request.method == "POST":
        context['diagnoses'] = request.POST.getlist('diagnoses')
        
    return render_to_response('formtest.html', context, context_instance=RequestContext(request))
