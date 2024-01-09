from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import ContactSubmission
from .serializers import ContactSubmissionSerializer
from django_ratelimit.decorators import ratelimit



@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def rate_limit_check(request):
    pass

class ContactSubmissionView(APIView):

    
    def get(self, request, pk=None, *args, **kwargs):

        if not request.user.is_staff:
            return Response({"detail": "You do not have permission to perform this action."},
                            status=status.HTTP_403_FORBIDDEN)
        if pk is not None:
            try:
                submission = ContactSubmission.objects.get(pk=pk)
            except ContactSubmission.DoesNotExist:
                return Response(status=status.HTTP_404_NOT_FOUND)
            serializer = ContactSubmissionSerializer(submission)
        else:
            submissions = ContactSubmission.objects.all()
            serializer = ContactSubmissionSerializer(submissions, many=True)
        
        return Response(serializer.data)

    
    def post(self, request):

        # Perform rate limit check
        rate_limit_check(request)

        serializer = ContactSubmissionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk, *args, **kwargs):
        try:
            submission = ContactSubmission.objects.get(pk=pk)
        except ContactSubmission.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        submission.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
