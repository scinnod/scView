#!/bin/bash
set -e

# Generate Django secret key if it doesn't exist
SECRET_KEY_FILE="${SECRET_KEY_FILE:-/secrets/django_secret_key}"
SECRET_KEY_DIR=$(dirname "$SECRET_KEY_FILE")

if [ ! -f "$SECRET_KEY_FILE" ]; then
    echo "Generating new Django secret key..."
    mkdir -p "$SECRET_KEY_DIR"
    python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())' > "$SECRET_KEY_FILE"
    chmod 600 "$SECRET_KEY_FILE"
    echo "Secret key generated at $SECRET_KEY_FILE"
fi

# Export secret key to environment
export DJANGO_SECRET_KEY=$(cat "$SECRET_KEY_FILE")

# Security check for DEBUG mode in production
if [ "${DJANGO_ENV}" = "production" ] && [ "${DEBUG}" = "True" ] || [ "${DEBUG}" = "true" ] || [ "${DEBUG}" = "1" ]; then
    echo "" >&2
    echo "╔════════════════════════════════════════════════════════════════════╗" >&2
    echo "║                    ⚠️  CRITICAL SECURITY WARNING ⚠️                  ║" >&2
    echo "╠════════════════════════════════════════════════════════════════════╣" >&2
    echo "║  DEBUG MODE IS ENABLED IN PRODUCTION!                             ║" >&2
    echo "║                                                                    ║" >&2
    echo "║  This exposes:                                                     ║" >&2
    echo "║    • Sensitive configuration and environment variables             ║" >&2
    echo "║    • Full stack traces with source code                           ║" >&2
    echo "║    • SQL queries and database structure                           ║" >&2
    echo "║    • File paths and system information                            ║" >&2
    echo "║                                                                    ║" >&2
    echo "║  IMMEDIATELY SET DEBUG=False IN YOUR PRODUCTION ENVIRONMENT!       ║" >&2
    echo "╚════════════════════════════════════════════════════════════════════╝" >&2
    echo "" >&2
    sleep 5  # Give operator time to see the warning
fi

if [ -n "$DB_HOST" ] && [ "$DB_HOST" != "NONE" ]; then
  echo "Waiting for database $DB_HOST:$DB_PORT..."
  until nc -z "$DB_HOST" "$DB_PORT"; do
    sleep 1
  done
else
  echo "Skipping database wait because DB_HOST is '$DB_HOST'"
fi

echo "Running migrations..."
python manage.py migrate --noinput

echo "Compiling translation messages..."
python manage.py compilemessages

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Generating cache table..."
python manage.py createcachetable 

echo "Starting Gunicorn with ${GUNICORN_WORKERS:-3} workers..."
exec gunicorn ${DJANGO_SETTINGS_DIR:-itsm_config}.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}"
