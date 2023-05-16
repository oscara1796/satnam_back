from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
import base64 
import json 
from django.contrib.auth.models import User
import stripe
from dotenv import dotenv_values


env_vars = dotenv_values(".env.dev")
stripe.api_key = env_vars["STRIPE_SECRET_KEY"]

PASSWORD = 'pAssw0rd!'

def create_user(username='testuser', password=PASSWORD):
    # Create a user with the given username and password
    return get_user_model().objects.create_user(
        username=username,
        password=password,
        first_name='Test',
        last_name='User',
        email='user@example.com',
        telephone='3331722789',
    )


class AuthenticationTest(APITestCase):
    def test_user_can_sign_up(self):
        # Test user sign up endpoint
        response = self.client.post(reverse('sign_up'), data={
            'username':'testuser',
            'email':'user@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'telephone': '3331722789',
            'password1': PASSWORD,
            'password2': PASSWORD
        })

        # Retrieve the user object from the database
        user= get_user_model().objects.last()
        # Assertions to check the response data matches the user object
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(response.data['id'], user.id)
        self.assertEqual(response.data['username'], user.username)
        self.assertEqual(response.data['email'], user.email)
        self.assertEqual(response.data['first_name'], user.first_name)
        self.assertEqual(response.data['last_name'], user.last_name)
        self.assertEqual(response.data['telephone'], user.telephone)
        self.assertIsNotNone(response.data["stripe_customer_id"])
        self.assertEqual(response.data["stripe_customer_id"], user.stripe_customer_id)
        response_stripe=stripe.Customer.delete(user.stripe_customer_id)
    
    def test_user_can_log_in(self):
        # Create a user for login
        user = create_user()

        
        response = self.client.post(reverse('log_in'), data={
            'username': user.username,
            'password': PASSWORD
            }
        )

        # Parse payload data from access token
        access= response.data['access']
        header, payload, signature = access.split('.')
        decoded_payload= base64.b64decode(f'{payload}==')
        payload_data= json.loads(decoded_payload)


        # Assertions to check the response data matches the user object
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertIsNotNone(response.data['refresh'])
        self.assertEqual(payload_data['id'], user.id)
        self.assertEqual(payload_data['username'], user.username)
        self.assertEqual(payload_data['email'], user.email)
        self.assertEqual(payload_data['first_name'], user.first_name)
        self.assertEqual(payload_data['last_name'], user.last_name)
        self.assertEqual(payload_data['telephone'], user.telephone)


class UserTestCase(APITestCase):
    
    def setUp(self):
        # Create a user and authenticate for subsequent tests
        self.user = create_user()
        response = self.client.post(reverse('log_in'), data={
            'username': self.user.username,
            'password': PASSWORD,
        })
        self.access = response.data['access']
    
    def test_get_user(self):
        # Test retrieving user details
        url = reverse('user-detail', args=[self.user.id])
        response = self.client.get(url, 
            HTTP_AUTHORIZATION=f'Bearer {self.access}', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.user.id)
        self.assertEqual(response.data['username'], self.user.username)
        self.assertEqual(response.data['email'], self.user.email)
        self.assertEqual(response.data['first_name'], self.user.first_name)
        self.assertEqual(response.data['last_name'], self.user.last_name)
        self.assertEqual(response.data['telephone'], self.user.telephone)

    def test_update_user(self):
         # Test updating user details
        url = reverse('user-detail', args=[self.user.id])
        data = {
            'username':'testuser2',
            'email':'user2@example.com',
            'first_name': 'Test2',
            'last_name': 'User2',
            'telephone': '3331722789',
            'password1': "pass",
            'password2': "pass"
        }
        response = self.client.put(url, data, HTTP_AUTHORIZATION=f'Bearer {self.access}',format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated_user = get_user_model().objects.get(id=self.user.id)
        self.assertEqual(data['username'], updated_user.username)
        self.assertEqual(data['email'], updated_user.email)
        self.assertEqual(data['first_name'], updated_user.first_name)
        self.assertEqual(data['last_name'], updated_user.last_name)
        self.assertEqual(data['telephone'], updated_user.telephone)
    
    def test_delete_user(self):
        # Test deleting a user
        response = self.client.post(reverse('sign_up'), data={
            'username':'testuser2',
            'email':'user2@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'telephone': '3331722789',
            'password1': PASSWORD,
            'password2': PASSWORD
        })
        user = get_user_model().objects.get(id=response.data["id"])
        url = reverse('user-detail', args=[user.id])
        response = self.client.delete(url, HTTP_AUTHORIZATION=f'Bearer {self.access}')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        with self.assertRaises(get_user_model().DoesNotExist):
            get_user_model().objects.get(id=user.id)