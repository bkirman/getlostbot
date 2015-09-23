import os
import sys
sys.path.append('/var/django_apps/getlostbot')
os.environ['DJANGO_SETTINGS_MODULE'] = 'getlostbot.settings'
os.environ['PYTHON_EGG_CACHE'] = '/var/django_apps/.python_egg_cache'
import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()
