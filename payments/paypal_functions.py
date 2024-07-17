import requests
from requests.auth import HTTPBasicAuth
import json
import os
from dotenv import load_dotenv
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
        print(f"HTTPError: {str(e)}")
    except requests.exceptions.RequestException as e:
        # Handle other possible errors (e.g., network issues)
        print(f"RequestException: {str(e)}")
    return None

# def create_paypal_product():
#     access_token = get_paypal_access_token()
#     print(access_token)
#     url = "https://api-m.sandbox.paypal.com/v1/catalogs/products"
#     headers = {
#         "Content-Type": "application/json",
#         "Authorization": f"Bearer {access_token}"
#     }
#     payload = {
#         "name": "Subscripción anual satnam",
#         "description": "Subscripción anual de satnam",
#         "type": "SERVICE",
#         "category": "SOFTWARE"
#     }
#     response = requests.post(url, headers=headers, data=json.dumps(payload))
    
#     if response.status_code == 201:
#         return response.json()
#     else:
#         raise Exception(f"Failed to create product: {response.status_code}, {response.text}")

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

# Example usage:
