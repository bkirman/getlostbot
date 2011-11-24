from django.views.generic.simple import direct_to_template
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.conf import settings
from django.http import HttpResponse, HttpRequest
from models import User, UserManager
from getlostbot.challenges.models import Challenge
import urllib2
import simplejson
from django.core.validators import email_re
# Create your views here.
def index(request):
    
    foursquare_uri = 'https://foursquare.com/oauth2/authenticate?client_id='+settings.FOURSQUARE_CLIENT+'&response_type=code&redirect_uri='+request.build_absolute_uri('/profile')
        
    return direct_to_template(request,'index.html',{'foursquare_uri':foursquare_uri,'session':request.session.has_key('getlostbotuser')})

def about(request):
    return direct_to_template(request,'about.html')


def profile(request):
    '''
    This is called from foursquare when a user authenticates through them.
    this might include a "code" or an "error" of some sort
    TODO: Handle errors gracefully
    '''
    #if no code/error, then just send them back to the index.
    #if(not request.GET.has_key('code') and not request.GET.has_key('error')):
    #    return redirect('/')
    contact_error = False
    if(request.GET.has_key('code')):
        #they have registered with foursquare, get their access token
        foursquare_verification_uri = 'https://foursquare.com/oauth2/access_token?client_id='+settings.FOURSQUARE_CLIENT+'&client_secret='+settings.FOURSQUARE_SECRET+'&grant_type=authorization_code&redirect_uri='+ request.build_absolute_uri('/profile') + '&code=' + request.GET['code']                           
        try:
            json_data = simplejson.loads(urllib2.urlopen(foursquare_verification_uri).read())
        except Exception, e:
            return direct_to_template(request,'error.html',{'error_title':'Can\'t find user','error_message':'We didn\'t get any data from foursquare - did you log in correctly? Perhaps foursquare is having issues?'})
        #does this user exist?
        try:
            u = User.objects.get(foursquare_auth = json_data['access_token'])
        except User.DoesNotExist:
            #or create them
            u = User.objects.createFromAccessToken(json_data['access_token'])
        request.session['getlostbotuser'] = u.id
    else:#check session
        if not request.session.has_key('getlostbotuser'):
            return direct_to_template(request,'error.html',{'error_title':'Can\'t find user','error_message':'We can\'t find reference to you. Click the robot to go back to the main page and try authenticating again.'})
        try:
            u = User.objects.get(id=request.session['getlostbotuser'])
        except User.DoesNotExist:
            del request.session['getlostbotuser']
            return direct_to_template(request,'error.html',{'error_title':'Can\'t find user','error_message':'Your session has become corrupted. lick the robot to go back to the main page and try authenticating again.'})
        if request.GET.has_key('toggleactive'):
            u.setPushNotifications(not u.active)
            u.save()
        if request.GET.has_key('setbravery'):
            u.bravery = float(request.GET['setbravery'])
            u.save()
        if request.POST.has_key('email'):
            u.email = request.POST['email']
            u.setPushNotifications(True)
            u.save()
            
        if request.POST.has_key('twitter'):
            u.twitter_id = request.POST['twitter'].replace("@","")
            u.setPushNotifications(True)
            u.save()
        if request.POST.has_key('prefer'):
            u.contact_pref = request.POST['prefer']    
            u.save()
        
        if (u.contact_pref=='twitter' and (u.twitter_id==' ' or u.twitter_id=='')) or (u.contact_pref=="email" and not email_re.match(u.email)):
            u.setPushNotifications(False)
            u.save()
            contact_error = True
                
        
    data = {'first_name':u.first_name,
            'active':u.active,
            'prefer_email':u.contact_pref=='email',
            'bravery':u.bravery,
            'twitter':u.twitter_id,
            'email':u.email,
            'contact_error':contact_error,
            'prefer':u.contact_pref
            }
    return direct_to_template(request,'profile.html',data)

#---------
#Below here it is all headless, based on pings from Foursquare
#---------

