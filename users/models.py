from django.db import models
import urllib2
import urllib
import simplejson
from django.conf import settings
import sys 
import tweepy
import logging
import os
from django.core.mail import send_mail

class UserManager(models.Manager):
    def createFromAccessToken(self,access_token):
        #get details of this user from foursquare and create new object
        #TODO: make sure they dont already exist
        req_uri = "https://api.foursquare.com/v2/users/self?v=20131016&oauth_token="+access_token
        json_data = simplejson.loads(urllib2.urlopen(req_uri).read())
        
        #print json_data
        #print json_data['response']
        user_obj = json_data['response']['user']
        
        u = User()
        u.foursquare_id = user_obj['id']
        if user_obj.has_key('firstName'):
            u.first_name = user_obj['firstName']
        else:
            u.first_name = ""
        if user_obj.has_key('lastName'):
            u.last_name = user_obj['lastName']
        else:
            u.last_name = ""
        
        u.foursquare_auth = access_token
        
        if user_obj['contact'].has_key('email'):
            u.email = user_obj['contact']['email']
        if user_obj['contact'].has_key('twitter'):
            u.twitter_id = user_obj['contact']['twitter']
            if(u.twitter_id==''):
                u.contact_pref="email"
        else:
            u.contact_pref = "email"
        u.save()
        if u.email == None and u.twitter_id == None:# no way of contacting this user
            u.active= False
        else:
            u.active = True#everything seemed to happen ok, lets make the user active
            u.setPushNotifications(True)
        u.save()
        msg = "Welcome to GetLostBot! You can change any settings at http://www.getlostbot.com/profile"
        if u.contact_pref=="twitter":
            u.sendTweet(msg)
        else:
            u.sendMail(msg)
        return u
# Create your models here.
class User(models.Model):
    first_name = models.CharField(max_length=100, blank=True,unique=False,null=False)
    last_name = models.CharField(max_length=100, blank=True,unique=False,null=False)
    foursquare_id = models.CharField(max_length=100, blank=False,unique=True,null=False)
    foursquare_auth = models.CharField(max_length=100, blank=False,unique=False,null=False)
    twitter_id = models.CharField(max_length=50,blank=True,null=False)
    email = models.EmailField(blank=True)
    contact_pref = models.CharField(max_length=10,default="twitter")
    created = models.DateTimeField(auto_now_add=True)
    bravery = models.FloatField(default=0.5)
    active = models.BooleanField(default=False)
    
    class Meta:
        app_label='users'
        
    #awards = models.ManyToManyField('awards.Award',through='awards.PlayerAward',related_name="players")
    objects = UserManager()
    def __unicode__(self):
        if len(self.last_name) > 0:
            return self.first_name + " " + unicode(self.last_name[0])
        else:
            return self.first_name
    
    def sendTweet(self, message):
        if self.twitter_id == None or self.twitter_id == '':#they don't have twitter...
            return self.sendMail(message)
        auth = tweepy.OAuthHandler(settings.TWITTER_CONSUMER_KEY,settings.TWITTER_CONSUMER_SECRET)
        auth.set_access_token(settings.TWITTER_AUTH_KEY, settings.TWITTER_AUTH_SECRET)
        api = tweepy.API(auth)
        api.update_status('@'+self.twitter_id+' '+unicode(message))
        
    def sendMail(self,message):
        send_mail('Challenge from GetLostBot!',message,'bkirman@lincoln.ac.uk',[self.email])
        return

        
    def setPushNotifications(self,set):
        '''
        Sets whether GetLostBot will receive push notifications from foursquare for this user.
        '''
        #do X
        self.active = set
        self.save()
        return
    
    def notifyOfChallenge(self,c):
        '''
        Send user a message, as appropriate, notifying of a new challenge.
        '''
        if not self.active:#this never should have happened.
            return
        #generate Google Maps link
        map_url = "http://maps.google.co.uk/maps?saddr="+c.start_address+"&daddr="+c.end_address+"&dirflg=w"
        #print "map: "+gmaps_url
        message = 'You have been here before. Let\'s have an adventure!'
        
        if self.contact_pref=='email':
            self.sendMail(message+ " \n"+map_url)
        else:
            bitly_url = "https://api-ssl.bitly.com/v3/shorten?access_token="+settings.BITLY_AUTH+"&longUrl="+urllib.quote(str(map_url))
            map_url = simplejson.loads(urllib2.urlopen(bitly_url).read())['data']['url']
            logging.debug("Bitly link: "+map_url)
            self.sendTweet(message+" "+map_url)

class Checkin(models.Model):
    '''
    Container class to store a queue of raw checkin pings received from foursquare.
    '''
    data = models.TextField(default='',blank=True,unique=False)
    resolved = models.BooleanField(default=False)
    created = models.DateTimeField()
    objects = models.Manager()
    class Meta:
        app_label='users'
    