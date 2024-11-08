

import datetime
import os
from pathlib import Path

import dj_database_url
import paypalrestsdk
import redis
from django.core.management.utils import get_random_secret_key
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# SECRET_KEY = 'django-insecure-j$3o=&)t0)2c7w8r&j3z_(2f2qv^&pdwzna+#c6_k!z3r*%s24'
load_dotenv(".env.dev")

SECRET_KEY = os.environ.get("SECRET_KEY", default=get_random_secret_key())


PASSWORD_RESET_URL = "https://www.satnamyogaestudio.com.mx"

DEBUG = int(os.environ.get("DEBUG", default=0))


TESTING = False

# SECURITY WARNING: don't run with debug turned on in production!
# DEBUG = True

ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS", default="127.0.0.1 localhost [::1]"
).split(" ")


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "sslserver",
    "rest_framework",
    "corsheaders",
    "storages",
    "core",
    "videos",
    "payments",
    "contact",
    "captcha_app",
    "scheduler",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "satnam.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "satnam.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.1/ref/settings/#databases

if DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": os.environ.get("SQL_ENGINE", "django.db.backends.sqlite3"),
            "NAME": os.environ.get(
                "SQL_DATABASE", os.path.join(BASE_DIR, "db.sqlite3")
            ),
            "USER": os.environ.get("SQL_USER", "user"),
            "PASSWORD": os.environ.get("SQL_PASSWORD", "password"),
            "HOST": os.environ.get("SQL_HOST", "localhost"),
            "PORT": os.environ.get("SQL_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

    DATABASE_URL = os.environ.get("DATABASE_URL")
    db_from_env = dj_database_url.config(
        default=DATABASE_URL, conn_max_age=500, ssl_require=True
    )
    DATABASES["default"].update(db_from_env)

# REDIS CONFIG

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

# Set up a Redis connection pool
REDIS_POOL = redis.ConnectionPool.from_url(REDIS_URL)


# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = "es-MX"

TIME_ZONE = "America/Mexico_City"

USE_I18N = True

USE_L10N = True

USE_TZ = True

LANGUAGES = [
    ("es-MX", "Spanish (Mexico)"),
    # Add other languages here
]


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = "static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"


MEDIA_ROOT = os.path.join(BASE_DIR, "media")


# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Custom model

AUTH_USER_MODEL = "core.CustomUser"


# Authentication using session and token auth

AUTHENTICATION_BACKENDS = ["core.backends.CustomBackend"]


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",  
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": datetime.timedelta(minutes=120),
    "REFRESH_TOKEN_LIFETIME": datetime.timedelta(days=1),
    "USER_ID_CLAIM": "id",
    "SLIDING_TOKEN_REFRESH_RESET": True,
    "BLACKLIST_AFTER_ROTATION": False,
}


STRIPE_WEBHOOK_SECRET = (
    "whsec_aea6cc4ba45773f32e82953b195c02843187f9b6ef0c85915b327a1927dfda53"
)
STRIPE_SUBSCRIPTION_PRICE_ID = "price_1I2kVQJQ5QjlwW1LWRpqDQlC"


# frontend
SUBSCRIPTION_SUCCESS_URL = "http://localhost:8009/subscription/success/"
SUBSCRIPTION_FAILED_URL = "http://localhost:8009/subscription/failed/"


# CORS_ORIGIN_WHITELIST = [
#     "http://localhost:3001",
#     "http://192.168.100.162:3001",
# ]

CORS_ALLOWED_ORIGINS = [
    "https://192.168.100.162:3001",
    "http://192.168.100.162:3001",
    "https://localhost:3001",
    "https://127.0.0.1:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3001",
    "https://satnam-client-4754c00a2e7d.herokuapp.com",
    "http://www.satnamyogaestudio.com.mx",
    "https://www.satnamyogaestudio.com.mx",
]

CORS_ORIGIN_ALLOW_ALL = False
CORS_ALLOW_CREDENTIALS = True

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "user_session"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "None"


CSRF_TRUSTED_ORIGINS = ["https://satnam-api-38ccd2c6f742.herokuapp.com"]

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True


# EMAIL WCONFIG

EMAIL_BACKEND = "django_ses.SESBackend"

# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# EMAIL_HOST = "smtp.mailgun.org"
EMAIL_HOST_USER = "satnamyogajal@gmail.com"
# EMAIL_HOST_PASSWORD = (os.environ.get("EMAIL_HOST_PASSWORD"),)
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True

# AWS USER CREDENTIALS

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_SES_REGION_NAME = "us-east-2"
AWS_SES_REGION_ENDPOINT = "email.us-east-2.amazonaws.com"

# AMAZON BUCKET

AWS_STORAGE_BUCKET_NAME = "satnam-bucket"

# if not DEBUG:
DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.us-east-2.amazonaws.com"
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "max-age=86400",
}
STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/static/"
MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"
# else:
#     MEDIA_URL = '/media/'
#     MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# PAYPAL CONFIG

PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET")
PAYPAL_WEBHOOK_ID = os.environ.get("PAYPAL_WEBHOOK_ID")
PAYPAL_FAILED_SUBSCRIPTION_PAYMENT_THRESHOLD = 3

# Configure PayPal SDK
paypalrestsdk.configure(
    {
        "mode": "sandbox",  # Change to "live" for production
        "client_id": PAYPAL_CLIENT_ID,
        "client_secret": PAYPAL_CLIENT_SECRET,
    }
)




if TESTING:
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True


# CELERY CONFIG
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER", REDIS_URL)
CELERY_RESULT_BACKEND = os.environ.get("CELERY_BACKEND", REDIS_URL)

CELERY_WORKER_CONCURRENCY = 2

CELERY_BROKER_TRANSPORT_OPTIONS = {
    'ssl': {
        'ssl_cert_reqs': 'CERT_NONE',  # Disables SSL certificate verification
    }
}


# logging logic
log_directory = os.path.join(BASE_DIR, "logs")
if not os.path.exists(log_directory):
    os.makedirs(log_directory)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "django_errors.log"),
            "maxBytes": 1024 * 1024 * 5,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["file", "console"],
            "level": "INFO",
            "propagate": False,
        },
        "videos": {  # Replace with your app's name
            "handlers": ["file", "console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["file"],
            "level": "INFO",
            "propagate": False,
        },
        "workers": {
            "handlers": ["file", "console"],
            "level": "INFO",
            "propagate": False,
        },
        "payments": {
            "handlers": ["file", "console"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
}

