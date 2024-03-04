from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from contact.models import ContactSubmission

PASSWORD = "pAssw0rd!"


def create_user(
    username="testuser", password=PASSWORD, active=False, email="user@example.com"
):
    # Function to create a user with the specified parameters
    return get_user_model().objects.create_user(
        username=username,
        password=password,
        first_name="Test",
        last_name="User",
        email=email,
        telephone="3331722789",
        active=active,
    )


class ContactSubmissionTests(APITestCase):

    def setUp(self):
        # create some test videos in the database
        self.staff_user = create_user(
            "testuser3", PASSWORD, False, "testuser3@test.com"
        )
        self.staff_user.is_staff = True
        self.staff_user.save()

        response3 = self.client.post(
            reverse("log_in"),
            data={
                "username": self.staff_user.username,
                "password": PASSWORD,
            },
        )

        self.access_staff_user_3 = response3.data["access"]

    def test_create_contact_submission(self):
        url = reverse("contacts")
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "message": "Hello there!",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "John Doe")
        self.assertEqual(response.data["email"], "john@example.com")
        self.assertEqual(response.data["message"], "Hello there!")

    def test_get_all_submissions(self):
        # Set up
        # Create a staff user and authenticate

        # Create test submissions
        ContactSubmission.objects.create(
            name="Test1", email="test1@example.com", message="Test Message 1"
        )
        ContactSubmission.objects.create(
            name="Test2", email="test2@example.com", message="Test Message 2"
        )

        # Test
        url = reverse("contacts")  # Adjust based on your url name
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access_staff_user_3}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_get_single_submission(self):
        # Similar setup as above, then...

        submission = ContactSubmission.objects.create(
            name="Test3", email="test3@example.com", message="Test Message 3"
        )
        url = reverse(
            "contact", kwargs={"pk": submission.id}
        )  # Adjust based on your url name
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access_staff_user_3}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Test3"

    def test_delete_submission(self):
        # Similar setup as above, then...

        submission = ContactSubmission.objects.create(
            name="Test4", email="test4@example.com", message="Test Message 4"
        )
        url = reverse(
            "contact", kwargs={"pk": submission.id}
        )  # Adjust based on your url name
        response = self.client.delete(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access_staff_user_3}"
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not ContactSubmission.objects.filter(pk=submission.id).exists()
