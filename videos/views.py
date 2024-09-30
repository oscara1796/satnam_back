import json
import logging

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Category, Video
from .serializers import CategorySerializer, VideoSerializer

logger = logging.getLogger(__name__)


def paginate_queryset(queryset, request):
    # Extract pagination parameters from query params
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 10))

    # Calculate start and end indices based on pagination parameters
    start_index = (page - 1) * page_size
    end_index = start_index + page_size

    # Slice the queryset based on start and end indices
    paginated_queryset = queryset[start_index:end_index]

    return paginated_queryset


class IsStaffOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        logger.info(f"Permission Check - Request method: {request.method}")
        if request.method in permissions.SAFE_METHODS:
            logger.info("Permission Granted: Safe method.")
            return True
        is_staff = request.user.is_staff
        logger.info(f"Permission Granted: Is user staff? {is_staff}")
        return is_staff


class VideoList(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request):
        logger.info("VideoList.get called")
        try:
            search_query = request.query_params.get("search", None)
            category_id = request.query_params.get("category", None)
            logger.info(f"search_query: {search_query}, category_id: {category_id}")
            queryset = Video.objects.all()

            if search_query:
                queryset = queryset.filter(title__icontains=search_query)

            if category_id:
                queryset = queryset.filter(categories__id=category_id)

            paginated_queryset = paginate_queryset(queryset, request)
            serializer = VideoSerializer(paginated_queryset, many=True, context={'request': request})

            return Response(
                {
                    "total_count": queryset.count(),
                    "count": len(paginated_queryset),
                    "results": serializer.data,
                }
            )

        except Exception as e:
            logger.error(f"Error in VideoList GET: {str(e)}")
            return Response(
                data={"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SearchVideoAPIView(APIView):
    def get(self, request, *args, **kwargs):
        try:
            search_query = request.query_params.get("search", None)
            category_id = request.query_params.get("category", None)

            if not search_query and not category_id:
                return Response(
                    {"error": "Search parameter or category parameter is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            queryset = None
            if search_query:
                queryset = Video.objects.filter(title__icontains=search_query)
            elif category_id:
                queryset = Video.objects.filter(categories__id=category_id)

            paginated_queryset = paginate_queryset(queryset, request)

            serializer = VideoSerializer(paginated_queryset, many=True)

            return Response(
                {
                    "total_count": queryset.count(),
                    "count": len(paginated_queryset),
                    "results": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                data={"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VideoDetail(APIView):
    permission_classes = [IsStaffOrReadOnly]
    

    def get(self, request, pk):
        try:
            video = Video.objects.get(id=pk)
            if (
                (request.user.is_authenticated and request.user.active) 
                or request.user.is_staff 
                or video.free
            ):
                serializer = VideoSerializer(video)
                return Response(serializer.data)
            return Response("Unauthorized", status=status.HTTP_401_UNAUTHORIZED)
        except Video.DoesNotExist:
            return Response(
                {"error": "Video not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                data={"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request, pk):
        video = Video.objects.get(id=pk)

        serializer = VideoSerializer(
            video,
            data=request.data,
        )

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
            return Response(
                data={"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, *args, **kwargs):

        try:
            if self.request.user.is_staff:
                # Check if 'categories' data is present in the request
                category_data = request.data.get("categories", None)

                if category_data:
                    # Validate and create categories
                    category_data = json.loads(category_data)
                    category = Category.objects.get(id=category_data.get("data_key"))

                    if category:
                        categories = [category]
                    else:
                        categories = []
                else:
                    # If no category data provided, create an empty list
                    categories = []

                # Create a video with associated categories
                video_data = request.data.copy()
                video_data.pop(
                    "categories", None
                )  # Remove 'categories' from video data

                video_serializer = VideoSerializer(data=video_data)
                video_serializer.is_valid(raise_exception=True)
                video = video_serializer.save()

                # Add the categories to the video
                video.categories.set(categories)

                return Response(
                    VideoSerializer(video).data, status=status.HTTP_201_CREATED
                )
            else:
                return Response("Unauthorized", status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response(
                {"errors": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def patch(self, request, pk):
        try:
            video = Video.objects.get(id=pk)
        except Video.DoesNotExist:
            return Response(
                {"error": "Video not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if not request.user.is_staff:
            return Response("Unauthorized", status=status.HTTP_401_UNAUTHORIZED)

        data = request.data.copy()

        # Extract and handle category data
        category_data = data.get("categories", None)
        if category_data:
            data.pop("categories", None)

            # Deserialize video data without category
            serializer = VideoSerializer(video, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()

                # Parse category_ids and update video categories
                try:
                    # Assuming category_data is a string in JSON format
                    category_json = json.loads(category_data)
                    category_id = int(
                        category_json.get("data_key")
                    )  # Extract the category ID
                    category = Category.objects.filter(id=category_id)
                    video.categories.set(category)
                except (ValueError, TypeError) as e:
                    return Response(
                        {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            serializer = VideoSerializer(video, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(VideoSerializer(video).data)


class CategoryAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request):
        logger.info("CategoryAPIView.get called")
        try:
            categories = Category.objects.all()
            serializer = CategorySerializer(categories, many=True, context={'request': request})
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error in CategoryAPIView GET: {str(e)}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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
        category.delete_with_videos()
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
        serializer = VideoSerializer(data=request.data, many=is_many)

        if serializer.is_valid():
            if is_many:
                videos = serializer.save()
                category.category_videos.add(
                    *videos
                )  # Add multiple videos to the category
            else:
                video = serializer.save()
                category.category_videos.add(
                    video
                )  # Add a single video to the category
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
