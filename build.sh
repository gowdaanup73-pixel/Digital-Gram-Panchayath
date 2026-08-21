#!/bin/bash
set -e

echo "Installing Python dependencies..."
pip install -q -r requirements.txt

echo "Running Django migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "Build completed successfully!"
