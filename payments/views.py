import json
import logging
from datetime import datetime, timezone

import stripe
import redis
import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from stripe.error import StripeError

from core.models import CustomUser

from .models import StripeEvent
from .serializers import PaymentMethodSerializer

from dotenv import load_dotenv

load_dotenv(".env.dev")
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
# Create your views here.
FRONTEND_SUBSCRIPTION_SUCCESS_URL = settings.SUBSCRIPTION_SUCCESS_URL
FRONTEND_SUBSCRIPTION_CANCEL_URL = settings.SUBSCRIPTION_FAILED_URL

webhook_secret = settings.STRIPE_WEBHOOK_SECRET

logger = logging.getLogger("django")


class SubscriptionPlanAPIView(APIView):
    def get(self, request, pk=None):
        if pk:
            plan = SubscriptionPlan.objects.get(pk=pk)
        else:
            plans = SubscriptionPlan.objects.all()
        serializer = SubscriptionPlanSerializer(plans, many=not pk)
        return Response(serializer.data)

    def post(self, request):
        serializer = SubscriptionPlanSerializer(data=request.data)
        if serializer.is_valid():
            validated_data = serializer.validated_data
            
            # Create Stripe Product
            stripe_product = stripe.Product.create(
                name=validated_data['name'],
                description=validated_data['description'],
                images=[validated_data['image']] if validated_data.get('image') else [],
                metadata=validated_data.get('metadata', {})
            )
            
            # Create Stripe Price
            stripe_price = stripe.Price.create(
                product=stripe_product.id,
                unit_amount=int(validated_data['metadata'].get('price', 10) * 100),
                currency='mxn',
                recurring={"interval": "month"}
            )

            # Create PayPal Plan
            access_token = get_paypal_access_token()
            paypal_url = "https://api-m.sandbox.paypal.com/v1/billing/plans"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            }
            paypal_payload = {
                "product_id": validated_data['metadata']['paypal_product_id'],
                "name": validated_data['name'],
                "description": validated_data['description'],
                "status": "ACTIVE",
                "billing_cycles": [
                    {
                        "frequency": {
                            "interval_unit": "MONTH",
                            "interval_count": 1
                        },
                        "tenure_type": "REGULAR",
                        "sequence": 1,
                        "total_cycles": 0,
                        "pricing_scheme": {
                            "fixed_price": {
                                "value": str(validated_data['metadata'].get('price', 10)),
                                "currency_code": "USD"
                            }
                        }
                    }
                ],
                "payment_preferences": {
                    "auto_bill_outstanding": True,
                    "setup_fee_failure_action": "CONTINUE",
                    "payment_failure_threshold": 3
                }
            }
            paypal_response = requests.post(paypal_url, headers=headers, json=paypal_payload)
            paypal_plan = paypal_response.json()

            # Save to database
            plan = serializer.save(
                stripe_product_id=stripe_product.id,
                stripe_price_id=stripe_price.id,
                paypal_plan_id=paypal_plan['id'] if paypal_response.status_code == 201 else None
            )

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        plan = SubscriptionPlan.objects.get(pk=pk)
        serializer = SubscriptionPlanSerializer(plan, data=request.data, partial=True)
        if serializer.is_valid():
            # Update logic (similar structure as POST, with modification logic)
            plan.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        plan = SubscriptionPlan.objects.get(pk=pk)
        # Delete logic for PayPal and Stripe
        plan.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def patch(self, request, pk):
        return self.put(request, pk)


