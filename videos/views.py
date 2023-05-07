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
        if self.request.user.active or self.request.user.is_staff:
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
        try:
            video = Video.objects.get(id=pk)
            if self.request.user.active or self.request.user.is_staff or video.free:
                serializer = VideoSerializer(video)
                return Response(serializer.data)
            return Response("Unauthorized", status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response(data={'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request, pk):
        video = Video.objects.get(id=pk)
        serializer = VideoSerializer(video, data=request.data)

       
        if self.request.user.is_staff and serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        # print(serializer.errors)
        return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)
    
    def delete(self, request, pk):
        try:
            if self.request.user.is_staff:
                video = Video.objects.get(id=pk)
                video.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response("Unauthorized", status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response(data={'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request, *args, **kwargs):
        
        try:
            if self.request.user.is_staff:
                serializer = VideoSerializer(data=request.data) 

                serializer.is_valid(raise_exception=True)
                video = serializer.save()

                return Response(VideoSerializer(video).data, status=201)
            return Response("Unauthorized", status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            print("HELLO",e)
            return Response({'errors': e.detail}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)