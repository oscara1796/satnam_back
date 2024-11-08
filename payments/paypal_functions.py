import logging
import os
# from payments.paypal_scheduler import SchedulerSingleton
from datetime import datetime

import paypalrestsdk
import pytz
import requests
from celery.result import AsyncResult
from django.conf import settings
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

# This assumes you've configured the PayPal SDK as shown in settings.py
paypalrestsdk.configure(
    {
        "mode": "sandbox" if os.environ.get("DEBUG", False) == "1" else "live",
        "client_id": settings.PAYPAL_CLIENT_ID,
        "client_secret": settings.PAYPAL_CLIENT_SECRET,
    }
)


logger = logging.getLogger("payments")


load_dotenv("../.env.dev")


def get_paypal_base_url():
    # Interpret "DEBUG=1" as True, otherwise fallback to False
    is_debug_mode = os.environ.get("DEBUG", False) == "1"
    debug_url = "https://api-m.sandbox.paypal.com"
    live_url = "https://api-m.paypal.com"

    # Choose the URL based on the debug mode
    paypal_base_url = debug_url if is_debug_mode else live_url

    return paypal_base_url


def get_paypal_access_token():
    base_url = get_paypal_base_url()
    url = f"{base_url}/v1/oauth2/token"
    headers = {
        "Accept": "application/json",
        "Accept-Language": "en_US",
    }
    data = {"grant_type": "client_credentials"}

    response = requests.post(
        url,
        headers=headers,
        data=data,
        auth=HTTPBasicAuth(
            os.environ.get("PAYPAL_CLIENT_ID"), os.environ.get("PAYPAL_CLIENT_SECRET")
        ),
    )

    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(
            f"Failed to get access token: {response.status_code}, {response.text}"
        )


def get_paypal_subscription(subscription_id):
    """
    Retrieves details for a single PayPal subscription using the PayPal REST API.

    Args:
        subscription_id (str): The unique identifier for the PayPal subscription.

    Returns:
        dict: The JSON response from PayPal if successful, or None if an error occurs.
    """
    try:
        base_url = get_paypal_base_url()
        access_token = get_paypal_access_token()
        url = f"{base_url}/v1/billing/subscriptions/{subscription_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
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
    base_url = get_paypal_base_url()
    access_token = get_paypal_access_token()
    url = f"{base_url}/v1/catalogs/products"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(
            f"Failed to retrieve PayPal products: {response.status_code}, {response.text}"
        )


def create_paypal_product(product_data=None):
    """
    Create a product on PayPal using the PayPal REST API.

    Args:
        product_data (dict): A dictionary containing product details as per PayPal API requirements.

    Returns:
        dict: The JSON response from PayPal if successful.

    Raises:
        Exception: If the API request fails.
    """

    product_data = {
        "name": "Sat Nam yoga service",
        "description": "Monthly and yearly  subscriptions for video streaming  yoga service",
        "type": "SERVICE",
        "category": "SOFTWARE",
        "image_url": "https://satnam-bucket.s3.us-east-2.amazonaws.com/logo.png",
        "home_url": "https://www.satnamyogaestudio.com.mx/",
    }
    base_url = get_paypal_base_url()
    access_token = get_paypal_access_token()
    url = f"{base_url}/v1/catalogs/products"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers, json=product_data)
    if response.status_code == 201:
        return response.json()
    else:
        raise Exception(
            f"Failed to create PayPal product: {response.status_code}, {response.text}"
        )


def schedule_subscription_deletion(subscription_id, billing_cycle_end):
    """Schedule the deletion of the PayPal subscription using Celery."""
    # Convert the billing cycle end time to a datetime object
    from payments.tasks import cancel_paypal_subscription_task

    end_time = datetime.strptime(billing_cycle_end, "%Y-%m-%dT%H:%M:%SZ")
    end_time = pytz.UTC.localize(end_time)  # Ensure timezone awareness

    # Schedule the Celery task
    task = cancel_paypal_subscription_task.apply_async(
        eta=end_time,  # Schedule for the billing cycle end time
        args=[subscription_id],
        task_id=f"delete_subscription_{subscription_id}",  # Assign a custom task ID
    )

    logger.info(
        f"Deletion of PayPal subscription {subscription_id} scheduled for {end_time.isoformat()} with task ID {task.id}"
    )


def remove_scheduled_deletion(subscription_id):
    """Remove scheduled deletion task for a subscription."""
    task_id = f"delete_subscription_{subscription_id}"
    result = AsyncResult(task_id)

    if result.state == "PENDING":
        result.revoke()  # Revoke the task before it is executed
        logger.info(f"Removed scheduled deletion for subscription {subscription_id}")
    else:
        logger.info(
            f"Task for subscription {subscription_id} is already in state {result.state} and cannot be revoked"
        )


def verify_paypal_webhook_signature(request):
    """
    Verifies the PayPal webhook signature using request data.

    Args:
    - request: Django request object containing the webhook data and headers.

    Returns:
    - bool: True if the signature is verified, False otherwise.
    """
    payload = request.body.decode("utf-8")
    transmission_id = request.headers.get("Paypal-Transmission-Id")
    timestamp = request.headers.get("Paypal-Transmission-Time")
    signature = request.headers.get("Paypal-Transmission-Sig")
    cert_url = request.headers.get("Paypal-Cert-Url")
    auth_algo = request.headers.get("Paypal-Auth-Algo")
    webhook_id = settings.PAYPAL_WEBHOOK_ID  # Replace with your actual webhook ID

    try:
        response = paypalrestsdk.WebhookEvent.verify(
            transmission_id=transmission_id,
            timestamp=timestamp,
            webhook_id=webhook_id,
            event_body=payload,
            cert_url=cert_url,
            actual_sig=signature,
            auth_algo=auth_algo,
        )
        return response
    except Exception as e:
        print("Error verifying PayPal webhook signature: ", e)
        return False
