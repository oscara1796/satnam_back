#!/bin/bash

set -o errexit
set -o nounset

celery -A satnam worker -l INFO