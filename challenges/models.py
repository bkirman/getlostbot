from django.db import models

import urllib2
import simplejson
from django.conf import settings
import datetime
import os
from getlostbot.users.models import User
import logging
import random

class ChallengeManager(models.Manager):
    
    def getSimilarVenue(self,user,venue,venue_history):
        '''find a suitable venue to send this user, based on nearby similar venues they have never visited'''
        logging.debug("finding similar venues to "+venue['name']+" for "+unicode(user))
        #get venues similar to the one sent
        req_uri = 'https://api.foursquare.com/v2/venues/'+venue['id']+'/similar?limit=1&oauth_token='+user.foursquare_auth
        json_data = simplejson.loads(urllib2.urlopen(req_uri).read())
        similar_venues = json_data['response']['similarVenues']['items']
        random.shuffle(similar_venues)#randomise so we don't get same one first each time
        
        new_venue = None
        for suggestion in similar_venues:
            #if they haven't been here before, we'll send them there.
            been_here = False
            for history in venue_history:
                if history['venue']['id'] == suggestion['id']:
                    been_here = True
                    logging.debug( suggestion['name']+ " is not a suitable venue for "+unicode(user)+", they have been here before")
                    break
            #ALSO, if the new place appears to be in the same building, then skip it (hard to give directions!)
            if venue['location'].has_key('lat') and suggestion['location'].has_key('lat'):
                if venue['location']['lat'] == suggestion['location']['lat'] and venue['location']['lng'] == suggestion['location']['lng'] :
                    been_here = True
                    logging.debug( suggestion['name']+ " is not a suitable venue for "+unicode(user)+", they appear to be in the same building(?)")
                    continue
            #ALSO, it must have some kind of address
            if not suggestion['location'].has_key('lat'):
                been_here = True
                logging.debug( suggestion['name']+ " is not a suitable venue for "+unicode(user)+", the address is invalid")
                continue
            
            if not been_here:
                return suggestion
                
        return None#none found :(
    
    def getRecommendedVenue(self,user,venue):
        '''
        find a suitable venue based on the 4sq recommendation engine. Note that this doesn't care what the current venue is, so suggestions are more varied (and apparently frequently restaurants)
        '''
        #get venues similar to the one sent
        logging.debug( "finding recommended venues near "+venue['name']+" for "+unicode(user))
        req_uri = 'https://api.foursquare.com/v2/venues/explore?ll='+str(venue['location']['lat'])+','+str(venue['location']['lng'])+'&novelty=new&limit=10&oauth_token='+user.foursquare_auth
        #print req_uri
        json_data = simplejson.loads(urllib2.urlopen(req_uri).read())
        possible_venues = json_data['response']['groups'][0]['items']
        random.shuffle(possible_venues)
        try:
            
            new_venue = possible_venues[0]['venue']
            #print "got data "+unicode(new_venue['location'])
            if not new_venue['location'].has_key('lat'):
                return None
            
        except Exception, e:
            logging.debug( "Couldn't find any suitable venues :( "+str(e))
            return None
        return new_venue
        
    
    def createChallenge(self,user,venue,venue_history):
        '''
        Generate a challenge for a given user, based on their current venue and their bravery.
        Finally, ping the user with the message that their challenge has been made
        '''
        #first off, check we can actually direct the person from their venue. It needs an address
        if not venue['location'].has_key('lat'):
            logging.debug( "Can't generate a challenge for "+unicode(user)+" because venue "+venue['name']+ " doesn't seem to have an address or location")
            return False
        
        new_venue = self.getSimilarVenue(user, venue, venue_history)
        if new_venue == None:
            new_venue = self.getRecommendedVenue(user, venue)
            
        if new_venue == None:
            logging.debug( "Couldn't find a suggestion for venue "+ venue['name']+ " for "+unicode(user)+ " (probably they have already been to all the possible places)")
            return False
        #begin challenge
        logging.debug( "Creating Challenge for " + unicode(user)+ " to go from "+venue['name']+ " to " + new_venue['name'])
        c = Challenge()
        c.user = user
        c.start_venue_id = venue['id']
        c.start_name = venue['name']
        if venue['location'].has_key('lat'):
            c.start_address = str(venue['location']['lat'])+","+str(venue['location']['lng'])
        else:
            c.start_address = unicode(venue['location']['address'])+", "+ unicode(venue['location']['postalCode'])
        c.end_venue_id = new_venue['id']
        c.end_name = new_venue['name']
        if new_venue['location'].has_key('lat'):
            c.end_address = str(new_venue['location']['lat'])+","+str(new_venue['location']['lng'])
        else:
            c.end_address = unicode(new_venue['location']['address'])+", "+ unicode(new_venue['location']['postalCode'])
        #print c
        c.save()
        user.notifyOfChallenge(c)
        return True
    
    def checkCompletedChallenge(self,u,venue_id):
        finished = False
        for c in self.filter(end_venue_id=venue_id).filter(user=u).filter(finished=None).all():
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
        return "Challenge for "+unicode(self.user)+" to go from venue "+self.start_name+" to "+self.end_name
    
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
