from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Video, Category
from .serializers import VideoSerializer, CategorySerializer

class IsStaffOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:  # Allow GET, HEAD, OPTIONS requests
            return True
        return request.user.is_staff

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
                # Check if 'categories' data is present in the request
                category_data = request.data.get('categories', [])
                if category_data:
                    # Validate and create categories
                    category_serializer = CategorySerializer(data=category_data, many=True)
                    category_serializer.is_valid(raise_exception=True)
                    categories = category_serializer.save()
                else:
                    # If no category data provided, create an empty list
                    categories = []

                # Create a video with associated categories
                video_data = request.data.copy()
                video_data.pop('categories', None)  # Remove 'categories' from video data
                video_serializer = VideoSerializer(data=video_data)
                video_serializer.is_valid(raise_exception=True)
                video = video_serializer.save()

                # Add the categories to the video
                video.video_categories.set(categories)

                return Response(VideoSerializer(video).data, status=status.HTTP_201_CREATED)
            return Response("Unauthorized", status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'errors': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def patch(self, rerquest, pk):
        video = Video.objects.get(id=pk)

        

class CategoryAPIView(APIView):

    permission_classes = [IsStaffOrReadOnly]
    def get(self, request):
        categories = Category.objects.all()
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        category = self.get_object(pk)
        serializer = CategorySerializer(category, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        category = self.get_object(pk)
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_object(self, pk):
        try:
            return Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            raise status.HTTP_404_NOT_FOUND
    
    def patch(self, request, pk):
        category = self.get_object(pk)
        
        # Check if the request data is a list of videos or a single video
        is_many = isinstance(request.data, list)
        print(request.data)
        serializer = VideoSerializer(data=request.data, many=is_many)
        
        if serializer.is_valid():
            if is_many:
                videos = serializer.save()
                category.category_videos.add(*videos)  # Add multiple videos to the category
            else:
                video = serializer.save()
                category.category_videos.add(video)  # Add a single video to the category
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        print(serializer.errors)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LinkCategoryVideoAPIView(APIView):
    def post(self, request, category_id, video_id):
        try:
            category = Category.objects.get(id=category_id)
            video = Video.objects.get(id=video_id)
        except (Category.DoesNotExist, Video.DoesNotExist):
            return Response(status=status.HTTP_404_NOT_FOUND)

        category.category_videos.add(video)
        return Response(status=status.HTTP_200_OK)