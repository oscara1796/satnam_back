import logging
import os

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
from dotenv import load_dotenv
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import (TokenObtainPairView,
                                            TokenRefreshView)

from payments.models import SubscriptionPlan
from payments.views import SubscriptionPlanAPIView
from satnam.settings import EMAIL_HOST_USER

from .models import TrialDays
from .serializers import LogInSerializer, TrialDaysSerializer, UserSerializer

load_dotenv(".env.dev")
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

logger = logging.getLogger("django")


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
            logger.warning(
                "User registration failed due to invalid data.",
                extra={"request_data": request.data, "errors": serializer.errors},
            )
            errors = {"message": serializer.errors}
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            logger.info(
                "New user registered successfully.",
                extra={"user_id": serializer.data.get("id", "Unknown")},
            )
            return Response(
                serializer.data, status=status.HTTP_201_CREATED, headers=headers
            )
        except Exception:
            logger.error("Unexpected error during user registration", exc_info=True)
            return Response(
                {"message": "An unexpected error occurred during user registration."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
            logger.error(f"Login error: {str(e)}", exc_info=True)
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
        except get_user_model().DoesNotExist:
            logger.info(
                "Intento de restablecimiento de contraseña para usuario inexistente"
            )
            return Response(
                {"message": "No se encontró ningún usuario con el ID proporcionado."},
                status=status.HTTP_404_NOT_FOUND,
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
            logger.warning("Intento de decodificación de UID inválido", exc_info=True)
            return Response(
                {
                    "message": "ID de usuario no válido. Por favor, revise su solicitud y vuelva a intentarlo."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except get_user_model().DoesNotExist:
            logger.info(
                "Intento de restablecimiento de contraseña para usuario inexistente"
            )
            return Response(
                {"message": "No se encontró ningún usuario con el ID proporcionado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.error(
                "Error inesperado durante el restablecimiento de contraseña",
                exc_info=True,
            )
            return Response(
                {
                    "message": "Ocurrió un error inesperado. Por favor, intente de nuevo más tarde."
                },
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
        else:
            errors = {"message": serializer.errors}
            logger.error(f"Update user failed: {errors}")
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        user = get_user_model().objects.get(id=pk)

        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            errors = {"message": serializer.errors}
            logger.error(f"Partial update user failed: {errors}")
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        try:
            user = get_user_model().objects.get(id=pk)
            stripe_response = stripe.Customer.delete(user.stripe_customer_id)
            if not stripe_response["deleted"]:
                raise Exception("Stripe could not delete customer")
            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Error deleting user: {str(e)}", exc_info=True)
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
            logger.error(f"TrialDay with pk={pk} not found.")
            raise Http404

    def get(self, request, pk=None, format=None):
        if pk:
            try:
                trial_day = self.get_object(pk)
                serializer = TrialDaysSerializer(trial_day)
                return Response(serializer.data)
            except Http404:
                return Response(
                    {"error": "TrialDay not found"}, status=status.HTTP_404_NOT_FOUND
                )
        else:
            trial_days = TrialDays.objects.all()
            serializer = TrialDaysSerializer(trial_days, many=True)
            logger.info("Retrieved all trial days.")
            return Response(serializer.data)

    def post(self, request, format=None):
        serializer = TrialDaysSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info("Created a new trial day.")

            # Update trial days in all existing subscription plans
            self.update_subscription_plans_with_trial_days(
                serializer.validated_data["days"]
            )

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            logger.warning(f"Failed to create a new trial day: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk, format=None):
        trial_day = self.get_object(pk)
        serializer = TrialDaysSerializer(trial_day, data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Updated trial day with pk={pk}.")

            # Update trial days in all existing subscription plans
            self.update_subscription_plans_with_trial_days(
                serializer.validated_data["days"]
            )

            return Response(serializer.data)
        else:
            logger.warning(
                f"Failed to update trial day with pk={pk}: {serializer.errors}"
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        trial_day = self.get_object(pk)
        try:
            trial_day.delete()
            logger.info(f"Deleted trial day with pk={pk}.")

            # Set trial days to zero in all existing subscription plans
            self.update_subscription_plans_with_trial_days(0)

            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(
                f"Failed to delete trial day with pk={pk}: {str(e)}", exc_info=True
            )
            return Response(
                {"error": "An error occurred while deleting the trial day."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def update_subscription_plans_with_trial_days(self, days):
        subscription_plans = SubscriptionPlan.objects.all()
        subscription_plan_api_view = SubscriptionPlanAPIView()
        for plan in subscription_plans:
            subscription_plan_api_view.update_trial_days(plan.pk, days)
