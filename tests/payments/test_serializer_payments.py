from rest_framework.test import APITestCase
from django.urls import reverse
import stripe
from dotenv import dotenv_values
import  json
from django.contrib.auth import get_user_model



# Load the environment variables from .env.dev file
env_vars = dotenv_values(".env.dev")
PASSWORD = 'pAssw0rd!'


class StripeIntegrationTest(APITestCase):

    
    def setUp(self):
        # Initialize the Stripe API client with your API key
        stripe.api_key = env_vars["STRIPE_SECRET_KEY"]
        # self.subscription_url = reverse('subscription')
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
        self.user= get_user_model().objects.last()
        response = self.client.post(reverse('log_in'), data={
            'username': self.user.username,
            'password': PASSWORD,
        })
        self.access = response.data['access']
    
    def tearDown(self):
        # Clean up code
        # Delete test data, reset state, etc.
        url = reverse('user-detail', args=[self.user.id])
        response = self.client.delete(url, HTTP_AUTHORIZATION=f'Bearer {self.access}')
    
  

    def test_create_subscription(self):
        # Make the API request
        
        card_data={
            'number': '4242424242424242',
            'exp_month': 12,
            'exp_year': 2024,
            'cvc': '123',
        }

        url = reverse('create_subscription', args=[self.user.id])
        response = self.client.post(url, card_data,HTTP_AUTHORIZATION=f'Bearer {self.access}', format='json')
        print(response.data)
        self.assertEqual(response.status_code, 201)
        
        self.assertIn('stripe_customer_id', response.data)
        self.assertIn('subscription_id', response.data)
        self.assertIn('status', response.data)
        user = get_user_model().objects.get(id=self.user.id)
        self.assertTrue(user.active)
        # self.assertTrue(stripe.PaymentMethod.retrieve(response_obj["id"]))
        subscription_id = response.data['subscription_id']
        self.assertIsNotNone(subscription_id)

    



    
    def test_get_product_prices(self):
        url = reverse('get_product_prices')
        response = self.client.get(url, format='json')
        response_obj = json.loads(response.data)
        # print(response_obj)
        self.assertEqual(response.status_code, 200)
        for product in response_obj:
            # print(product)
            self.assertTrue(product["default_price"].startswith('price_'))
            self.assertTrue(product["id"].startswith('prod_'))
            self.assertIsNotNone(product["name"])
    
    def test_delete_subscription(self):
        card_data={
            'number': '4242424242424242',
            'exp_month': 12,
            'exp_year': 2024,
            'cvc': '123',
        }

        url = reverse('create_subscription', args=[self.user.id])
        response = self.client.post(url, card_data,HTTP_AUTHORIZATION=f'Bearer {self.access}', format='json')
        user = get_user_model().objects.get(id=self.user.id)
        self.assertTrue(user.active)
        self.assertEqual(response.status_code, 201)
        response = self.client.delete(url, HTTP_AUTHORIZATION=f'Bearer {self.access}', format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'success': 'Subscription canceled'})
        user = get_user_model().objects.get(id=self.user.id)
        self.assertFalse(user.active)

        with self.assertRaises(stripe.error.StripeError):
            subscription = stripe.Subscription.retrieve(self.user.stripe_subscription_id )

        

    def test_get_subscription(self):
        card_data={
            'number': '4242424242424242',
            'exp_month': 12,
            'exp_year': 2024,
            'cvc': '123',
        }

        url = reverse('create_subscription', args=[self.user.id])
        response = self.client.post(url, card_data,HTTP_AUTHORIZATION=f'Bearer {self.access}', format='json')
        self.assertEqual(response.status_code, 201)
        user = get_user_model().objects.get(id=self.user.id)
        response = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.access}', format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["subscription_id"], user.stripe_subscription_id)
        self.assertIn('status', response.data)
        self.assertIn('current_period_end', response.data)
        self.assertIn('cancel_at_period_end', response.data)

            

        
    
    
        
        


    
#     def test_create_payment_intent(self):
#         # Make a request to your Django API endpoint that creates a payment intent
#         response = self.client.post('/api/payment/create-intent/', data={'amount': 1000, 'currency': 'usd'})
        
#         # Assert that the API request was successful (HTTP status code 200)
#         self.assertEqual(response.status_code, 200)

#         # Assert that the response contains a valid payment intent ID
#         payment_intent_id = response.data.get('payment_intent_id')
#         self.assertIsNotNone(payment_intent_id)

#         # Retrieve the payment intent from Stripe using the payment intent ID
#         payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

#         # Assert that the payment intent amount and currency match the request
#         self.assertEqual(payment_intent.amount, 1000)
#         self.assertEqual(payment_intent.currency, 'usd')
    
#     def test_process_payment(self):
#         # Create a payment method in Stripe (e.g., using a test card)
#         payment_method = stripe.PaymentMethod.create(
#             type='card',
#             card={
#                 'number': '4242424242424242',
#                 'exp_month': 12,
#                 'exp_year': 2024,
#                 'cvc': '123'
#             }
#         )

#         # Make a request to your Django API endpoint that processes the payment
#         response = self.client.post('/api/payment/process-payment/', data={'payment_method_id': payment_method.id})

#         # Assert that the API request was successful (HTTP status code 200)
#         self.assertEqual(response.status_code, 200)

#         # Assert that the payment was successful by checking the payment status
#         payment_status = response.data.get('status')
#         self.assertEqual(payment_status, 'succeeded')
    
    # def test_create_subscription(self):
    #     # Prepare the request data

        

    #     data = {
    #         'customer_id': 'cus_1234567890',  # Stripe customer ID
    #         'plan_id': 'plan_1234567890',  # Stripe plan ID
    #         'payment_method_id': 'pm_1234567890',  # Stripe payment method ID
    #     }

    #     # Make the API request
    #     response = self.client.post(self.subscription_url, data, format='json')

    #     # Assert the response status code
    #     self.assertEqual(response.status_code, 200)

    #     # Assert the response data
    #     response_data = json.loads(response.content)
    #     self.assertTrue('subscription_id' in response_data)

    #     # Assert the subscription was created in Stripe
    #     subscription_id = response_data['subscription_id']
    #     try:
    #         subscription = stripe.Subscription.retrieve(subscription_id)
    #         self.assertEqual(subscription.customer, data['customer_id'])
    #         self.assertEqual(subscription.plan, data['plan_id'])
    #         self.assertEqual(subscription.default_payment_method, data['payment_method_id'])
    #     except stripe.StripeError as e:
    #         self.fail(f"Failed to retrieve subscription from Stripe: {str(e)}")




