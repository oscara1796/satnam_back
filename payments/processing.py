from django.core.mail import send_mail
from datetime import datetime, timezone
import logging
from core.models import CustomUser # Adjust your imports as necessary

logger = logging.getLogger("django")

def process_event(event):
    try:
        event_type = event.type

        if event_type == "invoice.payment_succeeded":
            handle_invoice_payment_succeeded(event)

        elif event_type == "invoice.payment_failed":
            handle_invoice_payment_failed(event)

        elif event_type == "customer.subscription.created":
            handle_subscription_created(event)

        elif event_type == "customer.subscription.updated":
            handle_subscription_updated(event)

        elif event_type == "customer.subscription.deleted":
            handle_subscription_deleted(event)

        elif event_type == "customer.subscription.trial_will_end":
            handle_trial_will_end(event)

        else:
            logger.info(f"Unhandled event type: {event_type}")

    except Exception as e:
        logger.error(f"Error processing event {event.id}: {e}", exc_info=True)
       
def handle_invoice_payment_succeeded(event):
    invoice = event.data.object
    customer_id = invoice.customer
    customer_email = get_customer_email(customer_id)
    if customer_email:
        send_invoice_email(customer_email, invoice)
        logger.info(f"Invoice payment email sent for invoice {invoice.id} to {customer_email}")


def handle_invoice_payment_failed(event):
    invoice = event.data.object
    customer_id = invoice.customer
    customer_email = get_customer_email(customer_id)
    if customer_email:
        send_payment_failed_email(customer_email, invoice)
        logger.info(f"Payment failed email sent for invoice {invoice.id} to {customer_email}")


def handle_subscription_created(event):
    subscription = event.data.object
    if subscription.trial_end:
        customer_id = subscription.customer
        customer_email = get_customer_email(customer_id)
        if customer_email:
            send_trial_start_email(customer_email, subscription)
            logger.info(f"Trial start email sent for subscription {subscription.id} to {customer_email}")


def handle_subscription_updated(event):
    # Implement logic for handling subscription updates if needed
    pass

def handle_subscription_deleted(event):
    subscription = event.data.object
    customer_id = subscription.customer
    customer_email = get_customer_email(customer_id)
    if customer_email:
        send_subscription_deleted_email(customer_email)
        logger.info(f"Subscription deleted email sent for subscription {subscription.id} to {customer_email}")

    try:
        user = CustomUser.objects.get(stripe_customer_id=customer_id)
        user.active = False
        user.stripe_subscription_id = None
        user.save()
        logger.info(f"User {user.id} deactivated after subscription deletion")
    except CustomUser.DoesNotExist:
        logger.error(f"User with Stripe customer ID {customer_id} not found")


def handle_trial_will_end(event):
    subscription = event.data.object
    customer_id = subscription.customer
    customer_email = get_customer_email(customer_id)
    if customer_email:
        send_trial_will_end_email(customer_email, subscription)
        logger.info(f"Trial end email sent for subscription {subscription.id} to {customer_email}")


def get_customer_email(customer_id):
    # Implement logic to retrieve customer's email from your database
    try:
        user = CustomUser.objects.get(stripe_customer_id=customer_id)
        return user.email
    except CustomUser.DoesNotExist:
        logger.error(f"Error retrieving email for customer {customer_id}: User does not exist")
        return None


def send_invoice_email(customer_email, invoice):
    subject = "Pago Sat Nam Yoga Notificación"
    message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Suscripción pagada</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f0f0f0;
                    margin: 0;
                    padding: 0;
                }}

                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #ffffff;
                    border-radius: 5px;
                    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                }}

                h1 {{
                    color: #3165f5;
                }}

                p {{
                    color: #333333;
                }}

                b {{
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Suscripción pagada</h1>
                <p>Hola,</p>
                <p>Has pagado tu suscripción de Sat Nam Yoga.</p>
                <p>Pago ID: <b>{invoice.id}</b></p>
                <p>Monto: <b>{invoice.amount_due / 100:.2f} {invoice.currency}</b></p>
                <p>Gracias por tu apoyo.</p>
                <p>Saludos,</p>
                <p>El equipo de Sat Nam Yoga</p>
            </div>
        </body>
        </html>
    """
    from_email = "satnamyogajal@gmail.com"
    recipient_list = [customer_email]

    send_mail(subject, message, from_email, recipient_list, fail_silently=False, html_message=message)


def send_trial_start_email(customer_email, subscription):
    readable_date = datetime.fromtimestamp(subscription.trial_end, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    subject = "Bienvenido a tu período de prueba! Sat Nam Yoga Estudio"
    message = f"Estimado cliente,\n\n¡Gracias por comenzar un período de prueba con nosotros! Esperamos que disfrutes de todo lo que tenemos para ofrecer. Tu período de prueba termina el {readable_date}."
    send_email(customer_email, subject, message)


def send_payment_failed_email(customer_email, invoice):
    subject = "Notificación de Pago Fallido"
    message = f"Hola,\n\nTu pago para el ID de factura: {invoice.id} ha fallado.\nPor favor, actualiza tu información de pago o contacta al soporte."
    send_email(customer_email, subject, message)


def send_subscription_deleted_email(customer_email):
    subject = "Vamos a extrañarte! Subscripción ha sido eliminado (Sat Nam yoga Estudio)"
    message = "Estimado cliente,\n\nHemos notado que tu suscripción ha sido eliminada. ¡Vamos a extrañarte! Si tienes algún comentario o necesitas asistencia, no dudes en contactarnos."
    send_email(customer_email, subject, message)


def send_trial_will_end_email(customer_email, subscription):
    subject = "Tu período de prueba está por terminar"
    message = f"Estimado cliente,\n\nSolo un aviso de que tu período de prueba está por terminar. Se te cobrará después del {subscription.trial_end}. ¡Esperamos que hayas disfrutado tu prueba!"
    send_email(customer_email, subject, message)


def send_email(to_email, subject, message):
    from_email = "satnamyogajal@gmail.com"
    send_mail(subject, message, from_email, [to_email], fail_silently=False)
    logger.info(f"Email sent to {to_email} with subject '{subject}'")
