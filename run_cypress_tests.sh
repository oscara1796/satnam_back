#!/bin/bash


# Run the Django createsuperuser command
docker-compose exec core python manage.py create_superuser



# Run Cypress in interactive mode
cd ../client && yarn run cypress open &

# Capture the process ID of the Cypress command
CYPRESS_PID=$!

# Wait for the Cypress process to finish
wait $CYPRESS_PID

# Check if the browser was closed or if the process ended for other reasons
CYPRESS_EXIT_CODE=$?
if [ $CYPRESS_EXIT_CODE -eq 0 ]; then
  # Clean up Docker containers and volumes
  
  docker-compose down -v
  docker-compose up -d
else
  echo "Cypress was terminated or encountered an error. Skipping clean up."
fi

# Exit with the same exit code as the Cypress process
exit $CYPRESS_EXIT_CODE

