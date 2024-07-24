from datetime import datetime, timezone
import logging
from django.contrib.auth import get_user_model
import psycopg2
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger("django")

User = get_user_model()

def process_event(event, cur):
    try:
        event_type = event.get('type', event.get('event_type', 'Unknown event type'))
        logger.info(f"Processing event type: {event_type}")

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
            if event_type == "BILLING.SUBSCRIPTION.CREATED":
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
            return user['email']
        else:
            logger.error(f"Error retrieving email for customer {customer_id}: User does not exist")
            return None
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        return None

def get_customer_email_with_paypal_sub_id(paypal_subscription_id, cur):
    try:
        cur.execute("SELECT email FROM core_customuser WHERE paypal_subscription_id = %s", (paypal_subscription_id,))
        user = cur.fetchone()
        if user:
            return user['email']
        else:
            logger.error(f"Error retrieving email for PayPal subscription {paypal_subscription_id}: User does not exist")
            return None
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        return None


def handle_paypal_subscription_activated(event, cur):
    subscription = event['resource']
    customer_email = get_customer_email_with_paypal_sub_id(subscription["id"], cur)
    if customer_email:
        send_paypal_subscription_activated_email(customer_email, subscription)
        logger.info(f"Subscription activated email sent for subscription {subscription['id']} to {customer_email}")

def handle_paypal_subscription_cancelled(event, cur):
    subscription = event['resource']
    customer_email = get_customer_email_with_paypal_sub_id(subscription["id"], cur)
    if customer_email:
        send_paypal_subscription_cancelled_email(customer_email, subscription)
        logger.info(f"Subscription cancelled email sent for subscription {subscription['id']} to {customer_email}")

    try:
        cur.execute("SELECT * FROM core_customuser WHERE paypal_customer_id = %s FOR UPDATE", (subscription['id'],))
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
    customer_email = get_customer_email_with_paypal_sub_id(subscription["id"], cur)
    if customer_email:
        send_paypal_subscription_expired_email(customer_email, subscription)
        logger.info(f"Subscription expired email sent for subscription {subscription['id']} to {customer_email}")

def handle_paypal_subscription_suspended(event, cur):
    subscription = event['resource']
    customer_email = get_customer_email_with_paypal_sub_id(subscription["id"], cur)
    if customer_email:
        send_paypal_subscription_suspended_email(customer_email, subscription)
        logger.info(f"Subscription suspended email sent for subscription {subscription['id']} to {customer_email}")

def handle_paypal_subscription_reactivated(event, cur):
    subscription = event['resource']
    customer_email = get_customer_email_with_paypal_sub_id(subscription["id"], cur)
    if customer_email:
        send_paypal_subscription_reactivated_email(customer_email, subscription)
        logger.info(f"Subscription re-activated email sent for subscription {subscription['id']} to {customer_email}")

