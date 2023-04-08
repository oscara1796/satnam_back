from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Video
from .serializers import VideoSerializer

class VideoList(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        # extract pagination parameters from query params
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))

       
        
        # calculate start and end indices based on pagination parameters
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        videos = None
        # query the database for videos
        if self.request.user.active:
            # print("active", self.request.user.username)
            videos = Video.objects.all()[start_index:end_index]
        else:
            # print("inactive", self.request.user.username)
            videos = Video.objects.filter(free=True)[start_index:end_index]
        
        # serialize the videos and return them as a response
        serializer = VideoSerializer(videos, many=True)
        
        return Response({
            'total_count': Video.objects.all().count(),
            'count': len(videos),
            'results': serializer.data,
        })
    

class VideoDetail(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, pk):
        if self.request.user.active:
            video = Video.objects.get(id=pk)
            serializer = VideoSerializer(video)
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)