import logging
from datetime import datetime, timezone

from django.core.mail import send_mail

logger = logging.getLogger("django")


def send_invoice_email(customer_email, invoice):
    subject = "Pago Sat Nam Yoga Notificación"
    logo_url = "https://satnam-bucket.s3.us-east-2.amazonaws.com/logo.png"
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
    readable_date = datetime.fromtimestamp(
        subscription.trial_end, timezone.utc
    ).strftime("%Y-%m-%d %H:%M:%S")
    subject = "Bienvenido a tu período de prueba! Sat Nam Yoga Estudio"
    logo_url = "https://satnam-bucket.s3.us-east-2.amazonaws.com/logo.png"
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
    subject = "Notificación de Pago Fallido (Sat Nam yoga Estudio)"
    logo_url = "https://satnam-bucket.s3.us-east-2.amazonaws.com/logo.png"
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
    subject = (
        "Vamos a extrañarte! Subscripción ha sido eliminada (Sat Nam Yoga Estudio)"
    )
    logo_url = "https://satnam-bucket.s3.us-east-2.amazonaws.com/logo.png"
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
    subject = "Tu período de prueba  Sat Nam Yoga está por terminar"
    logo_url = "https://satnam-bucket.s3.us-east-2.amazonaws.com/logo.png"
    readable_date = datetime.fromtimestamp(
        subscription.trial_end, timezone.utc
    ).strftime("%Y-%m-%d %H:%M:%S")
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
    subject = "Tu suscripción de Sat Nam Yoga con  PayPal ha sido activada"
    logo_url = "https://satnam-bucket.s3.us-east-2.amazonaws.com/logo.png"
    message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Suscripción activada</title>
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
                    <h1>Suscripción activada</h1>
                </div>
                <div class="content">
                    <p>Hola,</p>
                    <p>Tu suscripción con ID: <b>{subscription['id']}</b> ha sido activada.</p>
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


def send_paypal_subscription_cancelled_email(customer_email, subscription):
    subject = "Tu suscripción de PayPal de Sat Nam Yoga  ha sido cancelada"
    logo_url = "https://satnam-bucket.s3.us-east-2.amazonaws.com/logo.png"
    message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Suscripción cancelada</title>
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
                    <h1>Suscripción cancelada</h1>
                </div>
                <div class="content">
                    <p>Hola,</p>
                    <p>Tu suscripción con ID: <b>{subscription['id']}</b> ha sido cancelada.</p>
                    <p>Si tienes algún comentario o necesitas asistencia, no dudes en contactarnos.</p>
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


def send_paypal_subscription_expired_email(customer_email, subscription):
    subject = "Tu suscripción Sat Nam Yoga de PayPal ha expirado"
    logo_url = "https://satnam-bucket.s3.us-east-2.amazonaws.com/logo.png"
    message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Suscripción expirada</title>
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
                    <h1>Suscripción expirada</h1>
                </div>
                <div class="content">
                    <p>Hola,</p>
                    <p>Tu suscripción con ID: <b>{subscription['id']}</b> ha expirado.</p>
                    <p>Si tienes algún comentario o necesitas asistencia, no dudes en contactarnos.</p>
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


def send_paypal_subscription_suspended_email(customer_email, subscription):
    subject = "Tu suscripción de Sat Nam Yoga con  PayPal ha sido suspendida"
    logo_url = "https://satnam-bucket.s3.us-east-2.amazonaws.com/logo.png"
    message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Suscripción suspendida</title>
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
                    <h1>Suscripción suspendida</h1>
                </div>
                <div class="content">
                    <p>Hola,</p>
                    <p>Tu suscripción con ID: <b>{subscription['id']}</b> ha sido suspendida.</p>
                    <p>Si tienes algún comentario o necesitas asistencia, no dudes en contactarnos.</p>
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


def send_paypal_subscription_reactivated_email(customer_email, subscription):
    subject = "Tu suscripción de SatNam con PayPal ha sido reactivada"
    logo_url = "https://satnam-bucket.s3.us-east-2.amazonaws.com/logo.png"
    message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Suscripción reactivada</title>
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
                    <h1>Suscripción reactivada</h1>
                </div>
                <div class="content">
                    <p>Hola,</p>
                    <p>Tu suscripción con ID: <b>{subscription['id']}</b> ha sido reactivada.</p>
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


def send_email(subject, message, from_email, recipient_list):
    try:
        send_mail(
            subject,
            message,
            from_email,
            recipient_list,
            fail_silently=False,
            html_message=message,
        )
        logger.info(f"Email sent to {recipient_list} with subject '{subject}'")
        return True
    except Exception as e:
        logger.error(
            f"Failed to send email to {recipient_list} with subject '{subject}': {e}",
            exc_info=True,
        )
        return False
