from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from django.contrib.auth import get_user_model
from payments.paypal_functions import get_paypal_access_token
from unittest.mock import patch, Mock,  MagicMock


class PaypalSubscriptionViewTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username='testuser',
            password='password123',
            paypal_subscription_id='I-F5J97PWEY3FA'  # Use a real subscription ID here
        )
        self.client.force_authenticate(user=self.user)
        self.subscription_id = 'I-F5J97PWEY3FA'  # Replace with your real subscription ID
        self.url = reverse('subscription_plan_paypal', args=[self.subscription_id])

    @patch('requests.get')  # Mock the requests.get call
    def test_get_subscription_success(self, mock_get):
        # Create a mock response object with the desired attributes
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': self.subscription_id,
            "plan_id": "P-5ML4271244454362WXNWU5NQ",
            "start_time": "2019-04-10T07:00:00Z",
            "quantity": "20",
            "shipping_amount": 
            {

                "currency_code": "USD",
                "value": "10.0"

            },
            "subscriber": 
            {

                "shipping_address": 

            {

                "name": 

            {

                "full_name": "John Doe"

            },
            "address": 

                {
                    "address_line_1": "2211 N First Street",
                    "address_line_2": "Building 17",
                    "admin_area_2": "San Jose",
                    "admin_area_1": "CA",
                    "postal_code": "95131",
                    "country_code": "US"
                }

            },
            "name": 

                {
                    "given_name": "John",
                    "surname": "Doe"
                },
                "email_address": "customer@example.com",
                "payer_id": "2BBBB8YJQSCCC"

            },
            "billing_info": 
            {

                "outstanding_balance": 

            {

                "currency_code": "USD",
                "value": "1.0"

            },
            "cycle_executions": 
            [

            {

                "tenure_type": "TRIAL",
                "sequence": 1,
                "cycles_completed": 0,
                "cycles_remaining": 2,
                "total_cycles": 2

            },
            {

                "tenure_type": "TRIAL",
                "sequence": 2,
                "cycles_completed": 0,
                "cycles_remaining": 3,
                "total_cycles": 3

            },

                {
                    "tenure_type": "REGULAR",
                    "sequence": 3,
                    "cycles_completed": 0,
                    "cycles_remaining": 12,
                    "total_cycles": 12
                }

            ],
            "last_payment": 
            {

                "amount": 

                    {
                        "currency_code": "USD",
                        "value": "1.15"
                    },
                    "time": "2019-04-09T10:27:20Z"
                },
                "next_billing_time": "2019-04-10T10:00:00Z",
                "failed_payments_count": 0

            },
            "create_time": "2019-04-09T10:26:04Z",
            "update_time": "2019-04-09T10:27:27Z",
            "links": 
            [

            {

                "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/cancel",
                "rel": "cancel",
                "method": "POST"

            },
            {

                "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                "rel": "edit",
                "method": "PATCH"

            },
            {

                "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                "rel": "self",
                "method": "GET"

            },
            {

                "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/suspend",
                "rel": "suspend",
                "method": "POST"

            },

                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/capture",
                    "rel": "capture",
                    "method": "POST"
                }

            ],
            "status": "ACTIVE",
            "status_update_time": "2019-04-09T10:27:27Z"
            # Add other necessary fields from the PayPal response
        }
        
        # Set the mock object to return the mock response
        mock_get.return_value = mock_response

        # Make the API call
        response = self.client.get(self.url)

        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.subscription_id)
        self.assertEqual(response.data['status'], 'ACTIVE')
        self.assertEqual(response.data['plan_id'], 'P-5ML4271244454362WXNWU5NQ')

        # Ensure the mock was called with the correct URL and headers
        mock_get.assert_called_once_with(
            f"https://api-m.sandbox.paypal.com/v1/billing/subscriptions/{self.subscription_id}",
            headers={
                "Authorization": f"Bearer {get_paypal_access_token()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def test_post_subscription_success(self):
        url = reverse('subscription_plan_paypal')
        data = {
            "user_id": self.user.id,
            "subscriptionID": "I-BW452GLLEP1G",  # Use the actual subscription ID
        }

        self.subscription_id = "I-BW452GLLEP1G"

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.user.refresh_from_db()
        self.assertEqual(self.user.paypal_subscription_id, self.subscription_id)
        self.assertTrue(self.user.active)

    def test_post_subscription_user_not_found(self):
        url = reverse('subscription_plan_paypal')
        data = {
            "user_id": 999,  # Invalid user ID
            "subscriptionID": self.subscription_id,
        }

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('requests.get')  # Mock requests.get
    @patch('requests.post')  # Mock requests.post
    @patch('celery.result.AsyncResult')  # Mock AsyncResult
    def test_patch_subscription_success(self, mock_async_result, mock_post, mock_get):
        # Mock response for requests.get
        url = reverse('subscription_plan_paypal', args=[self.user.id])
        mock_get_response =  MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            'id': self.subscription_id,
            "plan_id": "P-5ML4271244454362WXNWU5NQ",
            "start_time": "2019-04-10T07:00:00Z",
            "quantity": "20",
            "shipping_amount": 
            {

                "currency_code": "USD",
                "value": "10.0"

            },
            "subscriber": 
            {

                "shipping_address": 

            {

                "name": 

            {

                "full_name": "John Doe"

            },
            "address": 

                {
                    "address_line_1": "2211 N First Street",
                    "address_line_2": "Building 17",
                    "admin_area_2": "San Jose",
                    "admin_area_1": "CA",
                    "postal_code": "95131",
                    "country_code": "US"
                }

            },
            "name": 

                {
                    "given_name": "John",
                    "surname": "Doe"
                },
                "email_address": "customer@example.com",
                "payer_id": "2BBBB8YJQSCCC"

            },
            "billing_info": 
            {

                "outstanding_balance": 

            {

                "currency_code": "USD",
                "value": "1.0"

            },
            "cycle_executions": 
            [

            {

                "tenure_type": "TRIAL",
                "sequence": 1,
                "cycles_completed": 0,
                "cycles_remaining": 2,
                "total_cycles": 2

            },
            {

                "tenure_type": "TRIAL",
                "sequence": 2,
                "cycles_completed": 0,
                "cycles_remaining": 3,
                "total_cycles": 3

            },

                {
                    "tenure_type": "REGULAR",
                    "sequence": 3,
                    "cycles_completed": 0,
                    "cycles_remaining": 12,
                    "total_cycles": 12
                }

            ],
            "last_payment": 
            {

                "amount": 

                    {
                        "currency_code": "USD",
                        "value": "1.15"
                    },
                    "time": "2019-04-09T10:27:20Z"
                },
                "next_billing_time": "2019-04-10T10:00:00Z",
                "failed_payments_count": 0

            },
            "create_time": "2019-04-09T10:26:04Z",
            "update_time": "2019-04-09T10:27:27Z",
            "links": 
            [

            {

                "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/cancel",
                "rel": "cancel",
                "method": "POST"

            },
            {

                "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                "rel": "edit",
                "method": "PATCH"

            },
            {

                "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                "rel": "self",
                "method": "GET"

            },
            {

                "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/suspend",
                "rel": "suspend",
                "method": "POST"

            },

                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/capture",
                    "rel": "capture",
                    "method": "POST"
                }

            ],
            "status": "SUSPENDED",
            "status_update_time": "2019-04-09T10:27:27Z"
            # Add other necessary fields from the PayPal response
        }
        mock_get.return_value = mock_get_response

        # Mock response for requests.post
        mock_post_response =  MagicMock()
        mock_post_response.status_code = 200
        mock_post.return_value = mock_post_response

        # Mock AsyncResult
        mock_async_result_instance =  MagicMock()
        mock_async_result_instance.state = "PENDING"
        mock_async_result.return_value = mock_async_result_instance

        # Make the PATCH request
        response = self.client.patch(url)

        # Assertions
        print(response.json)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], "Subscription updated and reactivated successfully.")

        # Ensure the mock_get was called with the correct URL and headers
        mock_get.assert_called_once_with(
            f"https://api-m.sandbox.paypal.com/v1/billing/subscriptions/{self.user.paypal_subscription_id}",
            headers={
                "Authorization": f"Bearer {get_paypal_access_token()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

        

       

    # def test_delete_subscription_success(self):
    #     url = reverse('subscription_plan_paypal_delete', args=[self.user.id])

    #     response = self.client.delete(url)
    #     self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)