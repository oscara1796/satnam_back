from rest_framework import viewsets
from rest_framework.response import Response
from .models import Event
from .serializers import EventSerializer
from rest_framework import viewsets, permissions

class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAdminUser]

    # def create(self, request, *args, **kwargs):
    #     if Event.objects.exists():
    #         # If an instance already exists, update it instead of creating a new one
    #         return self.update(request, *args, **kwargs)
    #     return super(EventViewSet, self).create(request, *args, **kwargs)

    # def update(self, request, *args, **kwargs):
    #     # Ensure there is only one instance
    #     event, created = Event.objects.get_or_create(pk=1)
    #     serializer = self.get_serializer(event, data=request.data)
    #     serializer.is_valid(raise_exception=True)
    #     self.perform_update(serializer)

    #     if getattr(event, '_prefetched_objects_cache', None):
    #         # If 'prefetch_related' has been applied to a queryset, we need to forcibly invalidate the prefetch cache on the instance.
    #         event._prefetched_objects_cache = {}

    #     return Response(serializer.data)
