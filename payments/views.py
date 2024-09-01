import json
import logging
import os
from datetime import datetime, timedelta, timezone

import pytz
import requests
import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse, JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from stripe.error import StripeError

from core.models import CustomUser, TrialDays
from payments.paypal_functions import (get_paypal_access_token,
                                       get_paypal_subscription,
                                       remove_scheduled_deletion,
                                       schedule_subscription_deletion,
                                       verify_paypal_webhook_signature)

from .models import SubscriptionPlan
from .serializers import PaymentMethodSerializer, SubscriptionPlanSerializer
from .tasks import process_payment_event

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
# Create your views here.
FRONTEND_SUBSCRIPTION_SUCCESS_URL = settings.SUBSCRIPTION_SUCCESS_URL
FRONTEND_SUBSCRIPTION_CANCEL_URL = settings.SUBSCRIPTION_FAILED_URL

webhook_secret = settings.STRIPE_WEBHOOK_SECRET

logger = logging.getLogger("django")


class IsStaffOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if (
            request.method in permissions.SAFE_METHODS
        ):  # Allow GET, HEAD, OPTIONS requests
            return True
        return request.user.is_staff


class SubscriptionPlanAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get_trial_days(self):
        try:
            trial_days_entry = TrialDays.objects.first()
            if trial_days_entry:
                return trial_days_entry.days
            return 0
        except TrialDays.DoesNotExist:
            return 0

    def get(self, request, pk=None):
        if pk:
            plan = SubscriptionPlan.objects.get(pk=pk)
            logger.info(f"A specific plan was retrieved {plan}")
        else:
            plans = SubscriptionPlan.objects.all()
        serializer = SubscriptionPlanSerializer(plans, many=not pk)
        return Response(serializer.data)

    def post(self, request):

        serializer = SubscriptionPlanSerializer(data=request.data)
        if serializer.is_valid():
            validated_data = serializer.validated_data

            try:
                # Create Stripe Product with corrected metadata and marketing_features
                stripe_product = stripe.Product.create(
                    name=validated_data["name"],
                    description=validated_data["description"],
                    metadata={
                        k: str(v)
                        for k, v in validated_data.get("metadata", "{}").items()
                    },
                    marketing_features=validated_data.get("features", "[]"),
                )

                # Create Stripe Price with correct price handling
                stripe_price = stripe.Price.create(
                    product=stripe_product.id,
                    unit_amount=int(validated_data["price"] * 100),
                    currency="mxn",
                    recurring={"interval": validated_data["frequency_type"]},
                )

            except stripe.error.StripeError as e:
                return Response(
                    {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Create PayPal Plan
            access_token = get_paypal_access_token()
            paypal_url = "https://api-m.sandbox.paypal.com/v1/billing/plans"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            }
            trial_days = self.get_trial_days()
            billing_cycles = []

            if trial_days > 0:
                billing_cycles.append(
                    {
                        "frequency": {"interval_unit": "DAY", "interval_count": 1},
                        "tenure_type": "TRIAL",
                        "sequence": 1,
                        "total_cycles": trial_days,
                        "pricing_scheme": {
                            "fixed_price": {"value": "0", "currency_code": "MXN"}
                        },
                    }
                )

            billing_cycles.append(
                {
                    "frequency": {
                        "interval_unit": validated_data["frequency_type"].upper(),
                        "interval_count": 1,
                    },
                    "tenure_type": "REGULAR",
                    "sequence": 2 if trial_days > 0 else 1,
                    "total_cycles": 0,
                    "pricing_scheme": {
                        "fixed_price": {
                            "value": str(validated_data["price"]),
                            "currency_code": "MXN",
                        }
                    },
                }
            )

            paypal_payload = {
                "product_id": os.environ.get("PAYPAL_PRODUCT_ID"),
                "name": validated_data["name"],
                "description": validated_data["description"],
                "status": "ACTIVE",
                "billing_cycles": billing_cycles,
                "payment_preferences": {
                    "auto_bill_outstanding": True,
                    "setup_fee_failure_action": "CONTINUE",
                    "payment_failure_threshold": 3,
                },
            }
            paypal_response = requests.post(
                paypal_url, headers=headers, json=paypal_payload
            )
            paypal_plan = paypal_response.json()

            # Save to database
            plan = serializer.save(
                stripe_product_id=stripe_product.id,
                stripe_price_id=stripe_price.id,
                paypal_plan_id=(
                    paypal_plan["id"] if paypal_response.status_code == 201 else None
                ),
            )

            stripe.Product.modify(
                stripe_product.id,
                images=[plan.image.url],
            )

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        plan = SubscriptionPlan.objects.get(pk=pk)
        serializer = SubscriptionPlanSerializer(plan, data=request.data, partial=True)

        if serializer.is_valid():
            validated_data = serializer.validated_data

            # Detect changes
            changes = {
                field: validated_data[field]
                for field in validated_data
                if validated_data[field] != getattr(plan, field)
            }
            # Apply changes from serializer to the plan instance
            modified_plan = serializer.save()
            try:
                # Deactivate the existing PayPal plan if it exists
                if plan.paypal_plan_id:
                    self.deactivate_paypal_plan(plan.paypal_plan_id)

                # Formulate the new PayPal plan data
                paypal_payload = self.formulate_paypal_payload(
                    plan, validated_data, changes
                )

                # Create a new PayPal plan with the merged details
                new_paypal_plan = self.create_paypal_plan(paypal_payload)
                plan.paypal_plan_id = new_paypal_plan["id"]

                # Update Stripe Product if relevant fields are modified
                if any(
                    field in changes
                    for field in [
                        "name",
                        "description",
                        "image",
                        "metadata",
                        "features",
                    ]
                ):
                    stripe_update_params = {
                        "name": validated_data.get("name", plan.name),
                        "description": validated_data.get(
                            "description", plan.description
                        ),
                        "metadata": validated_data.get("metadata", plan.metadata),
                        "images": [modified_plan.image.url],
                        "marketing_features": validated_data.get("features", []),
                    }
                    stripe.Product.modify(
                        plan.stripe_product_id, **stripe_update_params
                    )

                # Update or create a new Stripe price
                if "price" in changes or "frequency_type" in changes:
                    stripe_price = stripe.Price.create(
                        product=plan.stripe_product_id,
                        unit_amount=int(validated_data["price"] * 100),
                        currency="mxn",
                        recurring={"interval": validated_data["frequency_type"]},
                    )
                    plan.stripe_price_id = stripe_price.id

                # Save the updated plan to the database
                plan.save()

                return Response(serializer.data)
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def formulate_paypal_payload(self, plan, validated_data, changes):
        """Create or update PayPal plan payload with data merged from existing plan and new changes."""
        trial_days = self.get_trial_days()
        billing_cycles = []

        if trial_days > 0:
            billing_cycles.append(
                {
                    "frequency": {"interval_unit": "DAY", "interval_count": 1},
                    "tenure_type": "TRIAL",
                    "sequence": 1,
                    "total_cycles": trial_days,
                    "pricing_scheme": {
                        "fixed_price": {"value": "0", "currency_code": "MXN"}
                    },
                }
            )

        billing_cycles.append(
            {
                "frequency": {
                    "interval_unit": validated_data.get(
                        "frequency_type", plan.frequency_type
                    ).upper(),
                    "interval_count": 1,
                },
                "tenure_type": "REGULAR",
                "sequence": 2 if trial_days > 0 else 1,
                "total_cycles": 0,
                "pricing_scheme": {
                    "fixed_price": {
                        "value": str(validated_data.get("price", plan.price)),
                        "currency_code": "MXN",
                    }
                },
            }
        )

        paypal_payload = {
            "product_id": os.environ.get(
                "PAYPAL_PRODUCT_ID", plan.metadata.get("paypal_product_id")
            ),
            "name": validated_data.get("name", plan.name),
            "description": validated_data.get("description", plan.description),
            "status": "ACTIVE",
            "billing_cycles": billing_cycles,
            "payment_preferences": {
                "auto_bill_outstanding": True,
                "setup_fee_failure_action": "CONTINUE",
                "payment_failure_threshold": 3,
            },
        }
        return paypal_payload

    def update_trial_days(self, pk, trial_days):
        """Update the trial days of a subscription plan."""
        plan = SubscriptionPlan.objects.get(pk=pk)

        try:
            # Deactivate the existing PayPal plan if it exists
            if plan.paypal_plan_id:
                self.deactivate_paypal_plan(plan.paypal_plan_id)

            # Create new PayPal plan data
            billing_cycles = []

            if trial_days > 0:
                billing_cycles.append(
                    {
                        "frequency": {"interval_unit": "DAY", "interval_count": 1},
                        "tenure_type": "TRIAL",
                        "sequence": 1,
                        "total_cycles": trial_days,
                        "pricing_scheme": {
                            "fixed_price": {"value": "0", "currency_code": "MXN"}
                        },
                    }
                )

            billing_cycles.append(
                {
                    "frequency": {
                        "interval_unit": plan.frequency_type.upper(),
                        "interval_count": 1,
                    },
                    "tenure_type": "REGULAR",
                    "sequence": 2 if trial_days > 0 else 1,
                    "total_cycles": 0,
                    "pricing_scheme": {
                        "fixed_price": {
                            "value": str(plan.price),
                            "currency_code": "MXN",
                        }
                    },
                }
            )

            paypal_payload = {
                "product_id": os.environ.get("PAYPAL_PRODUCT_ID"),
                "name": plan.name,
                "description": plan.description,
                "status": "ACTIVE",
                "billing_cycles": billing_cycles,
                "payment_preferences": {
                    "auto_bill_outstanding": True,
                    "setup_fee_failure_action": "CONTINUE",
                    "payment_failure_threshold": 3,
                },
            }
            new_paypal_plan = self.create_paypal_plan(paypal_payload)
            plan.paypal_plan_id = new_paypal_plan["id"]
            plan.save()

            return Response({"status": "success"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def create_paypal_plan(self, data):
        """Create a new PayPal plan based on the provided data."""
        access_token = get_paypal_access_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        paypal_url = "https://api-m.sandbox.paypal.com/v1/billing/plans"
        response = requests.post(paypal_url, headers=headers, json=data)
        if response.status_code == 201:
            return response.json()
        else:
            raise Exception(
                f"Failed to create new PayPal plan: {response.status_code}, {response.text}"
            )

    def deactivate_paypal_plan(self, plan_id):
        """Send a request to PayPal to deactivate a billing plan."""
        access_token = get_paypal_access_token()  # Retrieve a valid access token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        paypal_url = (
            f"https://api-m.sandbox.paypal.com/v1/billing/plans/{plan_id}/deactivate"
        )
        response = requests.post(paypal_url, headers=headers)
        if response.status_code not in (200, 204):
            raise Exception(
                f"Failed to deactivate PayPal plan {plan_id}: {response.text}"
            )

    def delete(self, request, pk):
        plan = SubscriptionPlan.objects.get(pk=pk)

        # Delete Stripe product
        stripe.Product.modify(plan.stripe_product_id, active=False)

        # Deactivate PayPal Plan
        access_token = get_paypal_access_token()
        paypal_url = f"https://api-m.sandbox.paypal.com/v1/billing/plans/{plan.paypal_plan_id}/deactivate"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        requests.post(paypal_url, headers=headers)

        plan.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def patch(self, request, pk):
        return self.put(request, pk)


class PaypalSubscriptionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, subscription_id=None):
        """Retrieve details for a single PayPal subscription."""
        if subscription_id is None:
            logger.error("No subscription ID provided.")
            return Response(
                {"error": "No subscription ID provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(f"Fetching subscription Paypal details for ID: {subscription_id}")
        access_token = get_paypal_access_token()
        url = f"https://api-m.sandbox.paypal.com/v1/billing/subscriptions/{subscription_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # This will raise an error for HTTP error codes
            logger.info(f"Successfully retrieved subscription details for ID: {subscription_id}")
            return Response(response.json(), status=status.HTTP_200_OK)
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error occurred: {e}")
            return Response(response.json(), status=response.status_code)
        except Exception as e:
            logger.error(f"An error occurred while fetching subscription details: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        """Create a subscription and save the subscription ID to a user."""
        data = request.data
        user_id = data.get("user_id")
        subscription_id = data.get("subscriptionID")

        logger.info(f"Attempting to save  Paypal subscription ID: {subscription_id} for user ID: {user_id}")
        try:
            user = CustomUser.objects.get(pk=user_id)
            user.paypal_subscription_id = subscription_id
            user.active = True
            user.save()
            logger.info(f"Successfully saved  paypal subscription ID: {subscription_id} for user ID: {user_id}")
            return Response(
                {"message": "Subscription saved successfully."},
                status=status.HTTP_201_CREATED,
            )
        except CustomUser.DoesNotExist:
            logger.error(f"User with ID {user_id} not found.")
            return Response(
                {"error": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"An error occurred while saving  paypal subscription: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        """Partially update a user's PayPal subscription."""
        logger.info(f"Received request to partially update subscription for user ID: {pk}")
        print("HOLA")
        try:
            user = CustomUser.objects.get(pk=pk)

            if user.paypal_subscription_id:
                paypal_subscription = get_paypal_subscription(user.paypal_subscription_id)
                logger.info(f"Retrieved PayPal subscription for user ID: {pk}")
                print("OUTSIDE SUSPENDED REVIEW ")
                if paypal_subscription["status"] == "SUSPENDED":
                    print("inside SUSPENDED REVIEW ")
                    logger.info(f"Subscription is suspended, attempting to reactivate for user ID: {pk}")
                    self.activate_paypal_subscription(user.paypal_subscription_id)
                    remove_scheduled_deletion(user.paypal_subscription_id)
                    logger.info(f"Subscription reactivated and scheduled deletion removed for user ID: {pk}")
                    return Response(
                        {"message": "Subscription updated and reactivated successfully."},
                        status=status.HTTP_200_OK,
                    )
                else:
                    logger.warning(f"Subscription for user ID: {pk} is not suspended. Cannot reactivate.")
                    return Response(
                        {"error": "Subscription not suspended"},
                        status=status.HTTP_409_CONFLICT,
                    )
            else:
                logger.error(f"No PayPal subscription found for user ID: {pk}")
                return Response(
                    {"error": "No PayPal subscription found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        except CustomUser.DoesNotExist:
            logger.error(f"User with ID {pk} not found.")
            return Response(
                {"error": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print("ERROR ", e)
            logger.error(f"An error occurred while updating subscription for user ID: {pk}: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk):
        logger.info(f"Received request to delete subscription for user ID: {pk}")
        try:
            user = CustomUser.objects.get(pk=pk)

            if user.paypal_subscription_id:
                logger.info(f"Attempting to deactivate PayPal subscription for user ID: {pk}")
                last_billing_date = self.deactivate_paypal_subscription(user.paypal_subscription_id)

                if last_billing_date:
                    # Time used for testing
                    formatted_time = (
                        datetime.now(timezone.utc) + timedelta(minutes=3)
                    ).strftime("%Y-%m-%dT%H:%M:%SZ")
                    logger.debug(f"Scheduling deletion at: {formatted_time} for testing purposes.")
                    schedule_subscription_deletion(user.paypal_subscription_id, formatted_time)
                    # Uncomment for real method with the next_billing_time
                    # schedule_subscription_deletion(user.paypal_subscription_id, last_billing_date)
                    logger.info(f"Scheduled deletion for PayPal subscription {user.paypal_subscription_id} for user ID: {pk}")

            logger.info(f"Successfully deactivated PayPal subscription for user ID: {pk}")
            return Response(
                {"message": "Subscription deactivated and deletion scheduled."},
                status=status.HTTP_204_NO_CONTENT,
            )
        except CustomUser.DoesNotExist:
            logger.error(f"User with ID {pk} not found.")
            return Response(
                {"error": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"An error occurred while deactivating subscription for user ID: {pk}: {e}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def deactivate_paypal_subscription(self, subscription_id):
        """Deactivate a PayPal subscription."""
        logger.info(f"Attempting to deactivate PayPal subscription ID: {subscription_id}")
        access_token = get_paypal_access_token()
        url = f"https://api-m.sandbox.paypal.com/v1/billing/subscriptions/{subscription_id}/suspend"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            last_billing_date = self.get_last_billing_date(subscription_id)
            user = get_user_model().objects.get(paypal_subscription_id=subscription_id)
            next_billing_time = parse_datetime(last_billing_date)

            # Ensure the datetime is timezone-aware (UTC)
            if next_billing_time and not next_billing_time.tzinfo:
                next_billing_time = pytz.utc.localize(next_billing_time)
            
            user.paypal_next_billing_time = next_billing_time
            user.save()

            logger.info(f"User {user.id} next  paypal billing time updated to {next_billing_time}")

            response = requests.post(url, headers=headers)
            if response.status_code in (200, 204):
                logger.info(f"Successfully deactivated PayPal subscription ID: {subscription_id}")
                return last_billing_date
            else:
                logger.error(f"Failed to deactivate PayPal subscription ID: {subscription_id} - {response.text}")
                raise Exception(
                    f"Failed to deactivate PayPal subscription {subscription_id}: {response.text}"
                )
        except Exception as e:
            logger.error(f"An error occurred during PayPal subscription deactivation: {e}")
            raise

    def activate_paypal_subscription(self, subscription_id):
        """Reactivate a PayPal subscription."""
        logger.info(f"Attempting to reactivate PayPal subscription ID: {subscription_id}")
        access_token = get_paypal_access_token()
        url = f"https://api-m.sandbox.paypal.com/v1/billing/subscriptions/{subscription_id}/activate"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(url, headers=headers)
            if response.status_code not in (200, 204):
                logger.error(f"Failed to reactivate PayPal subscription ID: {subscription_id} - {response.text}")
                raise Exception(
                    f"Failed to activate PayPal subscription {subscription_id}: {response.text}"
                )
            logger.info(f"Successfully reactivated PayPal subscription ID: {subscription_id}")
            return response.status_code == 204
        except Exception as e:
            logger.error(f"An error occurred during PayPal subscription reactivation: {e}")
            raise

    def get_last_billing_date(self, subscription_id):
        """Retrieve the last billing date from a PayPal subscription."""
        logger.info(f"Fetching last billing date for PayPal subscription ID: {subscription_id}")
        access_token = get_paypal_access_token()
        url = f"https://api-m.sandbox.paypal.com/v1/billing/subscriptions/{subscription_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                subscription_details = response.json()
                last_billing_date = subscription_details.get("billing_info", {}).get(
                    "next_billing_time"
                )  # Adjust depending on actual response structure
                logger.info(f"Retrieved last billing date for PayPal subscription ID: {subscription_id}: {last_billing_date}")
                return last_billing_date
            else:
                logger.error(f"Failed to retrieve subscription details for ID: {subscription_id} - {response.text}")
                raise Exception(f"Failed to retrieve subscription details: {response.text}")
        except Exception as e:
            logger.error(f"An error occurred while retrieving last billing date for PayPal subscription ID: {subscription_id}: {e}")
            raise


class PricesListView(APIView):

    def get(self, request):
        # extract pagination parameters from query params
        try:
            # Retrieve only active products from Stripe
            active_products = stripe.Product.list(active=True)

            products = active_products.data
            # Iterate through the list of active products
            for product in products:
                # Retrieve the price details using the default_price ID
                if product.default_price:
                    data_json_product = stripe.Price.retrieve(product.default_price)
                    # Append price and currency to each product's dictionary
                    product["price"] = data_json_product.unit_amount
                    product["currency"] = data_json_product.currency

            # Convert the list of products to JSON string
            json_str = json.dumps(products)
            logger.info("Retrieved product prices successfully.")
            return Response(json_str, status=status.HTTP_200_OK)
        except Exception as e:
            # Log the error and return a 500 Internal Server Error response
            logger.error("Failed to retrieve product prices", exc_info=True)
            return Response(
                {"errors": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
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
            logger.error(
                f"Failed to create or attach payment method: {e}", exc_info=True
            )
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
            logger.error(
                f"Failed to update default payment method for user {user.id}: {e}",
                exc_info=True,
            )
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
            response = {}

            if hasattr(user, "stripe_subscription_id") and user.stripe_subscription_id:
                # Retrieve the customer's Stripe subscription
                subscription = stripe.Subscription.retrieve(user.stripe_subscription_id)
                product = stripe.Product.retrieve(subscription.plan.product)

                response.update(
                    {
                        "subscription_id": subscription.id,
                        "status": subscription.status,
                        "current_period_end": subscription.current_period_end,
                        "product_price": subscription.plan.amount,
                        "product_name": product.name,
                        "cancel_at_period_end": subscription.cancel_at_period_end,
                        "subscription_type": "stripe",
                    }
                )

                if subscription.status == "trialing":
                    response.update(
                        {
                            "trial_start": subscription.trial_start,
                            "trial_end": subscription.trial_end,
                        }
                    )

                logger.info(f"Stripe subscription details retrieved for user {user.id}")

            elif (
                hasattr(user, "paypal_subscription_id") and user.paypal_subscription_id
            ):
                # Retrieve the customer's PayPal subscription
                paypal_subscription = get_paypal_subscription(
                    user.paypal_subscription_id
                )
                plan = SubscriptionPlan.objects.get(
                    paypal_plan_id=paypal_subscription["plan_id"]
                )
                cancel_at_period_end = False
                if paypal_subscription["status"] == "SUSPENDED":
                    cancel_at_period_end = True

                next_billing_time = paypal_subscription.get("billing_info", {}).get(
                    "next_billing_time", user.paypal_next_billing_time
                )
                last_payment_amount = (
                    paypal_subscription.get("billing_info", {})
                    .get("last_payment", {})
                    .get("amount", {})
                    .get("value", "")
                )

                response.update(
                    {
                        "subscription_id": paypal_subscription["id"],
                        "status": paypal_subscription["status"],
                        "current_period_end": next_billing_time,
                        "product_price": last_payment_amount,
                        "product_name": plan.name,
                        "cancel_at_period_end": cancel_at_period_end,
                        "subscription_type": "paypal",
                    }
                )

                logger.info(f"PayPal subscription details retrieved for user {user.id}")

            if not response:
                return Response(
                    {"message": "No subscription information available."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            return Response(response, status=status.HTTP_200_OK)

        except get_user_model().DoesNotExist:
            logger.error(f"User with ID {pk} not found.")
            return Response(
                {"message": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except (
            Exception
        ) as e:  # This catches any other exceptions including Stripe and PayPal specific ones
            logger.error(
                f"Error while retrieving subscription for user {user.id}: {e}",
                exc_info=True,
            )
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
            logger.error(
                f"Stripe error while creating subscription for user {user.id}: {e}",
                exc_info=True,
            )
            return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(
                f"Unexpected error while creating subscription: {e}", exc_info=True
            )
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, pk):
        try:
            user = get_user_model().objects.get(id=pk)
            subscription_id = user.stripe_subscription_id

            if not subscription_id:
                logger.warning(
                    f"Attempt to cancel non-existent subscription for user {user.id}"
                )
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
            logger.error(
                f"Stripe error while cancelling subscription for user {user.id}: {e}",
                exc_info=True,
            )
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def patch(self, request, pk):
        try:
            user = get_user_model().objects.get(id=pk)
            subscription_id = user.stripe_subscription_id

            if not subscription_id:
                logger.warning(
                    f"No subscription_id provided for update for user {user.id}"
                )
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
            logger.error(
                f"Stripe error while updating subscription for user {user.id}: {e}",
                exc_info=True,
            )
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

        # Send the event to be processed by Celery
        process_payment_event.delay(payload_data)
        logger.info(f"Event {event.id} sent to Celery")

        return Response(status=200)


@csrf_exempt
@require_POST
def paypal_webhook(request):
    try:
        # Load the JSON data sent from PayPal
        event = json.loads(request.body.decode("utf-8"))

        if verify_paypal_webhook_signature(request):
            logger.info(
                f"Verified PayPal event: {event['event_type']}, ID: {event.get('id', 'No ID')}"
            )

            process_payment_event.delay(event)

            return HttpResponse(status=200)
        else:
            logger.error("Failed to verify PayPal webhook signature.")
            return JsonResponse({"error": "Failed to verify signature"}, status=403)

    except Exception as e:
        logger.error(f"Error processing PayPal webhook: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)
