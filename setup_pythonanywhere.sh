#!/bin/bash
# Digital Gram Panchayat - PythonAnywhere Auto Setup Script
# Run this in your PythonAnywhere Bash console

set -e

USERNAME=$(whoami)
PROJECT_DIR="/home/$USERNAME/Digital-Gram-Panchayath"
VENV_DIR="/home/$USERNAME/.virtualenvs/gramenv"

echo "============================================"
echo " Digital Gram Panchayat - Auto Setup"
echo " PythonAnywhere user: $USERNAME"
echo "============================================"

# Step 1: Clone repo
echo "[1/7] Cloning repository..."
if [ -d "$PROJECT_DIR" ]; then
    echo "  Directory exists, pulling latest..."
    cd "$PROJECT_DIR" && git pull
else
    git clone https://github.com/gowdaanup73-pixel/Digital-Gram-Panchayath.git "$PROJECT_DIR"
fi
cd "$PROJECT_DIR"

# Step 2: Create virtualenv
echo "[2/7] Creating virtual environment..."
python3.12 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Step 3: Install dependencies
echo "[3/7] Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Step 4: Collect static files
echo "[4/7] Collecting static files..."
export SECRET_KEY="${SECRET_KEY:-insecure-setup-key-for-collectstatic-only}"
export DEBUG="${DEBUG:-False}"
python manage.py collectstatic --no-input -v 0

# Step 5: Run migrations
echo "[5/7] Running database migrations..."
python manage.py migrate --run-syncdb

# Step 6: Write WSGI file
echo "[6/7] Writing WSGI configuration..."
WSGI_FILE="/var/www/${USERNAME}_pythonanywhere_com_wsgi.py"
cat > "$WSGI_FILE" << 'WSGI'
import os
import sys
from dotenv import load_dotenv

project_home = os.path.expanduser('~/Digital-Gram-Panchayath')
if project_home not in sys.path:
    sys.path.insert(0, project_home)

load_dotenv(os.path.join(project_home, '.env'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'digital_gram_panchayat.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
WSGI


echo "  WSGI file written to: $WSGI_FILE"

# Step 7: Print remaining manual steps
echo ""
echo "[7/7] Almost done! Two manual steps left in the Web tab:"
echo "============================================"
echo " Your username : $USERNAME"
echo " Virtualenv    : $VENV_DIR"
echo " Static URL    : /static/"
echo " Static Dir    : $PROJECT_DIR/staticfiles"
echo " Your site URL : https://$USERNAME.pythonanywhere.com"
echo "============================================"
echo ""
echo "In the PythonAnywhere WEB tab:"
echo "  1. Virtualenv -> enter: $VENV_DIR"
echo "  2. Static files -> URL: /static/  Dir: $PROJECT_DIR/staticfiles"
echo "  3. Click the GREEN RELOAD button"
echo ""
echo "Done! Visit: https://$USERNAME.pythonanywhere.com"