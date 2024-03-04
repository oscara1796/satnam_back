import stripe
from django.conf import settings
from django.contrib.auth import get_user_model

# Create your views here.
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.http import Http404
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django_ratelimit.decorators import ratelimit
from dotenv import dotenv_values
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from satnam.settings import EMAIL_HOST_USER

from .models import TrialDays
from .serializers import LogInSerializer, TrialDaysSerializer, UserSerializer

env_vars = dotenv_values(".env.dev")
stripe.api_key = env_vars["STRIPE_SECRET_KEY"]


def conditional_ratelimit(*args, **kwargs):
    def decorator(func):
        if settings.TESTING:
            return func
        return ratelimit(*args, **kwargs)(func)

    return decorator


@conditional_ratelimit(key="ip", rate="5/m", method="POST", block=True)
def rate_limit_check(request):
    pass


@method_decorator(
    conditional_ratelimit(key="ip", rate="5/m", method="POST", block=True),
    name="dispatch",
)
class SignUpView(generics.CreateAPIView):
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            # Here you can customize the error response
            errors = {"message": serializer.errors}
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        # If the serializer is valid, proceed as normal
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


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
            print("HELLO", e.detail)
            return Response(
                {
                    "message": "No se encontró una cuenta activa con las credenciales proporcionadas."
                },
                status=401,
            )


class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        print("Request data:", request.data)
        response = super().post(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # Fetch updated model data based on user (replace this with your logic)
            access_token = response.data["access"]
            decoded_access_token = RefreshToken(access_token, verify=False)

            user_id = decoded_access_token.payload.get(
                "id"
            )  # Replace 'user_id' with the actual key used in your token payload
            if user_id is not None:
                user_active = get_user_model().objects.get(id=user_id).active

                # Update the payload of the decoded access token
                decoded_access_token.payload["active"] = user_active

                # Re-encode the access token with the modified payload
                modified_access_token = str(decoded_access_token)

                # Update the response data with the modified access token
                response.data["access"] = modified_access_token

        return response


class PasswordResetRequestView(APIView):
    def post(self, request, *args, **kwargs):
        email = request.data.get("email")
        user_model = get_user_model()
        try:
            user = user_model.objects.get(email=email)
            # Generate a one-time use token and UID
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_link = f"http://192.168.100.162:3001/#/reset-password/{uid}/{token}"

            # Send email to user with password reset link
            send_mail(
                "[Sat Nam Yoga] Solicitud de restablecimiento de contraseña",
                f"Por favor vaya al siguiente enlace para restablecer su contraseña: {reset_link}",
                EMAIL_HOST_USER,
                [email],
                fail_silently=False,
            )
            return Response(
                {
                    "message": "Si existe una cuenta con el correo electrónico, se ha enviado un enlace para restablecer la contraseña"
                },
                status=status.HTTP_200_OK,
            )
        except user_model.DoesNotExist:
            # For privacy reasons, do not reveal whether or not the email exists in the system
            return Response(
                {
                    "message": "Si existe una cuenta con el correo electrónico, se ha enviado un enlace para restablecer la contraseña"
                },
                status=status.HTTP_200_OK,
            )


class PasswordResetConfirmView(APIView):
    def post(self, request, uidb64, token, *args, **kwargs):
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = get_user_model().objects.get(pk=uid)

            if default_token_generator.check_token(user, token):
                user.set_password(request.data.get("password"))
                user.save()
                return Response(
                    {"message": "Your password has been reset successfully."},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"message": "Invalid token or user ID."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError:
            # Handle the case where urlsafe_base64_decode() raises a ValueError
            return Response(
                {
                    "message": "Invalid user ID. Please check your request and try again."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except get_user_model().DoesNotExist:
            # Handle the case where no user matches the provided UID
            return Response(
                {"message": "No user found with the provided user ID."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            # Log or handle unexpected exceptions here
            # Consider logging the exception to help with debugging
            # print(e)
            return Response(
                {"message": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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

        errors = {"message": serializer.errors}
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        try:
            user = get_user_model().objects.get(id=pk)
            stripe_response = stripe.Customer.delete(user.stripe_customer_id)
            # print(stripe_response)
            if not stripe_response["deleted"]:
                raise Exception("Stripe could not delete customer")
            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            print(e)
            return Response(
                data={"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class IsStaffOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if (
            request.method in permissions.SAFE_METHODS
        ):  # Allow GET, HEAD, OPTIONS requests
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
                return Response(
                    {"error": "TrialDay not found"}, status=status.HTTP_404_NOT_FOUND
                )
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
