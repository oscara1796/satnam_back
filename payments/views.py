from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from .serializers import PaymentMethodSerializer, StripePriceSerializer
import stripe
from dotenv import dotenv_values
import json


env_vars = dotenv_values(".env.dev")
stripe.api_key = env_vars["STRIPE_SECRET_KEY"]
# Create your views here.


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


    def post(self, request, pk):
        try:
            serializer = StripePriceSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            price_id = serializer.validated_data['price_id']

            user = get_user_model().objects.get(id=pk)
            
            

            subscription = stripe.Subscription.create(
                customer=user.stripe_customer_id,
                items=[
                    {
                        'price': price_id,  # Price ID of the subscription plan
                    },
                ],
            )

            user.stripe_subscription_id = subscription.id 
            user.save()

            json_str = json.dumps(subscription)
            
            response_data = {
                'status': 'success',
                'data': json_str,
            }

            return Response(response_data, status=201)
        except Exception as e:
            print("HELLO",e)
            return Response({'errors': e}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class PaymentDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    # def get(self, request, pk):
    #     user = get_user_model().objects.get(id=pk)
    #     serializer = UserSerializer(user)
    #     return Response(serializer.data)
    
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
            json_str = json.dumps(payment_method)
            
            response_data = {
                'status': 'success',
                'data': json_str,
            }

            return Response(response_data, status=201)
        except Exception as e:
            print("HELLO",e)
            return Response({'errors': e.detail}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # def put(self, request, *args, **kwargs):
    #     user = self.request.user
    #     serializer = UserSerializer(user, data=request.data)
    #     if serializer.is_valid():
    #         serializer.save()
    #         return Response(serializer.data)
        
        
    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    # def delete(self, request, pk):
    #     try:
    #         user = get_user_model().objects.get(id=pk)
    #         user.delete()
    #         return Response(status=status.HTTP_204_NO_CONTENT)
    #     except Exception as e:
    #         return Response(data={'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)