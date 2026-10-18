"""
Django settings for digital_gram_panchayat project.
Production-hardened, secure architecture configuration.
"""

from pathlib import Path
from datetime import timedelta
import os
import sys
from django.core.exceptions import ImproperlyConfigured
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
except ImportError:
    pass

# Add parent directories to path for Vercel / serverless deployments
sys.path.insert(0, str(BASE_DIR))

# Media files (Uploaded files)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB max file upload size

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# Default DEBUG to True in local development; production must explicitly set DEBUG=False
DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')

# SECURITY: Secret key handling
# In production (DEBUG=False), SECRET_KEY must be provided via environment variable.
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG or 'test' in sys.argv:
        # Development / test fallback key generated dynamically per process
        import secrets
        SECRET_KEY = os.environ.get('SECRET_KEY') or f"dev-env-key-{secrets.token_hex(24)}"
    else:
        raise ImproperlyConfigured(
            "SECRET_KEY environment variable is missing. Set SECRET_KEY in your production environment."
        )


# Host validation
env_allowed_hosts = os.environ.get('ALLOWED_HOSTS')
if env_allowed_hosts:
    ALLOWED_HOSTS = [h.strip() for h in env_allowed_hosts.split(',') if h.strip()]
    if DEBUG and 'testserver' not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append('testserver')
elif DEBUG or 'test' in sys.argv:
    ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver', '[::1]']

else:
    ALLOWED_HOSTS = [
        '127.0.0.1',
        'localhost',
        '.vercel.app',
        '.herokuapp.com',
        '.onrender.com',
        '.pythonanywhere.com',
    ]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    # Local apps
    'core',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Serve static files in production
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# Security Headers & Protections
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = 'same-origin'

# Session Security
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# CSRF settings
CSRF_COOKIE_HTTPONLY = False  # Allows standard client-side CSRF token handling
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_HEADER_NAME = 'HTTP_X_CSRFTOKEN'

# HTTPS & Production Cookie Settings
if not DEBUG and 'test' not in sys.argv:
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() in ('true', '1')
    CSRF_COOKIE_SECURE = os.environ.get('CSRF_COOKIE_SECURE', 'True').lower() in ('true', '1')
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    if os.environ.get('SECURE_SSL_REDIRECT', 'False').lower() in ('true', '1'):
        SECURE_SSL_REDIRECT = True
        SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True
else:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False

ROOT_URLCONF = 'digital_gram_panchayat.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.csrf',
            ],
            'libraries': {
                'validators_tags': 'core.templatetags.validators_tags',
                'form_tags': 'core.templatetags.form_tags',
            },
        },
    },
]

WSGI_APPLICATION = 'digital_gram_panchayat.wsgi.application'

# Database Configuration
# Fall back to SQLite when DATABASE_URL is not provided (local dev / automated tests)
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Django REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
        'auth': '10/minute',
    },
}

# SimpleJWT configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
if os.environ.get('VERCEL') == '1':
    STATIC_ROOT = os.path.join(os.path.dirname(BASE_DIR), '.vercel', 'output', 'static')
else:
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
os.makedirs(STATIC_ROOT, exist_ok=True)
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')] if os.path.exists(os.path.join(BASE_DIR, 'static')) else []


# WhiteNoise storage
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication Backends (supports standard Django auth and allauth social login)
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Email Configuration
# Uses console backend locally if SMTP is not provided; does not claim live email without verified config.
if os.environ.get('EMAIL_HOST'):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ.get('EMAIL_HOST')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
    EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1')
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@digitalgrampanchayat.gov.in')

# django-allauth Google OAuth 2.0 Configuration
# Credentials are loaded exclusively via environment variables
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': os.environ.get('GOOGLE_OAUTH_CLIENT_ID') or os.environ.get('GOOGLE_CLIENT_ID', ''),
            'secret': os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET') or os.environ.get('GOOGLE_CLIENT_SECRET', ''),
            'key': ''
        },
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'VERIFIED_EMAIL': True,
    }
}
SOCIALACCOUNT_LOGIN_ON_GET = False
SOCIALACCOUNT_AUTO_SIGNUP = True
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_SIGNUP_FIELDS = ['username*', 'email', 'password1*', 'password2*']
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'services'
ACCOUNT_LOGOUT_REDIRECT_URL = 'login'

# Custom adapters: profile autofill on Google signup, privilege-escalation prevention
SOCIALACCOUNT_ADAPTER = 'core.adapters.GramPanchayathSocialAccountAdapter'
ACCOUNT_ADAPTER = 'core.adapters.GramPanchayathAccountAdapter'

# In-Memory Cache configuration for rate limiting and session throttling
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'dgp_cache_locmem',
    }
}


# Logging & Audit Configuration
LOGGING = {

    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} [{name}:{lineno}] {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django.security': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'core.audit': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
