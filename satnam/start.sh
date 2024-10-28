#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

python manage.py flush --no-input
python manage.py migrate 

# Use Daphne to serve ASGI, which supports WebSockets.
daphne -b 0.0.0.0 -p 8000 satnam.asgi:application