class PricesListView(APIView):
    

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
            logger.info("Retrieved product prices successfully.")
            return Response(json_str, status=200)
        except Exception as e:
            logger.error("Failed to retrieve product prices", exc_info=True)
            return Response({"errors": e}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# class SubscriptionDetailView(APIView):
#     permission_classes = [permissions.IsAuthenticated]

#     def post(self, request):
#         data = request.data
#         try:
#             checkout_session = stripe.checkout.Session.create(
#                 line_items=[{"price": data["price_id"], "quantity": 1}],
#                 mode="subscription",
#                 success_url=FRONTEND_SUBSCRIPTION_SUCCESS_URL
#                 + "?session_id={CHECKOUT_SESSION_ID}",
#                 cancel_url=FRONTEND_SUBSCRIPTION_CANCEL_URL,
#             )
#             logger.info("Checkout session created successfully.")
#             return redirect(checkout_session.url, code=303)
#         except Exception as err:
#             logger.error(f"Failed to create checkout session: {err}", exc_info=True)
#             return Response(
#                 {"errors": err}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )


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
            logger.info(f"Retrieved payment methods for user {user.id}")
            return Response(
                {
                    "default_payment_method": default_payment_method,
                    "all_payment_methods": payment_methods.data,
                },
                status=status.HTTP_200_OK,
            )
        except get_user_model().DoesNotExist:
            logger.warning(f"User with id {pk} not found")
            return Response(
                {"message": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except StripeError as e:
            logger.error(f"Stripe API error: {e}", exc_info=True)
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
            logger.info(f"Created and attached new payment method for user {user.id}")
            return Response(
                {"payment_method_id": payment_method.id}, status=status.HTTP_201_CREATED
            )
        except StripeError as e:
            logger.error(f"Failed to create or attach payment method: {e}", exc_info=True)
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
            logger.info(f"Updated default payment method for user {user.id}")
            return Response(
                {"success": "Default payment method updated"}, status=status.HTTP_200_OK
            )
        except StripeError as e:
            logger.error(f"Failed to update default payment method for user {user.id}: {e}", exc_info=True)
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
            logger.info(f"Detached and deleted payment method {payment_method_id}")
            return Response(
                {"success": "Payment method detached and deleted"},
                status=status.HTTP_200_OK,
            )
        except StripeError as e:
            logger.error(f"Failed to detach payment method: {e}", exc_info=True)
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

            logger.info(f"Subscription details retrieved for user {user.id}")
            return Response(response, status=status.HTTP_200_OK)
        except get_user_model().DoesNotExist:
            logger.error(f"User with ID {pk} not found.")
            return Response(
                {"message": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except StripeError as e:
            logger.error(f"Stripe error while retrieving subscription for user {user.id}: {e}", exc_info=True)
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


            logger.info(f"New subscription created for user {user.id}")
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
            logger.error(f"Stripe error while creating subscription for user {user.id}: {e}", exc_info=True)
            return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error while creating subscription: {e}", exc_info=True)
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, pk):
        try:
            user = get_user_model().objects.get(id=pk)
            subscription_id = user.stripe_subscription_id

            if not subscription_id:
                logger.warning(f"Attempt to cancel non-existent subscription for user {user.id}")
                return Response(
                    {"error": "Missing subscription_id in request data"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
            logger.info(f"Subscription set to cancel at period end for user {user.id}")
            return Response(
                {"success": "Subscription set to cancel at period end"},
                status=status.HTTP_200_OK,
            )
        except get_user_model().DoesNotExist:
            logger.error(f"User with ID {pk} not found.")
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except StripeError as e:
            logger.error(f"Stripe error while cancelling subscription for user {user.id}: {e}", exc_info=True)
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def patch(self, request, pk):
        try:
            user = get_user_model().objects.get(id=pk)
            subscription_id = user.stripe_subscription_id

            if not subscription_id:
                logger.warning(f"No subscription_id provided for update for user {user.id}")
                return Response(
                    {"error": "Missing subscription_id"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Update the subscription to not cancel at the period end
            updated_subscription = stripe.Subscription.modify(
                subscription_id, cancel_at_period_end=False
            )
            logger.info(f"Subscription update processed for user {user.id}")
            # Prepare and return the response
            response = {
                "subscription_id": updated_subscription.id,
                "cancel_at_period_end": updated_subscription.cancel_at_period_end,
            }
            return Response(response, status=status.HTTP_200_OK)
        except get_user_model().DoesNotExist:
            logger.error(f"User with ID {pk} not found.")
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except StripeError as e:
            logger.error(f"Stripe error while updating subscription for user {user.id}: {e}", exc_info=True)
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
            logger.info(f"Stripe event {event.type} received with ID {event.id}")
        except ValueError as e:
            logger.error(f"Invalid payload received: {str(e)}")
            return JsonResponse({"error": str(e)}, status=400)

        redis_conn = redis.Redis.from_url(settings.REDIS_URL)

        try:
            redis_conn.rpush('task_queue', json.dumps(payload_data))
            logger.info(f"Event {event.id} added to Redis queue")
        except Exception as e:
            logger.error(f"Error adding event to Redis queue: {e}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)

        return Response(status=200)


        