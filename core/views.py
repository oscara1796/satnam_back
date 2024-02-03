
from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, viewsets, status
# Create your views here.
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from satnam.settings import DEFAULT_FROM_EMAIL
from rest_framework_simplejwt.views import TokenObtainPairView 
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import  LogInSerializer,UserSerializer
from rest_framework.response import Response
from rest_framework import status,permissions
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
import stripe
from dotenv import dotenv_values
from .models import TrialDays
from .serializers import TrialDaysSerializer
from django.http import Http404
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_text
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.urls import reverse



env_vars = dotenv_values(".env.dev")
stripe.api_key = env_vars["STRIPE_SECRET_KEY"]




@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def rate_limit_check(request):
    pass

@method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=True), name='dispatch')
class SignUpView(generics.CreateAPIView):
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            # Here you can customize the error response
            errors = {'message': serializer.errors}
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
        # If the serializer is valid, proceed as normal
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class LogInView(TokenObtainPairView):
    serializer_class = LogInSerializer
    

    def post(self, request, *args, **kwargs):

        # Perform rate limit check
        rate_limit_check(request)
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            # Perform any additional actions you need to do here
            return Response(serializer.validated_data)
        except Exception as e:
            print("HELLO",e.detail)
            return Response({'message': "No se encontró una cuenta activa con las credenciales proporcionadas."}, status=401)
        

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
    
class PasswordResetRequestView(views.APIView):
    def post(self, request, *args, **kwargs):
        email = request.data.get("email")
        user_model = get_user_model()
        try:
            user = user_model.objects.get(email=email)
            # Generate a one-time use token and UID
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_link = request.build_absolute_uri(reverse('password-reset-confirm', kwargs={'uidb64': uid, 'token': token}))
            
            # Send email to user with password reset link
            send_mail(
                'Password Reset Request',
                f'Please go to the following link to reset your password: {reset_link}',
                DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            return Response({"message": "If an account with the email exists, a password reset link has been sent."}, status=status.HTTP_200_OK)
        except user_model.DoesNotExist:
            # For privacy reasons, do not reveal whether or not the email exists in the system
            return Response({"message": "If an account with the email exists, a password reset link has been sent."}, status=status.HTTP_200_OK)

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
        
        errors = {'message': serializer.errors}
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)
    
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
            return Response(data={'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IsStaffOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:  # Allow GET, HEAD, OPTIONS requests
            return True
        return request.user.is_staff

class TrialDaysDetail(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get_object(self, pk):
        try:
            return TrialDays.objects.get(pk=pk)
        except TrialDays.DoesNotExist:
            raise Http404

    def get(self, request, pk=None, format=None):
        if pk:
            trial_day = self.get_object(pk)
            if trial_day is not None:
                serializer = TrialDaysSerializer(trial_day)
            else:
                # If pk is provided but the object is not found, return an empty response or error
                return Response({"error": "TrialDay not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            # If no pk is provided, return all trial days
            trial_days = TrialDays.objects.all()
            serializer = TrialDaysSerializer(trial_days, many=True)

        return Response(serializer.data)
    
    def post(self, request, format=None):
        serializer = TrialDaysSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk, format=None):
        trial_day = self.get_object(pk)
        serializer = TrialDaysSerializer(trial_day, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        trial_day = self.get_object(pk)
        trial_day.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

