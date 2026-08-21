import os
import sys
import django

# Add the root directory to the path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'digital_gram_panchayat.settings')

try:
    django.setup()
except RuntimeError:
    pass

# Import the WSGI application
from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()



