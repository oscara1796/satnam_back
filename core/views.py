
from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, viewsets, status
# Create your views here.
from rest_framework_simplejwt.views import TokenObtainPairView 
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import  LogInSerializer,UserSerializer
from rest_framework.response import Response
from rest_framework import status
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
            print("HELLO",e.detail)
            return Response({'errors': "No se encontró una cuenta activa con las credenciales proporcionadas."}, status=401)
        

class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        print("Request data:", request.data)
        response = super().post(request, *args, **kwargs)

        
        
        if response.status_code == status.HTTP_200_OK:
            # Fetch updated model data based on user (replace this with your logic)
            access_token = response.data['access']
            decoded_access_token = RefreshToken(access_token, verify=False)
            
            user_id = decoded_access_token.payload.get('id')  # Replace 'user_id' with the actual key used in your token payload
            if user_id is not None:
                user_active = get_user_model().objects.get(id=user_id).active

                # Update the payload of the decoded access token
                decoded_access_token.payload['active'] = user_active

                # Re-encode the access token with the modified payload
                modified_access_token = str(decoded_access_token)
            
                # Update the response data with the modified access token
                response.data['access'] = modified_access_token
                
                
        
        return response

class UserDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        user = get_user_model().objects.get(id=pk)
        serializer = UserSerializer(user)
        return Response(serializer.data)

    def put(self, request, pk):
        user = get_user_model().objects.get(id=pk)
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
    
