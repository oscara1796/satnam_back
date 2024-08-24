from celery import shared_task
import logging
import stripe
from .send_email_functions import *
from django.conf import settings
from datetime import datetime, timezone
import psycopg2
import psycopg2.extras
from payments.processing import process_event
import os

logger = logging.getLogger("django")

@shared_task(bind=True, max_retries=5, default_retry_delay=60)  # Retry up to 5 times with a 60-second delay
def process_payment_event(self, event_data):
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
    event = stripe.Event.construct_from(event_data, stripe.api_key)

    conn = None
    cur = None
    try:
        conn = psycopg2.connect(
            dbname=settings.DATABASES['default']['NAME'],
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            host=settings.DATABASES['default']['HOST'],
            port=settings.DATABASES['default']['PORT']
        )
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)  

        # Attempt to process the event
        process_event(event, cur)

    except Exception as e:
        logger.error(f"Error processing event {event.get('id', 'unknown id')}: {e}", exc_info=True)
        
        # Retry the task if it fails
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for event {event.get('id', 'unknown id')}")
    
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()