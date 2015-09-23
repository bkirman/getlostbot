import os
import sys
sys.path.append('/var/django_apps/getlostbot')
os.environ['DJANGO_SETTINGS_MODULE'] = 'getlostbot.settings'
os.environ['PYTHON_EGG_CACHE'] = '/var/django_apps/.python_egg_cache'
from django.core.wsgi import get_wsgi_application
#application = django.core.handlers.wsgi.WSGIHandler()
application = get_wsgi_application()