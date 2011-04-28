import json

from django.shortcuts import render_to_response
from django.views.decorators.csrf import csrf_exempt

from models import IncomingSMS

@csrf_exempt
def incoming(request):
    # log the incoming data somehow
    logger = IncomingSMS(
        get_data=json.dumps(request.GET),
        post_data=json.dumps(request.POST),
        headers=str(request.META)
    )
    logger.save()
    
    return render_to_response('incoming.html', {})
