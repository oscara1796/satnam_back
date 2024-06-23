from locust import HttpUser, TaskSet, task, between
import json
import stripe
import uuid

from dotenv import load_dotenv

load_dotenv(".env.dev")
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

class UserBehavior(TaskSet):
    
    @task
    def post_event(self):
        # Generate unique IDs for the event and object
        event_id = f'evt_{uuid.uuid4()}'
        object_id = f'in_{uuid.uuid4()}'
        customer_id = f'cus_{uuid.uuid4()}'

        # Define the payload for the event
        payload = {
            'id': event_id,
            'type': 'invoice.payment_succeeded',
            'data': {
                'object': {
                    'id': object_id,
                    'amount_due': 2000,
                    'currency': 'usd',
                    'customer': customer_id
                }
            }
        }

        # Construct the Stripe event from the payload
        event = stripe.Event.construct_from(payload, stripe.api_key)

        # Send the event to the endpoint
        self.client.post("/stripe/webhook/", json=event.to_dict())

class WebsiteUser(HttpUser):
    tasks = [UserBehavior]
    wait_time = between(1, 2)  # Simulates the time between tasks for each user
