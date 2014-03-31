from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    (r'^$','users.views.index'),
    (r'^profile/?$','users.views.profile'),
    (r'^about/?$','users.views.about'),
    (r'^faq/?$','users.views.faq'),
    (r'^queue/?$','users.views.queue'),
    (r'^force','users.views.force'),
    (r'^checkin','users.views.checkin'),
    (r'^ticker/?$','challenges.views.ticker'),
    (r'^static/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': '/Users/bkirman/Documents/Projects/GetLostBot/getlostbot/public/'}),
    # Example:
    # (r'^getlost/', include('getlost.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # (r'^admin/', include(admin.site.urls)),
)
