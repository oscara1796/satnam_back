
from rest_framework.response import Response
from .models import Event
from .serializers import EventSerializer
from rest_framework import viewsets, status, permissions


class IsStaffOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:  # Allow GET, HEAD, OPTIONS requests
            return True
        return request.user.is_staff

class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsStaffOrReadOnly]

    def create(self, request, *args, **kwargs):
        # Initial validation of the incoming data
        if isinstance(request.data, list):
            # Bulk creation case
            serializer = self.get_serializer(data=request.data, many=True)
        else:
            # Single creation case
            serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        # Data is valid, so now we can safely delete old events
        Event.objects.all().delete()

        # Perform the creation of new events
        self.perform_create(serializer)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