def force(request):
    '''
    For testing purposes, pass a local user id, and fetch the last checkin and push it to myself. Saves checking in every time I need to test!
    '''
    u = get_object_or_404(User,id=request.GET['user_id'])
    req_uri = 'https://api.foursquare.com/v2/users/self/checkins?limit=1&oauth_token='+u.foursquare_auth
    json_data = simplejson.loads(urllib2.urlopen(req_uri).read())
    check = json_data['response']['checkins']['items'][0]
    check['user'] = {'id':u.foursquare_id} #not included in request otherwise
    r = HttpRequest()
    r.POST['checkin'] = simplejson.dumps(check)
    return checkin(r)
    

def checkin(request):
    '''
    This is the function that should be called by foursquare when a user checks in (see foursquare push API)
    '''
    if not request.POST.has_key("checkin"):
        raise Exception("Attempted checkin with malformed request: "+str(request.POST))
    checkin = simplejson.loads(request.POST['checkin'])
    u = get_object_or_404(User,foursquare_id=checkin['user']['id'])
    
    #if user is inactive, just exit here
    if not u.active:
        return HttpResponse('Inactive User')
    
    #if it is not a regular checkin, then discard
    if not checkin.has_key('venue'):
        return HttpResponse('Only interested in venue checkins')
    
    #is this a completed challenge?
    if Challenge.objects.checkCompletedChallenge(u,checkin['venue']['id']):
        return HttpResponse('This was a completed challenge! no need to make a new one')
    
    #boring venues are now recommended to visit interesting ones :)
    #if it is a boring venue type, then discard
    #boring_categories = ['Apartment Buildings','Other - Buildings','Meeting Room','Factory','Courthouse','Medical','Dentist\'s Office','Doctor\'s Office','Emergency Room','Hospital','Optical Shops','Veterinarians','Corporate / Office','Conference room','Coworking Space','Residence','Home','Travel','Airport']
    #for category in checkin['venue']['categories']:
    #    if category['shortName'] in boring_categories:
    #        return HttpResponse('Yawn, that checkin was a bit dull')
    
    #check recent checkins - have they been here before?
    #get venue history
    req_uri = 'https://api.foursquare.com/v2/users/self/venuehistory?&oauth_token='+u.foursquare_auth
    venue_history = simplejson.loads(urllib2.urlopen(req_uri).read())['response']['venues']['items']
    #based on their bravery, fetch X previous checkins.
    checkin_bravery = int(10 - (u.bravery * 10.0))
    if(checkin_bravery == 0):  #every checkin results in a challenge!
        Challenge.objects.createChallenge(u, checkin['venue'],venue_history)
        return HttpResponse('New Challenge Created!')
        
    req_uri = 'https://api.foursquare.com/v2/users/self/checkins?limit='+str(checkin_bravery)+'&oauth_token='+u.foursquare_auth
    recent_checkins = simplejson.loads(urllib2.urlopen(req_uri).read())['response']['checkins']['items']
    
    #for each recent checkin, check if they have been here before
    #print venue_history
    
    #print "Checking "+str(checkin_bravery)+" past checkins for "+str(u)
    for recent_checkin in recent_checkins:
        #if they haven't been here before, they are leading interesting lives, so we'll let them off
        
        been_here = False
        for venue in venue_history:
            if venue['venue']['id']==recent_checkin['venue']['id']:
                if venue['beenHere'] > 1:
                    been_here = True
                else:#they haven't been here. therefore they are adventurous
                    break
        if not been_here:
            print str(u)+" hasn't been to " + recent_checkin['venue']['name'] + " before, so doesn't need challenging...yet"
            return HttpResponse('User is exploring new places.')
        
    #if we got here, the user has been to every location before
    #make a new challenge based on their current location
    Challenge.objects.createChallenge(u, checkin['venue'],venue_history)
    return HttpResponse('Checkin Analysis Completed')
