from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from scheduler.models import Event
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model


PASSWORD = 'pAssw0rd!'


def create_user(username='testuser', password=PASSWORD, active =False, email= 'user@example.com'):
     # Function to create a user with the specified parameters
    return get_user_model().objects.create_user(
        username=username,
        password=password,
        first_name='Test',
        last_name='User',
        email=email,
        telephone='3331722789',
        active=active
    )

class EventViewSetTest(APITestCase):
    def setUp(self):
        # Create a non-staff and a staff user
        self.non_staff_user = create_user()
        self.staff_user = create_user('testuser3', PASSWORD, False, 'testuser3@test.com')
        self.staff_user.is_staff = True
        self.staff_user.save()
        response1 = self.client.post(reverse('log_in'), data={
            'username': self.non_staff_user.username,
            'password': PASSWORD,
        })
        response2 = self.client.post(reverse('log_in'), data={
            'username': self.staff_user.username,
            'password': PASSWORD,
        })

        self.access_user = response1.data['access']
        self.access_staff_user = response2.data['access']

    

    def test_non_staff_user_can_read_events(self):
        response = self.client.get(reverse('events'), HTTP_AUTHORIZATION=f'Bearer {self.access_user}')  # Adjust 'event-list' to your actual URL name for EventViewSet list route
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_staff_user_cannot_create_event(self):
        data={'title': 'Test Event', 'day': 'Monday', 'startTime': '10:00', 'endTime': '11:00', 'description': 'A test event.'}
        response = self.client.post(reverse('events'), data=data, HTTP_AUTHORIZATION=f'Bearer {self.access_user}')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_user_can_create_event(self):
        data={'title': 'Staff Event', 'day': 'Tuesday', 'startTime': '12:00', 'endTime': '13:00', 'description': 'A staff created event.'}
        response = self.client.post(reverse('events'), data=data, HTTP_AUTHORIZATION=f'Bearer {self.access_staff_user}')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Event.objects.count(), 1)
        self.assertEqual(Event.objects.first().title, 'Staff Event')

    def test_bulk_create_events_by_staff(self):
        
        events_data = [
            {'title': 'Event 1', 'day': 'Wednesday', 'startTime': '14:00', 'endTime': '15:00', 'description': 'First bulk event.'},
            {'title': 'Event 2', 'day': 'Thursday', 'startTime': '16:00', 'endTime': '17:00', 'description': 'Second bulk event.'}
        ]
        response = self.client.post(reverse('events'), data=events_data,HTTP_AUTHORIZATION=f'Bearer {self.access_staff_user}', format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Event.objects.count(), len(events_data))
    
    def test_staff_user_can_update_event(self):
        event = Event.objects.create(
            title='Original Event',
            day='Friday',
            startTime='09:00',
            endTime='10:00',
            description='Original description.'
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_staff_user}')
        response = self.client.patch(reverse('event', kwargs={'pk': event.pk}), {
            'description': 'Updated description.'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event.refresh_from_db()
        self.assertEqual(event.description, 'Updated description.')
    
    def test_staff_user_can_delete_event(self):
        event = Event.objects.create(
            title='Deletable Event',
            day='Saturday',
            startTime='11:00',
            endTime='12:00',
            description='This event will be deleted.'
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_staff_user}')
        response = self.client.delete(reverse('event', kwargs={'pk': event.pk}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())
    
    def test_non_staff_user_cannot_update_or_delete_event(self):
        event = Event.objects.create(
            title='Non-Deletable Event',
            day='Sunday',
            startTime='13:00',
            endTime='14:00',
            description='Non-staff users should not be able to delete this.'
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_user}')
        update_response = self.client.patch(reverse('event', kwargs={'pk': event.pk}), {
            'description': 'Attempted unauthorized update.'
        }, format='json')
        delete_response = self.client.delete(reverse('event', kwargs={'pk': event.pk}))

        self.assertNotEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        event.refresh_from_db()
        self.assertNotEqual(event.description, 'Attempted unauthorized update.')