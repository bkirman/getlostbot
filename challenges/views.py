from django.http import HttpResponse, HttpRequest
from models import Challenge
import simplejson 

def ticker(request):
    '''Return JSON list of recent challenges for the front page'''
    out = []
    for ch in Challenge.objects.filter(complete=False).order_by('-created')[:20]:
        out.append({'u_id':ch.user.foursquare_id,'u_name':unicode(ch.user),'v_name':ch.start_name,'v_id':ch.start_venue_id})
    return HttpResponse(simplejson.dumps(out))
    