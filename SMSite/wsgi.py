"""
WSGI config for SMSite project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/howto/deployment/wsgi/
"""

import os
from threading import Timer

from django.core.wsgi import get_wsgi_application
from mainsite.bg_tasks import start_mon, tx_mon, bg_mon, rs, mk_sync

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SMSite.settings')

## delay the start for a second
Timer(1, start_mon, args=(tx_mon, bg_mon, rs, mk_sync)).start()

application = get_wsgi_application()