def send_invoice_email(customer_email, invoice):
    subject = "Pago Sat Nam Yoga Notificación"
    logo_url = f"https://satnam-bucket.s3.us-east-2.amazonaws.com/logo.png"
    message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Suscripción pagada</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f4f4f4;
                    margin: 0;
                    padding: 0;
                    color: #333;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    padding: 20px;
                    background-color: #ffffff;
                    border-radius: 8px;
                    box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
                    overflow: hidden;
                }}
                .header {{
                    background-color: #114c9e;
                    color: #ffffff;
                    padding: 20px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                }}
                .content {{
                    padding: 20px;
                    line-height: 1.6;
                }}
                .content p {{
                    margin: 0 0 10px;
                }}
                .content p b {{
                    color: #114c9e;
                }}
                .footer {{
                    margin-top: 20px;
                    text-align: center;
                    padding: 20px;
                    background-color: #f4f4f4;
                    color: #888888;
                }}
                .footer img {{
                    width: 150px;
                    height: auto;
                    margin-bottom: 10px;
                }}
                .footer p {{
                    margin: 5px 0 0;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Suscripción pagada</h1>
                </div>
                <div class="content">
                    <p>Hola,</p>
                    <p>Has pagado tu suscripción de Sat Nam Yoga.</p>
                    <p>Pago ID: <b>{invoice.id}</b></p>
                    <p>Monto: <b>{invoice.amount_due / 100:.2f} {invoice.currency.upper()}</b></p>
                    <p>Gracias por tu apoyo.</p>
                    <p>Saludos,</p>
                    <p>El equipo de Sat Nam Yoga</p>
                </div>
                <div class="footer">
                    <img src="{logo_url}" alt="Sat Nam Yoga Logo" />
                    <p>© 2023 Sat Nam Yoga Estudio. Todos los derechos reservados.</p>
                </div>
            </div>
        </body>
        </html>
    """
    from_email = "satnamyogajal@gmail.com"
    recipient_list = [customer_email]

    return send_email(subject, message, from_email, recipient_list)

def send_trial_start_email(customer_email, subscription):
    readable_date = datetime.fromtimestamp(subscription.trial_end, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    subject = "Bienvenido a tu período de prueba! Sat Nam Yoga Estudio"
    logo_url = f"https://satnam-bucket.s3.us-east-2.amazonaws.com/logo.png"
    message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Período de prueba</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f4f4f4;
                    margin: 0;
                    padding: 0;
                    color: #333;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    padding: 20px;
                    background-color: #ffffff;
                    border-radius: 8px;
                    box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
                    overflow: hidden;
                }}
                .header {{
                    background-color: #3165f5;
                    color: #ffffff;
                    padding: 20px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                }}
                .content {{
                    padding: 20px;
                    line-height: 1.6;
                }}
                .content p {{
                    margin: 0 0 10px;
                }}
                .content p b {{
                    color: #3165f5;
                }}
                .footer {{
                    margin-top: 20px;
                    text-align: center;
                    padding: 20px;
                    background-color: #f4f4f4;
                    color: #888888;
                }}
                .footer img {{
                    width: 150px;
                    height: auto;
                    margin-bottom: 10px;
                }}
                .footer p {{
                    margin: 5px 0 0;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Bienvenido a tu período de prueba!</h1>
                </div>
                <div class="content">
                    <p>Estimado cliente,</p>
                    <p>¡Gracias por comenzar un período de prueba con nosotros! Esperamos que disfrutes de todo lo que tenemos para ofrecer.</p>
                    <p>Tu período de prueba termina el <b>{readable_date}</b>.</p>
                    <p>Saludos,</p>
                    <p>El equipo de Sat Nam Yoga</p>
                </div>
                <div class="footer">
                    <img src="{logo_url}" alt="Sat Nam Yoga Logo" />
                    <p>© 2023 Sat Nam Yoga Estudio. Todos los derechos reservados.</p>
                </div>
            </div>
        </body>
        </html>
    """
    return send_email(subject, message, "satnamyogajal@gmail.com", [customer_email])


def send_payment_failed_email(customer_email, invoice):
    subject = "Notificación de Pago Fallido"
    logo_url = f"https://satnam-bucket.s3.us-east-2.amazonaws.com/logo.png"
    message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Pago Fallido</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f4f4f4;
                    margin: 0;
                    padding: 0;
                    color: #333;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    padding: 20px;
                    background-color: #ffffff;
                    border-radius: 8px;
                    box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
                    overflow: hidden;
                }}
                .header {{
                    background-color: #d9534f;
                    color: #ffffff;
                    padding: 20px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                }}
                .content {{
                    padding: 20px;
                    line-height: 1.6;
                }}
                .content p {{
                    margin: 0 0 10px;
                }}
                .content p b {{
                    color: #d9534f;
                }}
                .footer {{
                    margin-top: 20px;
                    text-align: center;
                    padding: 20px;
                    background-color: #f4f4f4;
                    color: #888888;
                }}
                .footer img {{
                    width: 150px;
                    height: auto;
                    margin-bottom: 10px;
                }}
                .footer p {{
                    margin: 5px 0 0;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Pago Fallido</h1>
                </div>
                <div class="content">
                    <p>Hola,</p>
                    <p>Tu pago para el ID de factura: <b>{invoice.id}</b> ha fallado.</p>
                    <p>Por favor, actualiza tu información de pago o contacta al soporte.</p>
                    <p>Saludos,</p>
                    <p>El equipo de Sat Nam Yoga</p>
                </div>
                <div class="footer">
                    <img src="{logo_url}" alt="Sat Nam Yoga Logo" />
                    <p>© 2023 Sat Nam Yoga Estudio. Todos los derechos reservados.</p>
                </div>
            </div>
        </body>
        </html>
    """
    return send_email(subject, message, "satnamyogajal@gmail.com", [customer_email])

def send_subscription_deleted_email(customer_email):
    subject = "Vamos a extrañarte! Subscripción ha sido eliminada (Sat Nam Yoga Estudio)"
    logo_url = f"https://satnam-bucket.s3.us-east-2.amazonaws.com/logo.png"
    message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Subscripción Eliminada</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f4f4f4;
                    margin: 0;
                    padding: 0;
                    color: #333;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    padding: 20px;
                    background-color: #ffffff;
                    border-radius: 8px;
                    box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
                    overflow: hidden;
                }}
                .header {{
                    background-color: #114c9e;
                    color: #ffffff;
                    padding: 20px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                }}
                .content {{
                    padding: 20px;
                    line-height: 1.6;
                }}
                .content p {{
                    margin: 0 0 10px;
                }}
                .content p b {{
                    color: #114c9e;
                }}
                .footer {{
                    margin-top: 20px;
                    text-align: center;
                    padding: 20px;
                    background-color: #f4f4f4;
                    color: #888888;
                }}
                .footer img {{
                    width: 150px;
                    height: auto;
                    margin-bottom: 10px;
                }}
                .footer p {{
                    margin: 5px 0 0;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Vamos a extrañarte!</h1>
                </div>
                <div class="content">
                    <p>Estimado cliente,</p>
                    <p>Hemos notado que tu suscripción ha sido eliminada. ¡Vamos a extrañarte! Si tienes algún comentario o necesitas asistencia, no dudes en contactarnos.</p>
                    <p>Saludos,</p>
                    <p>El equipo de Sat Nam Yoga</p>
                </div>
                <div class="footer">
                    <img src="{logo_url}" alt="Sat Nam Yoga Logo" />
                    <p>© 2023 Sat Nam Yoga Estudio. Todos los derechos reservados.</p>
                </div>
            </div>
        </body>
        </html>
    """
    return send_email(subject, message, "satnamyogajal@gmail.com", [customer_email])


def send_trial_will_end_email(customer_email, subscription):
    subject = "Tu período de prueba está por terminar"
    logo_url = f"https://satnam-bucket.s3.us-east-2.amazonaws.com/logo.png"
    readable_date = datetime.fromtimestamp(subscription.trial_end, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Período de prueba por terminar</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f4f4f4;
                    margin: 0;
                    padding: 0;
                    color: #333;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    padding: 20px;
                    background-color: #ffffff;
                    border-radius: 8px;
                    box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
                    overflow: hidden;
                }}
                .header {{
                    background-color: #3165f5;
                    color: #ffffff;
                    padding: 20px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                }}
                .content {{
                    padding: 20px;
                    line-height: 1.6;
                }}
                .content p {{
                    margin: 0 0 10px;
                }}
                .content p b {{
                    color: #3165f5;
                }}
                .footer {{
                    margin-top: 20px;
                    text-align: center;
                    padding: 20px;
                    background-color: #f4f4f4;
                    color: #888888;
                }}
                .footer img {{
                    width: 150px;
                    height: auto;
                    margin-bottom: 10px;
                }}
                .footer p {{
                    margin: 5px 0 0;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Tu período de prueba está por terminar</h1>
                </div>
                <div class="content">
                    <p>Estimado cliente,</p>
                    <p>Solo un aviso de que tu período de prueba está por terminar. Se te cobrará después del <b>{readable_date}</b>. ¡Esperamos que hayas disfrutado tu prueba!</p>
                    <p>Saludos,</p>
                    <p>El equipo de Sat Nam Yoga</p>
                </div>
                <div class="footer">
                    <img src="{logo_url}" alt="Sat Nam Yoga Logo" />
                    <p>© 2023 Sat Nam Yoga Estudio. Todos los derechos reservados.</p>
                </div>
            </div>
        </body>
        </html>
    """
    return send_email(subject, message, "satnamyogajal@gmail.com", [customer_email])


def send_paypal_subscription_activated_email(customer_email, subscription):
    subject = "Your PayPal Subscription is Activated"
    message = f"Your subscription with ID {subscription['id']} has been activated."
    from_email = "satnamyogajal@gmail.com"
    recipient_list = [customer_email]
    send_email(subject, message, from_email, recipient_list)

def send_paypal_subscription_cancelled_email(customer_email, subscription):
    subject = "Your PayPal Subscription is Cancelled"
    message = f"Your subscription with ID {subscription['id']} has been cancelled."
    from_email = "satnamyogajal@gmail.com"
    recipient_list = [customer_email]
    send_email(subject, message, from_email, recipient_list)

def send_paypal_subscription_expired_email(customer_email, subscription):
    subject = "Your PayPal Subscription has Expired"
    message = f"Your subscription with ID {subscription['id']} has expired."
    from_email = "satnamyogajal@gmail.com"
    recipient_list = [customer_email]
    send_email(subject, message, from_email, recipient_list)

def send_paypal_subscription_suspended_email(customer_email, subscription):
    subject = "Your PayPal Subscription is Suspended"
    message = f"Your subscription with ID {subscription['id']} has been suspended."
    from_email = "satnamyogajal@gmail.com"
    recipient_list = [customer_email]
    send_email(subject, message, from_email, recipient_list)

def send_paypal_subscription_reactivated_email(customer_email, subscription):
    subject = "Your PayPal Subscription is Re-Activated"
    message = f"Your subscription with ID {subscription['id']} has been re-activated."
    from_email = "satnamyogajal@gmail.com"
    recipient_list = [customer_email]
    send_email(subject, message, from_email, recipient_list)


def send_email(subject, message, from_email, recipient_list):
    try:
        send_mail(subject, message, from_email, recipient_list, fail_silently=False, html_message=message)
        logger.info(f"Email sent to {recipient_list} with subject '{subject}'")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_list} with subject '{subject}': {e}", exc_info=True)
        return False
