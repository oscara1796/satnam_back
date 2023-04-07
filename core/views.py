
from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, viewsets, status
# Create your views here.
from rest_framework_simplejwt.views import TokenObtainPairView 
from .serializers import  LogInSerializer,UserSerializer
from rest_framework.response import Response
from rest_framework.views import APIView


class SignUpView(generics.CreateAPIView):
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer


class LogInView(TokenObtainPairView):
    serializer_class = LogInSerializer

class UserDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = self.request.user
        serializer = UserSerializer(user)
        return Response(serializer.data)

    def put(self, request, *args, **kwargs):
        user = self.request.user
        serializer = UserSerializer(user, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)