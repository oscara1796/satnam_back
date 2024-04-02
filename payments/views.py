import json
import logging
from datetime import datetime, timezone

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from dotenv import dotenv_values
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from stripe.error import StripeError

from core.models import CustomUser

from .models import StripeEvent
from .serializers import PaymentMethodSerializer

env_vars = dotenv_values(".env.dev")
stripe.api_key = env_vars["STRIPE_SECRET_KEY"]
# Create your views here.
FRONTEND_SUBSCRIPTION_SUCCESS_URL = settings.SUBSCRIPTION_SUCCESS_URL
FRONTEND_SUBSCRIPTION_CANCEL_URL = settings.SUBSCRIPTION_FAILED_URL

webhook_secret = settings.STRIPE_WEBHOOK_SECRET

logger = logging.getLogger("django")


class PricesListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # extract pagination parameters from query params
        try:
            data = stripe.Product.list()

            products = data.data

            for product in products:
                data_json_product = stripe.Price.retrieve(product.default_price)
                product["price"] = data_json_product.unit_amount
                product["currency"] = data_json_product.currency
            json_str = json.dumps(products)

            return Response(json_str, status=200)
        except Exception as e:
            return Response({"errors": e}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SubscriptionDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data
        try:
            checkout_session = stripe.checkout.Session.create(
                line_items=[{"price": data["price_id"], "quantity": 1}],
                mode="subscription",
                success_url=FRONTEND_SUBSCRIPTION_SUCCESS_URL
                + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=FRONTEND_SUBSCRIPTION_CANCEL_URL,
            )
            return redirect(checkout_session.url, code=303)
        except Exception as err:
            return Response(
                {"errors": err}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaymentMethodView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            user = get_user_model().objects.get(id=pk)
            customer = stripe.Customer.retrieve(user.stripe_customer_id)

            # Retrieve the default payment method
            default_payment_method_id = customer.invoice_settings.default_payment_method
            default_payment_method = (
                stripe.PaymentMethod.retrieve(default_payment_method_id)
                if default_payment_method_id
                else None
            )

            # Retrieve all payment methods
            payment_methods = stripe.PaymentMethod.list(
                customer=user.stripe_customer_id, type="card"
            )

            return Response(
                {
                    "default_payment_method": default_payment_method,
                    "all_payment_methods": payment_methods.data,
                },
                status=status.HTTP_200_OK,
            )
        except get_user_model().DoesNotExist:
            return Response(
                {"message": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except StripeError as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, pk):
        try:
            user = get_user_model().objects.get(id=pk)
            serializer = PaymentMethodSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data
            payment_method = stripe.PaymentMethod.create(
                type="card",
                card=validated_data,
            )
            stripe.PaymentMethod.attach(
                payment_method.id,
                customer=user.stripe_customer_id,
            )

            stripe.Customer.modify(
                user.stripe_customer_id,
                invoice_settings={
                    "default_payment_method": payment_method.id,
                },
            )

            return Response(
                {"payment_method_id": payment_method.id}, status=status.HTTP_201_CREATED
            )
        except StripeError as e:

            return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        try:
            user = get_user_model().objects.get(id=pk)
            stripe.Customer.modify(
                user.stripe_customer_id,
                invoice_settings={
                    "default_payment_method": request.data.get("payment_method_id"),
                },
            )

            return Response(
                {"success": "Default payment method updated"}, status=status.HTTP_200_OK
            )
        except StripeError as e:
            return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        try:
            payment_method_id = request.data.get("payment_method_id")
            if not payment_method_id:
                return Response(
                    {"message": "No se proporciono un payment method"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Detach the payment method from the customer
            stripe.PaymentMethod.detach(payment_method_id)

            return Response(
                {"success": "Payment method detached and deleted"},
                status=status.HTTP_200_OK,
            )
        except StripeError as e:
            return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PaymentDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            user = get_user_model().objects.get(id=pk)
            # Retrieve the customer's Stripe subscription
            subscription = stripe.Subscription.retrieve(user.stripe_subscription_id)

            product = stripe.Product.retrieve(subscription.plan.product)

            response = {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end,
                "product_price": subscription.plan.amount,
                "product_name": product.name,
                "cancel_at_period_end": subscription.cancel_at_period_end,
            }

            if subscription.status == "trialing":
                response["trial_start"] = subscription.trial_start
                response["trial_end"] = subscription.trial_end

            # print(subscription)
            # Return the subscription details
            return Response(response, status=status.HTTP_200_OK)
        except get_user_model().DoesNotExist:
            return Response(
                {"message": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except StripeError as e:
            print("error ", e)
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, pk):
        try:
            user = get_user_model().objects.get(id=pk)

            payment_method_id = request.data.get("payment_method_id")
            subscription_args = {
                "customer": user.stripe_customer_id,
                "items": [{"price": request.data.get("price_id")}],
            }

            if payment_method_id:
                # Attach the provided payment method and set as default
                subscription_args["default_payment_method"] = payment_method_id
            else:
                serializer = PaymentMethodSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                # Create and attach a new payment method as per the existing flow
                validated_data = serializer.validated_data
                payment_method = stripe.PaymentMethod.create(
                    type="card", card=validated_data
                )
                stripe.PaymentMethod.attach(
                    payment_method.id, customer=user.stripe_customer_id
                )
                stripe.Customer.modify(
                    user.stripe_customer_id,
                    invoice_settings={"default_payment_method": payment_method.id},
                )

            # Subscription creation logic remains the same
            trial_days = request.data.get("trial")
            trial_period_days = None if trial_days is None else int(trial_days)

            if trial_period_days is not None:
                subscription_args["trial_period_days"] = trial_period_days
            subscription = stripe.Subscription.create(**subscription_args)

            user.stripe_subscription_id = subscription.id
            user.active = subscription.status in ("active", "trialing")
            user.save()

            response = {
                "stripe_customer_id": user.stripe_customer_id,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "user_is_active": user.active,
            }
            if subscription.status == "trialing":
                response["trial_start"] = subscription.trial_start
                response["trial_end"] = subscription.trial_end

            return Response(response, status=status.HTTP_201_CREATED)
        except stripe.error.StripeError as e:
            return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, pk):
        try:
            user = get_user_model().objects.get(id=pk)
            subscription_id = user.stripe_subscription_id

            if not subscription_id:
                return Response(
                    {"error": "Missing subscription_id in request data"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)

            return Response(
                {"success": "Subscription set to cancel at period end"},
                status=status.HTTP_200_OK,
            )
        except get_user_model().DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except StripeError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def patch(self, request, pk):
        try:
            user = get_user_model().objects.get(id=pk)
            subscription_id = user.stripe_subscription_id

            if not subscription_id:
                return Response(
                    {"error": "Missing subscription_id"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            print("hola")
            # Update the subscription to not cancel at the period end
            updated_subscription = stripe.Subscription.modify(
                subscription_id, cancel_at_period_end=False
            )

            # Prepare and return the response
            response = {
                "subscription_id": updated_subscription.id,
                "cancel_at_period_end": updated_subscription.cancel_at_period_end,
            }
            return Response(response, status=status.HTTP_200_OK)
        except get_user_model().DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except StripeError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class StripeWebhookView(APIView):
    def post(self, request, *args, **kwargs):
        payload = request.body
        event = None

        try:
            payload_data = json.loads(payload)
            event = stripe.Event.construct_from(payload_data, stripe.api_key)
        except ValueError as e:
            # Invalid payload
            return JsonResponse({"error": str(e)}, status=400)

        existing_event = StripeEvent.objects.filter(stripe_event_id=event.id).first()
        if existing_event:
            if existing_event.status == "processed":
                # Event already processed successfully
                return Response(status=200)

        try:

            with transaction.atomic():

                # Handle the event based on its type
                if event.type == "invoice.payment_succeeded":
                    invoice = event.data.object
                    customer_id = invoice.customer
                    print("invoice paid")
                    # Retrieve customer's email from your database
                    customer_email = self.get_customer_email(customer_id)
                    if customer_email:
                        print("mandamos email")
                        self.send_invoice_email(customer_email, invoice)

                elif event.type == "invoice.payment_failed":
                    invoice = event.data.object
                    customer_id = invoice.customer

                    # Retrieve customer's email from your database
                    customer_email = self.get_customer_email(customer_id)
                    if customer_email:
                        self.send_payment_failed_email(customer_email, invoice)

                elif event.type == "customer.subscription.created":
                    subscription = event.data.object
                    if subscription.trial_end:
                        customer_id = subscription.customer
                        customer_email = self.get_customer_email(customer_id)
                        if customer_email:
                            self.send_trial_start_email(customer_email, subscription)

                elif event.type == "customer.subscription.updated":
                    """
                    Occurs whenever a subscription changes (e.g., switching from one plan to another, or changing the status from trial to active).
                    """
                    pass

                elif event.type == "customer.subscription.deleted":
                    subscription = event.data.object
                    customer_id = subscription.customer
                    # Retrieve customer's email from your database
                    customer_email = self.get_customer_email(customer_id)
                    if customer_email:
                        self.send_subscription_deleted_email(customer_email)

                    try:
                        user = CustomUser.objects.get(stripe_customer_id=customer_id)
                        user.active = False
                        user.stripe_subscription_id = None
                        user.save()
                    except CustomUser.DoesNotExist:
                        return JsonResponse({"status": "user not found"}, status=404)

                elif event.type == "customer.subscription.trial_will_end":
                    subscription = event.data.object
                    customer_id = subscription.customer
                    customer_email = self.get_customer_email(customer_id)
                    if customer_email:
                        self.send_trial_will_end_email(customer_email, subscription)

                if existing_event:
                    existing_event.status = "processed"
                    existing_event.save()
                else:
                    # If the event is processed successfully, record it as 'processed'
                    StripeEvent.objects.create(
                        stripe_event_id=event.id, status="processed"
                    )

        except Exception as e:
            # Log the exception
            logger.error(f"Error processing Stripe webhook: {e}", exc_info=True)
            # If processing fails, record the event as failed
            if existing_event:
                existing_event.status = "failed"
                existing_event.save()
            else:
                # If anything goes wrong, record the event as 'failed'
                StripeEvent.objects.create(stripe_event_id=event.id, status="failed")
            # Return a non-200 response to indicate failure to Stripe
            print(e)
            return JsonResponse({"error": str(e)}, status=500)

        return Response(status=200)

    def get_customer_email(self, customer_id):
        # Implement logic to retrieve customer's email from your database
        try:
            user = get_user_model().objects.get(stripe_customer_id=customer_id)
            customer_email = user.email
            return customer_email
        except Exception as e:
            print(f"Error: {e}")

        return None

    def send_invoice_email(self, customer_email, invoice):
        subject = "Pago Sat Nam Yoga Notificación"
        message = """
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
                    <p>Pago ID: <b>{}</b></p>
                    <p>Monto: <b>{:.2f} {}</b></p>
                    <p>Gracias por tu apoyo.</p>
                    <p>Saludos,</p>
                    <p>El equipo de Sat Nam Yoga</p>
                </div>
            </body>
            </html>
            """.format(
            invoice.id, invoice.amount_due / 100, invoice.currency
        )
        from_email = "satnamyogajal@gmail.com"  # Replace with your email address
        recipient_list = [customer_email]

        send_mail(
            subject,
            message,
            from_email,
            recipient_list,
            fail_silently=False,
            html_message=message,
        )

    def send_trial_start_email(self, customer_email, subscription):
        # Convert to a readable format, timezone-aware
        readable_date = datetime.fromtimestamp(
            subscription.trial_end, timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S")
        # Set the timezone to UTC using `replace`
        subject = "Bienvenido a tu período de prueba! Sat Nam Yoga Estudio"
        message = f"Estimado cliente,\n\n¡Gracias por comenzar un período de prueba con nosotros! Esperamos que disfrutes de todo lo que tenemos para ofrecer. Tu período de prueba termina el {readable_date}."
        from_email = "satnamyogajal@gmail.com"
        recipient_list = [customer_email]

        send_mail(subject, message, from_email, recipient_list)

    def send_payment_failed_email(self, customer_email, invoice):
        subject = "Notificación de Pago Fallido"
        message = f"Hola,\n\nTu pago para el ID de factura: {invoice.id} ha fallado.\nPor favor, actualiza tu información de pago o contacta al soporte."
        from_email = "satnamyogajal@gmail.com"  # Replace with your email address
        recipient_list = [customer_email]

        send_mail(subject, message, from_email, recipient_list)

    def send_subscription_deleted_email(self, customer_email):
        subject = (
            "Vamos a extrañarte! Subscripción ha sido eliminado (Sat Nam yoga Estudio)"
        )
        message = "Estimado cliente,\n\nHemos notado que tu suscripción ha sido eliminada. ¡Vamos a extrañarte! Si tienes algún comentario o necesitas asistencia, no dudes en contactarnos."
        from_email = "satnamyogajal@gmail.com"  # Replace with your email address
        recipient_list = [customer_email]

        send_mail(subject, message, from_email, recipient_list)

    def send_trial_will_end_email(self, customer_email, subscription):
        subject = "Tu período de prueba está por terminar"
        message = f"Estimado cliente,\n\nSolo un aviso de que tu período de prueba está por terminar. Se te cobrará después del {subscription.trial_end}. ¡Esperamos que hayas disfrutado tu prueba!"
        from_email = "satnamyogajal@gmail.com"
        recipient_list = [customer_email]

        send_mail(subject, message, from_email, recipient_list)
