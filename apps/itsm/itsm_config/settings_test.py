"""
Test settings for running automated tests

Optimized for fast test execution while maintaining PostgreSQL compatibility.
Imports base settings and overrides only what's necessary for testing.
"""

from .settings import *

# Override for testing
DEBUG = True

# Use test secret key if not provided
if not os.getenv('DJANGO_SECRET_KEY'):
    SECRET_KEY = 'test-secret-key-for-ci-cd-only-not-for-production'

# Use PostgreSQL for tests (same as production)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'NAME': os.environ.get('POSTGRES_DATABASE', 'test_itsm'),
        'USER': os.environ.get('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'postgres'),
        'TEST': {
            'NAME': 'test_itsm_db',
            'CHARSET': 'UTF8',
        },
    }
}

# Simplified password hashing for faster tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Logging - only show errors during tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'ERROR',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'ERROR',
    },
}

# Disable cache during tests
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Static and media files for tests
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static_test/')
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media_test/')

# Email backend for tests
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Simplified authentication for tests
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

# Allow all hosts in tests
ALLOWED_HOSTS = ['*']
CSRF_TRUSTED_ORIGINS = []

# Don't require HTTPS for CSRF in tests
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

SESSION_COOKIE_SECURE = False
