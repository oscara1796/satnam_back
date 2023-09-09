#!/bin/bash



# Perform docker-compose operations
docker-compose down
docker-compose up -d


# Start the Stripe CLI to listen to the webhook on localhost:8009 in the background
./stripe listen --forward-to localhost:8009/stripe/webhook/ &

# Store the Stripe CLI's process ID
stripe_cli_pid=$!

# Wait for the Stripe CLI to finish listening before exiting
wait $stripe_cli_pid
