
from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, viewsets, status
# Create your views here.
from rest_framework_simplejwt.views import TokenObtainPairView 
from .serializers import  LogInSerializer,UserSerializer
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
import stripe
from dotenv import dotenv_values


env_vars = dotenv_values(".env.dev")
stripe.api_key = env_vars["STRIPE_SECRET_KEY"]


class SignUpView(generics.CreateAPIView):
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer


class LogInView(TokenObtainPairView):
    serializer_class = LogInSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            # Perform any additional actions you need to do here
            return Response(serializer.validated_data)
        except Exception as e:
            # print("HELLO",e.detail)
            return Response({'errors': e.detail}, status=401)

class UserDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        user = get_user_model().objects.get(id=pk)
        serializer = UserSerializer(user)
        return Response(serializer.data)

    def put(self, request, *args, **kwargs):
        user = self.request.user
        serializer = UserSerializer(user, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        try:
            user = get_user_model().objects.get(id=pk)
            stripe_response =stripe.Customer.delete(user.stripe_customer_id)
            # print(stripe_response)
            if stripe_response["deleted"] != True:
                raise Exception("Stripe couldn´t delete customer")
            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            print(e)
            return Response(data={'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
