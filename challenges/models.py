from django.db import models

import urllib2
import simplejson
from django.conf import settings
import datetime
import os
from getlostbot.users.models import User

class ChallengeManager(models.Manager):
    
    def createChallenge(self,user,venue,venue_history):
        '''
        Generate a challenge for a given user, based on their current venue and their bravery.
        Finally, ping the user with the message that their challenge has been made
        '''
        #first off, check we can actually direct the person from their venue. It needs an address
        if not ((venue['location'].has_key('postalCode') and venue['location'].has_key('address')) or venue['location'].has_key('lat')):
            print "Can't generate a challenge for "+str(user)+" because venue "+venue['name']+ " doesn't seem to have an address or location"
            return False
        #get venues similar to the one sent
        req_uri = 'https://api.foursquare.com/v2/venues/'+venue['id']+'/similar?limit=1&oauth_token='+user.foursquare_auth
        json_data = simplejson.loads(urllib2.urlopen(req_uri).read())
        
        found_new = False
        new_venue = None
        for suggestion in json_data['response']['similarVenues']['items']:
            #if they haven't been here before, we'll send them there.
            been_here = False
            for history in venue_history:
                if history['venue']['id'] == suggestion['id']:
                    been_here = True
                    print suggestion['name']+ " is not a suitable venue for "+str(user)+", they have been here before"
                    break
                #ALSO, if the new place appears to be in the same building, then skip it (hard to give directions!)
                if history['venue']['location'].has_key('postalCode') and suggestion['location'].has_key('postalCode'):
                    if history['venue']['location']['postalCode'] == suggestion['location']['postalCode']:
                        been_here = True
                        print suggestion['name']+ " is not a suitable venue for "+str(user)+", they appear to be in the same building(?)"
                        break
                #ALSO, it must have some kind of address
                if not ((history['venue']['location'].has_key('postalCode') and history['venue']['location'].has_key('address')) or history['venue']['location'].has_key('lat')):
                    been_here = True
                    print suggestion['name']+ " is not a suitable venue for "+str(user)+", the address is invalid"
                    break
            if not been_here:
                new_venue = suggestion
                break
            
        if new_venue == None:
            print "Couldn't find a suggestion for venue "+ venue['name']+ " for "+str(user)+ " (probably they have already been to all the possible places)"
            return False
        #begin challenge
        print "Creating Challenge for " + str(user)+ " to go from "+venue['name']+ " to " + new_venue['name']
        c = Challenge()
        c.user = user
        c.start_venue_id = venue['id']
        c.start_name = venue['name']
        if venue['location'].has_key('lat'):
            c.start_address = str(venue['location']['lat'])+","+str(venue['location']['lng'])
        else:
            c.start_address = str(venue['location']['address'])+", "+ str(venue['location']['postalCode'])
        c.end_venue_id = new_venue['id']
        c.end_name = new_venue['name']
        if new_venue['location'].has_key('lat'):
            c.end_address = str(new_venue['location']['lat'])+","+str(new_venue['location']['lng'])
        else:
            c.end_address = str(new_venue['location']['address'])+", "+ str(new_venue['location']['postalCode'])
        #print c
        c.save()
        user.notifyOfChallenge(c)
        return True
    
    def checkCompletedChallenge(self,u,venue_id):
        finished = False
        for c in self.filter(end_venue_id=venue_id).filter(user=u).all():
            c.setFinished()
            finished=True
        return finished
    
# Create your models here.
class Challenge(models.Model):
    user = models.ForeignKey(User,related_name="challenges")
    complete = models.BooleanField(default=False)
    start_venue_id= models.CharField(max_length=50, blank=False,unique=False,null=False)
    start_address = models.CharField(max_length=100, blank=False,unique=False,null=False)
    start_name = models.CharField(max_length=100, blank=False,unique=False,null=False)
    end_venue_id  = models.CharField(max_length=50, blank=False,unique=False,null=False)
    end_address   = models.CharField(max_length=100, blank=False,unique=False,null=False)
    end_name = models.CharField(max_length=100, blank=False,unique=False,null=False)
    created = models.DateTimeField(auto_now_add=True)
    finished = models.DateTimeField(null=True,default=None)

    objects = ChallengeManager()
    def __unicode__(self):
        return "Challenge for "+str(self.user)+" to go from venue "+self.start_name+" to "+self.end_name
    
    def setFinished(self):
        self.finished = datetime.datetime.now()
        self.complete = True
        message = "Well done! You checked into "+self.end_name+" and completed a challenge!"
        if self.user.contact_pref=='email':
            self.user.sendMail(message)
        else:
            self.user.sendTweet(message)
        
        self.save()
        return
