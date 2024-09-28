import logging
import os

import psycopg2
import psycopg2.extras
import requests
import stripe
from celery.exceptions import MaxRetriesExceededError
from django.conf import settings

from celery import shared_task
from core.models import CustomUser
from payments.paypal_functions import get_paypal_access_token, get_paypal_base_url
from payments.processing import process_event

logger = logging.getLogger("django")


@shared_task(
    bind=True, max_retries=5, default_retry_delay=60
)  # Retry up to 5 times with a 60-second delay
def process_payment_event(self, event_data):
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

    event = None
    if "type" in event_data:  # Stripe event structure
        event = stripe.Event.construct_from(event_data, stripe.api_key)
    else:  # Assume it's a PayPal event structure
        event = event_data

    conn = None
    cur = None
    try:
        conn = psycopg2.connect(
            dbname=settings.DATABASES["default"]["NAME"],
            user=settings.DATABASES["default"]["USER"],
            password=settings.DATABASES["default"]["PASSWORD"],
            host=settings.DATABASES["default"]["HOST"],
            port=settings.DATABASES["default"]["PORT"],
        )
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Attempt to process the event
        process_event(event, cur)

    except Exception as e:
        logger.error(
            f"Error processing event {event.get('id', 'unknown id')}: {e}",
            exc_info=True,
        )

        # Retry the task if it fails
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error(
                f"Max retries exceeded for event {event.get('id', 'unknown id')}"
            )

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def cancel_paypal_subscription_task(self, subscription_id):
    """Send a request to PayPal to cancel a subscription."""
    try:
        access_token = (
            get_paypal_access_token()
        )  # Ensure this function is properly implemented
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        data = '{ "reason": "Not satisfied with the service" }'
        base_url = get_paypal_base_url()
        response = requests.post(
            f"{base_url}/v1/billing/subscriptions/{subscription_id}/cancel",
            headers=headers,
            data=data,
        )

        if response.status_code in [200, 204]:
            user = CustomUser.objects.get(paypal_subscription_id=subscription_id)
            user.active = False
            user.paypal_subscription_id = None
            user.save()
            logger.info(f"Successfully cancelled PayPal subscription {subscription_id}")
        else:
            logger.error(
                f"Failed to cancel subscription {subscription_id}: {response.text}"
            )
            # Retry the task if the cancellation fails
            self.retry(
                exc=Exception(
                    f"Failed to cancel subscription {subscription_id}: {response.text}"
                )
            )

    except requests.exceptions.RequestException as e:
        # Retry the task in case of a network-related error
        logger.error(
            f"Network error occurred while cancelling subscription {subscription_id}: {str(e)}"
        )
        try:
            self.retry(exc=e)
        except MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for subscription {subscription_id}")

    except Exception as e:
        logger.error(
            f"An error occurred while cancelling subscription {subscription_id}: {str(e)}"
        )
        try:
            self.retry(exc=e)
        except MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for subscription {subscription_id}")
