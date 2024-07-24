import requests
from requests.auth import HTTPBasicAuth
import json
import os
from dotenv import load_dotenv

from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from apscheduler.jobstores.base import JobLookupError
from django_apscheduler.models import DjangoJobExecution
from payments.paypal_scheduler import SchedulerSingleton
from datetime import datetime
import pytz

import logging

from core.models import CustomUser

import paypalrestsdk
from paypalrestsdk.notifications import WebhookEvent
from django.conf import settings



# This assumes you've configured the PayPal SDK as shown in settings.py
paypalrestsdk.configure({
    "mode": "sandbox",  # or "live" based on your environment
    "client_id": settings.PAYPAL_CLIENT_ID,
    "client_secret": settings.PAYPAL_CLIENT_SECRET
})


logger = logging.getLogger("payments")


load_dotenv("../.env.dev")


def get_paypal_access_token():
    url = "https://api-m.sandbox.paypal.com/v1/oauth2/token"
    headers = {
        "Accept": "application/json",
        "Accept-Language": "en_US",
    }
    data = {
        "grant_type": "client_credentials"
    }
    response = requests.post(url, headers=headers, data=data, auth=HTTPBasicAuth(os.environ.get("PAYPAL_CLIENT_ID"), os.environ.get("PAYPAL_CLIENT_SECRET")))
    
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        raise Exception(f"Failed to get access token: {response.status_code}, {response.text}")


def get_paypal_subscription(subscription_id):
    """
    Retrieves details for a single PayPal subscription using the PayPal REST API.
    
    Args:
        subscription_id (str): The unique identifier for the PayPal subscription.

    Returns:
        dict: The JSON response from PayPal if successful, or None if an error occurs.
    """
    try:
        access_token = get_paypal_access_token()
        url = f"https://api-m.sandbox.paypal.com/v1/billing/subscriptions/{subscription_id}"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Will raise an HTTPError for bad responses
        return response.json()  # Return the parsed JSON data from the response
    except requests.exceptions.HTTPError as e:
        # Handle HTTP errors (e.g., response code 404, 401, etc.)
        logger.info(f"HTTPError: {str(e)}")
    except requests.exceptions.RequestException as e:
        # Handle other possible errors (e.g., network issues)
        logger.info(f"RequestException: {str(e)}")
    return None


def get_all_paypal_products():
    """Retrieve all PayPal products."""
    access_token = get_paypal_access_token()
    url = "https://api-m.sandbox.paypal.com/v1/catalogs/products"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to retrieve PayPal products: {response.status_code}, {response.text}")



def schedule_subscription_deletion(subscription_id, billing_cycle_end):
    """Schedule the deletion of the PayPal subscription using django-apscheduler."""
    scheduler = SchedulerSingleton.get_instance()

    # Convert the billing cycle end time to a datetime object
    end_time = datetime.strptime(billing_cycle_end, '%Y-%m-%dT%H:%M:%SZ')
    end_time = pytz.UTC.localize(end_time)  # Ensure timezone awareness

    # Schedule the job
    scheduler.add_job(
        func=cancel_paypal_subscription,  # This should be the function that deletes the subscription
        trigger='date',
        run_date=end_time,
        args=[subscription_id],
        id=f'delete_subscription_{subscription_id}',
        replace_existing=True,
    )
    logger.info(f"Deletion of PayPal subscription {subscription_id} scheduled for {end_time.isoformat()}")


def remove_scheduled_deletion(subscription_id):
    """Remove scheduled deletion task for a subscription."""
    scheduler = SchedulerSingleton.get_instance()
    job_id = f'delete_subscription_{subscription_id}'
    try:
        scheduler.remove_job(job_id)
        logger.info(f"Removed scheduled deletion for subscription {subscription_id}")
    except JobLookupError:
        logger.info(f"No scheduled deletion found for subscription {subscription_id}")


def cancel_paypal_subscription(subscription_id):
    """Send a request to PayPal to cancel a subscription."""
    access_token = get_paypal_access_token()  # Ensure this function is properly implemented
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    data = '{ "reason": "Not satisfied with the service" }'
    response = requests.post(f'https://api-m.sandbox.paypal.com/v1/billing/subscriptions/{subscription_id}/cancel', headers=headers, data=data)

    if response.status_code in [200, 204]:

        user = CustomUser.objects.get(paypal_subscription_id=subscription_id)
        user.active = False
        user.paypal_subscription_id = None
        user.save()
        self.stdout.write(self.style.SUCCESS(f'Successfully cancelled PayPal subscription {subscription_id}'))
    else:
        self.stdout.write(self.style.ERROR(f'Failed to cancel subscription {subscription_id}: {response.text}'))


def verify_paypal_webhook_signature(request):
    """
    Verifies the PayPal webhook signature using request data.

    Args:
    - request: Django request object containing the webhook data and headers.

    Returns:
    - bool: True if the signature is verified, False otherwise.
    """
    payload = request.body.decode('utf-8')
    transmission_id = request.headers.get('Paypal-Transmission-Id')
    timestamp = request.headers.get('Paypal-Transmission-Time')
    signature = request.headers.get('Paypal-Transmission-Sig')
    cert_url = request.headers.get('Paypal-Cert-Url')
    auth_algo = request.headers.get('Paypal-Auth-Algo')
    webhook_id = settings.PAYPAL_WEBHOOK_ID  # Replace with your actual webhook ID

    try:
        response = paypalrestsdk.WebhookEvent.verify(
            transmission_id=transmission_id,
            timestamp=timestamp,
            webhook_id=webhook_id,
            event_body=payload,
            cert_url=cert_url,
            actual_sig=signature,
            auth_algo=auth_algo
        )
        return response
    except Exception as e:
        print("Error verifying PayPal webhook signature: ", e)
        return False
