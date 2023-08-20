from django.shortcuts import render, redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.core.mail import send_mail
from .serializers import PaymentMethodSerializer, StripePriceSerializer
import stripe
from stripe.error import StripeError
from dotenv import dotenv_values
import json
from django.conf import settings


env_vars = dotenv_values(".env.dev")
stripe.api_key = env_vars["STRIPE_SECRET_KEY"]
# Create your views here.
FRONTEND_SUBSCRIPTION_SUCCESS_URL = settings.SUBSCRIPTION_SUCCESS_URL
FRONTEND_SUBSCRIPTION_CANCEL_URL = settings.SUBSCRIPTION_FAILED_URL

webhook_secret = settings.STRIPE_WEBHOOK_SECRET


class PaymentList(APIView):
    permission_classes = [permissions.IsAuthenticated]
    # def get(self, request):
    #     # extract pagination parameters from query params
    #     page = int(request.query_params.get('page', 1))
    #     page_size = int(request.query_params.get('page_size', 10))

       
        
    #     # calculate start and end indices based on pagination parameters
    #     start_index = (page - 1) * page_size
    #     end_index = start_index + page_size
    #     videos = None
    #     # query the database for videos
    #     if self.request.user.active or self.request.user.is_staff:
    #         # print("active", self.request.user.username)
    #         videos = Video.objects.all()[start_index:end_index]
    #     else:
    #         # print("inactive", self.request.user.username)
    #         videos = Video.objects.filter(free=True)[start_index:end_index]
        
    #     # serialize the videos and return them as a response
    #     serializer = VideoSerializer(videos, many=True)
        
    #     return Response({
    #         'total_count': Video.objects.all().count(),
    #         'count': len(videos),
    #         'results': serializer.data,
    #     })


class PricesListView(APIView):


    def get(self, request):
        # extract pagination parameters from query params
        try:
            data = stripe.Product.list()
            json_str = json.dumps(data.data)
            return Response(json_str, status=200)
        except:
            print("HELLO",e)
            return Response({'errors': e}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


class SubscriptionDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self , request):
        data = request.data
        try:
            checkout_session = stripe.checkout.Session.create(
                line_items = [
                    {
                   'price' : data['price_id'],
                   'quantity' : 1
                    }
                ],
                mode = 'subscription',        
                success_url = FRONTEND_SUBSCRIPTION_SUCCESS_URL +"?session_id={CHECKOUT_SESSION_ID}",
                cancel_url = FRONTEND_SUBSCRIPTION_CANCEL_URL
            )
            return redirect(checkout_session.url , code=303)
        except Exception as err:
            return Response({'errors': err}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class PaymentDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            user = get_user_model().objects.get(id=pk)
            
            # Retrieve the customer's Stripe subscription
            subscription = stripe.Subscription.retrieve(user.stripe_subscription_id)

            product = stripe.Product.retrieve(subscription.plan.product)

            # print(subscription)
            # Return the subscription details
            return Response({
                'subscription_id': subscription.id,
                'status': subscription.status,
                'current_period_end': subscription.current_period_end,
                'product_price': subscription.plan.amount,
                'product_name': product.name,
                'cancel_at_period_end': subscription.cancel_at_period_end,
            }, status=status.HTTP_200_OK)
        except get_user_model().DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        except StripeError as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
    def post(self, request, pk):
        try:
            serializer = PaymentMethodSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data
            
            payment_method = stripe.PaymentMethod.create(
                type='card',
                card=validated_data,
            )
            user = get_user_model().objects.get(id=pk)

            stripe.PaymentMethod.attach(
                payment_method.id,
                customer=user.stripe_customer_id,
            )

            stripe.Customer.modify(
                user.stripe_customer_id,
                invoice_settings={
                    'default_payment_method': payment_method.id,
                },
            )
            # Create a subscription for the customer
            subscription = stripe.Subscription.create(
                customer=user.stripe_customer_id,
                items=[
                    {'price': settings.STRIPE_SUBSCRIPTION_PRICE_ID}  # Stripe subscription price identifier
                ],
                # Additional subscription options (e.g., trial period, metadata)
            )

            user.active  = True
            user.save()
            user.stripe_subscription_id = subscription.id
            user.save()

            # Return the customer's Stripe customer ID and subscription details
            return Response({
                'stripe_customer_id': user.stripe_customer_id,
                'subscription_id': subscription.id,
                'status': subscription.status,
                'is_active': user.active
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            print("HELLO",e)
            return Response({'errors': e.detail}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def delete(self, request, pk):
        try:
            user = get_user_model().objects.get(id=pk)
            subscription_id = user.stripe_subscription_id

            if not subscription_id:
                return Response({'error': 'Missing subscription_id in request data'}, status=status.HTTP_400_BAD_REQUEST)

            stripe.Subscription.delete(subscription_id)

            user.active  = False 

            user.save()

            # Additional cleanup or updates if needed
            # ...

            return Response({'success': 'Subscription canceled'}, status=status.HTTP_200_OK)
        except get_user_model().DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except StripeError as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class StripeWebhookView(APIView):
    def post(self, request, *args, **kwargs):
        payload = request.body
        event = None

        try:
            event = stripe.Event.construct_from(
                payload, stripe.api_key
            )
        except ValueError as e:
            # Invalid payload
            return JsonResponse({'error': str(e)}, status=400)

        # Handle the event based on its type
        if event.type == 'invoice.paid':
            invoice = event.data.object
            customer_id = invoice.customer

            # Retrieve customer's email from your database
            customer_email = self.get_customer_email(customer_id)
            if customer_email:
                self.send_invoice_email(customer_email, invoice)
        
        elif event.type == 'invoice.payment_failed':
            invoice = event.data.object
            customer_id = invoice.customer
            
            # Retrieve customer's email from your database
            customer_email = self.get_customer_email(customer_id)
            if customer_email:
                self.send_payment_failed_email(customer_email, invoice)

        
        elif event.type == "customer.subscription.updated":
            """
            Occurs whenever a subscription changes (e.g., switching from one plan to another, or changing the status from trial to active).
            """
            pass
        
        elif event.type == "customer.subscription.deleted":
            pass

        elif event.type == "customer.subscription.trial_will_end":
            """
            Occurs three days before a subscription’s trial period is scheduled to end, or when a trial is ended immediately (using trial_end=now).
            """
            pass

        return Response(status=200)

    def get_customer_email(self, customer_id):
        # Implement logic to retrieve customer's email from your database
        # For example:
        # customer = YourCustomerModel.objects.get(stripe_customer_id=customer_id)
        # return customer.email
        pass

    def send_invoice_email(self, customer_email, invoice):
        subject = 'Invoice Notification'
        message = f'Hello,\n\nYour invoice has been paid. Invoice ID: {invoice.id}\nAmount: {invoice.amount_due / 100} {invoice.currency}'
        from_email = 'your@example.com'  # Replace with your email address
        recipient_list = [customer_email]

        send_mail(subject, message, from_email, recipient_list)
        
    def send_payment_failed_email(self, customer_email, invoice):
        subject = 'Payment Failed Notification'
        message = f'Hello,\n\nYour payment for Invoice ID: {invoice.id} has failed.\nPlease update your payment information or contact support.'
        from_email = 'your@example.com'  # Replace with your email address
        recipient_list = [customer_email]

        send_mail(subject, message, from_email, recipient_list)
