#!/bin/bash
set -e

# PostgreSQL Initialization Script for Django
# This script creates the database and user for Django with recommended settings
# Environment variables are passed from docker-compose.yml

echo "Initializing PostgreSQL database for Django..."

# Install extensions in template1 so all new databases (including test databases) inherit them
echo "Installing PostgreSQL extensions in template1..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "template1" <<-EOSQL
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- Trigram matching for full-text search
CREATE EXTENSION IF NOT EXISTS "btree_gin";      -- Index support for JSONB fields
CREATE EXTENSION IF NOT EXISTS "btree_gist";     -- Index support for range fields
EOSQL

# Database credentials from environment variables
DB_NAME="${POSTGRES_DB:-itsm}"
DB_USER="${POSTGRES_APP_USER:-itsm_user}"
DB_PASSWORD="${POSTGRES_APP_PASSWORD:-itsm_password}"

# Create database user if it doesn't exist
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
-- Create user if not exists
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$DB_USER') THEN
        CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
        RAISE NOTICE 'User $DB_USER created';
    ELSE
        RAISE NOTICE 'User $DB_USER already exists';
    END IF;
END
\$\$;

-- Create database if not exists
SELECT 'CREATE DATABASE $DB_NAME OWNER $DB_USER'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
EOSQL

# Configure database with Django-recommended settings
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$DB_NAME" <<-EOSQL
-- Django-recommended PostgreSQL configuration
-- See: https://docs.djangoproject.com/en/stable/ref/databases/#postgresql-notes

-- Timezone configuration (Django recommends UTC)
ALTER DATABASE $DB_NAME SET timezone = 'UTC';

-- Grant schema permissions to application user
GRANT ALL ON SCHEMA public TO $DB_USER;

-- For PostgreSQL 15+: Grant default privileges for future tables
-- This ensures the app user owns tables created by migrations
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO $DB_USER;

-- Extensions are inherited from template1, but we can verify they exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";
EOSQL

echo "PostgreSQL database '$DB_NAME' initialized successfully for user '$DB_USER'."
