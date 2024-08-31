"""
https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html
"""

import os

from django.conf import settings

from celery import Celery

# this code copied from manage.py
# set the default Django settings module for the 'celery' app.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "satnam.settings")

# you can change the name here
app = Celery("satnam_celery_app")

# read config from Django settings, the CELERY namespace would make celery
# config keys has `CELERY` prefix
app.config_from_object("django.conf:settings", namespace="CELERY")

# discover and load tasks.py from from all registered Django apps
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


@app.task
def divide(x, y):
    import time

    time.sleep(5)
    return x / y
