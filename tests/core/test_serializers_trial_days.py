from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import TrialDays  # Replace with your actual import

PASSWORD = "pAssw0rd!"


def create_user(
    username="testuser", password=PASSWORD, email="user@example.com", is_staff=False
):
    return get_user_model().objects.create_user(
        username=username, password=password, email=email, is_staff=is_staff
    )


class TrialDaysTests(APITestCase):

    def setUp(self):
        self.user = create_user("testuser", PASSWORD, "testuser@test.com")
        self.staff_user = create_user("staffuser", PASSWORD, "staffuser@test.com", True)

        # Log in as staff user
        response = self.client.post(
            reverse("log_in"),
            data={
                "username": self.staff_user.username,
                "password": PASSWORD,
            },
        )
        self.access_token = response.data["access"]

        response = self.client.post(
            reverse("log_in"),
            data={
                "username": self.user.username,
                "password": PASSWORD,
            },
        )
        self.non_staff_user_access_token = response.data["access"]

    def test_create_trial_day(self):
        url = reverse("trial_days")  # Adjust based on your url name
        data = {"days": 30}
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["days"], 30)

    def test_get_all_trial_days(self):
        # Create test trial days
        TrialDays.objects.create(days=10)
        TrialDays.objects.create(days=20)

        url = reverse("trial_days")  # Adjust based on your url name
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_get_single_trial_day(self):
        trial_day = TrialDays.objects.create(days=15)
        url = reverse(
            "trial_day_detail", kwargs={"pk": trial_day.id}
        )  # Adjust based on your url name
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["days"], 15)

    def test_delete_trial_day(self):
        trial_day = TrialDays.objects.create(days=15)
        url = reverse(
            "trial_day_detail", kwargs={"pk": trial_day.id}
        )  # Adjust based on your url name
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TrialDays.objects.filter(pk=trial_day.id).exists())

    def test_non_staff_user_access(self):
        # Attempt to create a trial day as a non-staff user
        url = reverse("trial_days")  # Adjust based on your url name
        data = {"days": 30}
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.non_staff_user_access_token}"
        )
        response = self.client.post(url, data, format="json")
        self.assertNotEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        TrialDays.objects.create(days=10)
        TrialDays.objects.create(days=20)
        # Attempt to access all trial days as a non-staff user
        url = reverse("trial_days")  # Adjust based on your url name
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        # Attempt to delete a trial day as a non-staff user
        trial_day = TrialDays.objects.create(days=15)
        url = reverse(
            "trial_day_detail", kwargs={"pk": trial_day.id}
        )  # Adjust based on your url name
        response = self.client.delete(url)
        self.assertNotEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # Add more tests as needed for update and other scenarios
