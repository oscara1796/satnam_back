from datetime import datetime, timezone
import logging
from django.contrib.auth import get_user_model
import psycopg2
from .send_email_functions import *
from django.conf import settings

logger = logging.getLogger("django")

User = get_user_model()

def process_event(event, cur):
    try:
        event_type = event.get('type', event.get('event_type', 'Unknown event type'))
        logger.info(f"Processing event type: {event_type}")

        print(event)

        # Handle Stripe events
        if 'type' in event:
            if event_type == "invoice.payment_succeeded":
                handle_invoice_payment_succeeded(event, cur)
                return True
            elif event_type == "invoice.payment_failed":
                handle_invoice_payment_failed(event, cur)
                return True
            elif event_type == "customer.subscription.created":
                handle_subscription_created(event, cur)
                return True
            elif event_type == "customer.subscription.updated":
                handle_subscription_updated(event, cur)
                return True
            elif event_type == "customer.subscription.deleted":
                handle_subscription_deleted(event, cur)
                return True
            elif event_type == "customer.subscription.trial_will_end":
                handle_trial_will_end(event, cur)
                return True
            else:
                logger.info(f"Unhandled Stripe event type: {event_type}")

        # Handle PayPal events
        elif 'event_type' in event:
            if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
                handle_paypal_subscription_activated(event, cur)
                return True
            elif event_type == "BILLING.SUBSCRIPTION.CANCELLED":
                handle_paypal_subscription_cancelled(event, cur)
                return True
            elif event_type == "BILLING.SUBSCRIPTION.EXPIRED":
                handle_paypal_subscription_expired(event, cur)
                return True
            elif event_type == "BILLING.SUBSCRIPTION.SUSPENDED":
                handle_paypal_subscription_suspended(event, cur)
                return True
            elif event_type == "BILLING.SUBSCRIPTION.RE-ACTIVATED":
                handle_paypal_subscription_reactivated(event, cur)
                return True
            else:
                logger.info(f"Unhandled PayPal event type: {event_type}")

    except Exception as e:
        logger.error(f"Error processing event {event.get('id', 'unknown id')}: {e}", exc_info=True)

    return False

def handle_invoice_payment_succeeded(event, cur):
    invoice = event.data.object
    customer_id = invoice.customer
    customer_email = get_customer_email(customer_id, cur)
    if customer_email:
        if send_invoice_email(customer_email, invoice):
            logger.info(f"Invoice payment email sent for invoice {invoice.id} to {customer_email}")

def handle_invoice_payment_failed(event, cur):
    invoice = event.data.object
    customer_id = invoice.customer
    customer_email = get_customer_email(customer_id, cur)
    if customer_email:
        if send_payment_failed_email(customer_email, invoice):
            logger.info(f"Payment failed email sent for invoice {invoice.id} to {customer_email}")

def handle_subscription_created(event, cur):
    subscription = event.data.object
    if subscription.trial_end:
        customer_id = subscription.customer
        customer_email = get_customer_email(customer_id, cur)
        if customer_email:
            if send_trial_start_email(customer_email, subscription):
                logger.info(f"Trial start email sent for subscription {subscription.id} to {customer_email}")

def handle_subscription_updated(event, cur):
    pass

def handle_subscription_deleted(event, cur):
    subscription = event.data.object
    customer_id = subscription.customer
    customer_email = get_customer_email(customer_id, cur)
    if customer_email:
        if send_subscription_deleted_email(customer_email):
            logger.info(f"Subscription deleted email sent for subscription {subscription.id} to {customer_email}")

    try:
        cur.execute("SELECT * FROM core_customuser WHERE stripe_customer_id = %s FOR UPDATE", (customer_id,))
        user = cur.fetchone()
        if user:
            user_id = user['id']
            cur.execute(
                """
                UPDATE core_customuser
                SET active = %s, stripe_subscription_id = %s
                WHERE id = %s
                """,
                (False, None, user_id)
            )
            logger.info(f"User {user_id} deactivated after subscription deletion")
        else:
            logger.error(f"User with Stripe customer ID {customer_id} not found")
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")

def handle_trial_will_end(event, cur):
    subscription = event.data.object
    customer_id = subscription.customer
    customer_email = get_customer_email(customer_id, cur)
    if customer_email:
        if send_trial_will_end_email(customer_email, subscription):
            logger.info(f"Trial end email sent for subscription {subscription.id} to {customer_email}")

def get_customer_email(customer_id, cur):
    try:
        cur.execute("SELECT email FROM core_customuser WHERE stripe_customer_id = %s", (customer_id,))
        user = cur.fetchone()
        if user:
            return user[0]  # Access the first item in the tuple
        else:
            logger.error(f"Error retrieving email for customer {customer_id}: User does not exist")
            return None
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        return None

def get_customer_email_with_paypal_sub_id(event):
    try:
        if 'resource' in event and 'subscriber' in event['resource']:
            subscriber_info = event['resource']['subscriber']
            if 'email_address' in subscriber_info:
                return subscriber_info['email_address']
            else:
                logger.error("Error retrieving email: 'email_address' field is missing in subscriber info")
                return None
        else:
            logger.error("Error retrieving email: 'resource' or 'subscriber' field is missing in event")
            return None
    except Exception as e:
        logger.error(f"Error retrieving email from event: {e}", exc_info=True)
        return None


def handle_paypal_subscription_activated(event, cur):
    subscription = event['resource']
    customer_email = get_customer_email_with_paypal_sub_id(event)
    if customer_email:
        send_paypal_subscription_activated_email(customer_email, subscription)
        logger.info(f"Subscription activated email sent for subscription {subscription['id']} to {customer_email}")

def handle_paypal_subscription_cancelled(event, cur):
    subscription = event['resource']
    customer_email = get_customer_email_with_paypal_sub_id(event)
    if customer_email:
        send_paypal_subscription_cancelled_email(customer_email, subscription)
        logger.info(f"Subscription cancelled email sent for subscription {subscription['id']} to {customer_email}")

    try:
        cur.execute("SELECT * FROM core_customuser WHERE paypal_subscription_id = %s FOR UPDATE", (subscription['id'],))
        user = cur.fetchone()
        if user:
            user_id = user['id']
            cur.execute(
                """
                UPDATE core_customuser
                SET active = %s, paypal_subscription_id = %s
                WHERE id = %s
                """,
                (False, None, user_id)
            )
            logger.info(f"User {user_id} deactivated after subscription cancellation")
        else:
            logger.error(f"User with PayPal customer ID {subscription['id']} not found")
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")

def handle_paypal_subscription_expired(event, cur):
    subscription = event['resource']
    customer_email = get_customer_email_with_paypal_sub_id(event)
    if customer_email:
        send_paypal_subscription_expired_email(customer_email, subscription)
        logger.info(f"Subscription expired email sent for subscription {subscription['id']} to {customer_email}")

def handle_paypal_subscription_suspended(event, cur):
    subscription = event['resource']
    customer_email = get_customer_email_with_paypal_sub_id(event)
    if customer_email:
        send_paypal_subscription_suspended_email(customer_email, subscription)
        logger.info(f"Subscription suspended email sent for subscription {subscription['id']} to {customer_email}")

def handle_paypal_subscription_reactivated(event, cur):
    subscription = event['resource']
    customer_email = get_customer_email_with_paypal_sub_id(event)
    if customer_email:
        send_paypal_subscription_reactivated_email(customer_email, subscription)
        logger.info(f"Subscription re-activated email sent for subscription {subscription['id']} to {customer_email}")


