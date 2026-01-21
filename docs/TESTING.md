# Testing Guide

This document describes how to run and write tests for the ITSM Service Catalogue.

## Overview

The project uses **pytest** with **pytest-django** for testing. The test suite covers:

- **Model tests**: Creation, validation, and business logic
- **View tests**: HTTP responses, templates, and context data
- **Integration tests**: Complete workflows and relationships
- **Performance tests**: Query optimization verification

## Quick Start

**TL;DR**: Run tests locally with Docker (fastest and easiest):

```bash
cd /home/da1061/docker/jade-prod/2_itsm
docker-compose exec itsm python -m pytest -v
```

## Running Tests Locally

### Option 1: With Docker (Recommended)

This is the easiest and most reliable way since Docker handles all dependencies:

```bash
# Make sure containers are running
docker-compose up -d

# Run all tests
docker-compose exec itsm python -m pytest

# Run with verbose output
docker-compose exec itsm python -m pytest -v

# Run with coverage
docker-compose exec itsm python -m pytest --cov=ServiceCatalogue --cov-report=term-missing

# Run specific test file
docker-compose exec itsm python -m pytest ServiceCatalogue/tests.py

# Run specific test class
docker-compose exec itsm python -m pytest ServiceCatalogue/tests.py::ServiceModelTest

# Run specific test method
docker-compose exec itsm python -m pytest ServiceCatalogue/tests.py::ServiceModelTest::test_service_creation
```

**Quick test without running containers:**

```bash
docker-compose run --rm itsm python -m pytest -v
```

### Option 2: Local Python Environment (Advanced)

If you want to run tests outside Docker:

**Prerequisites:**
- Python 3.10, 3.11, or 3.12
- PostgreSQL 15 with extensions
- System dependencies

**Setup:**

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get install -y \
    postgresql-15 \
    postgresql-contrib-15 \
    libpq-dev \
    libldap2-dev \
    libsasl2-dev \
    libssl-dev

# Enable PostgreSQL extensions
sudo -u postgres psql -c "CREATE DATABASE test_itsm;"
sudo -u postgres psql -d test_itsm -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
sudo -u postgres psql -d test_itsm -c "CREATE EXTENSION IF NOT EXISTS btree_gin;"

# Create Python virtual environment
cd apps/itsm
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
pip install pytest pytest-django pytest-cov

# Set environment variables
export DB_HOST=localhost
export DB_PORT=5432
export POSTGRES_DATABASE=test_itsm
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=your_postgres_password
export DJANGO_SECRET_KEY=test-secret-key
export DJANGO_SETTINGS_MODULE=itsm_config.settings_test

# Run tests
pytest -v
```

**Important**: The PostgreSQL database must have the `pg_trgm` extension enabled for the GIN indexes used in full-text search.

## Running Tests on GitHub Actions

Tests run automatically on every push and pull request. GitHub Actions tests against Python 3.10, 3.11, and 3.12 simultaneously.

### Local vs GitHub Actions

| Aspect | Local Docker | GitHub Actions |
|--------|-------------|----------------|
| **Speed** | Fast (runs on your machine) | Slower (cloud runners) |
| **Setup** | Already configured | Automatic |
| **Cost** | Free | Free (with limits) |
| **Matrix Testing** | One Python version at a time | Tests 3.10, 3.11, 3.12 simultaneously |
| **When to use** | During development | Before merging, on push |

### Recommended Workflow

1. **During development**: Use local Docker tests for immediate feedback
2. **Before committing**: Run with coverage to verify your changes
3. **Before pushing**: Ensure all tests pass locally
4. **After pushing**: GitHub Actions validates across all Python versions

## Test Configuration

### pytest.ini

The pytest configuration is in `apps/itsm/pytest.ini`:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = itsm_config.settings_test
testpaths = ServiceCatalogue
addopts = --verbose --strict-markers --tb=short -p no:warnings
```

### Test Settings

Test-specific Django settings are in `apps/itsm/itsm_config/settings_test.py`:

- Uses simplified password hashing for faster tests
- Disables caching
- Uses in-memory email backend
- Simplified authentication (no Keycloak/SSO)

## Continuous Integration

### GitHub Actions Workflow

Tests run automatically on every push and pull request via GitHub Actions (`.github/workflows/django-tests.yml`).

The CI workflow:
1. Sets up PostgreSQL 15 with required extensions (`pg_trgm`, `btree_gin`)
2. Tests against Python 3.10, 3.11, and 3.12 in parallel
3. Runs Django system checks
4. Runs database migrations
5. Executes the full test suite
6. Uploads coverage reports to Codecov

**Status Badge:** Add this to your README to show test status:

```markdown
[![Django Tests](https://github.com/YOUR_USERNAME/REPO_NAME/actions/workflows/django-tests.yml/badge.svg)](https://github.com/YOUR_USERNAME/REPO_NAME/actions/workflows/django-tests.yml)
```

## Writing Tests

### Test Structure

Tests are organized by component in `apps/itsm/ServiceCatalogue/tests.py`:

```python
class ServiceProviderModelTest(TestCase):
    """Test ServiceProvider model"""

    def setUp(self):
        """Create test fixtures"""
        self.provider = ServiceProvider.objects.create(
            hierarchy="1.1",
            name="IT Department",
            acronym="IT"
        )

    def test_service_provider_creation(self):
        """Test creating a service provider"""
        self.assertEqual(self.provider.name, "IT Department")
        self.assertEqual(str(self.provider), "1.1 IT Department (IT)")
```

### Test Markers

Use markers to categorize tests:

```python
import pytest

@pytest.mark.slow
def test_large_dataset_performance():
    """This test is marked as slow"""
    pass

@pytest.mark.integration
def test_complete_workflow():
    """This test is marked as integration"""
    pass
```

Run specific categories:

```bash
# Skip slow tests
pytest -m "not slow"

# Run only integration tests
pytest -m integration
```

### Testing Views

```python
from django.test import Client
from django.urls import reverse

class ServiceListViewTest(TestCase):
    def test_services_listed_view_accessible(self):
        """Test that services listed view is accessible"""
        response = self.client.get(reverse('services_listed'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ServiceCatalogue/services_listed.html')
```

### Testing with Authentication

```python
class AuthenticatedViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_protected_view(self):
        response = self.client.get(reverse('protected_view'))
        self.assertEqual(response.status_code, 200)
```

## Coverage

### Generating Coverage Reports

**With Docker:**

```bash
# Terminal report with missing lines
docker-compose exec itsm python -m pytest --cov=ServiceCatalogue --cov-report=term-missing

# HTML report (interactive)
docker-compose exec itsm python -m pytest --cov=ServiceCatalogue --cov-report=html
# Then copy from container: docker cp itsm:/app/htmlcov ./htmlcov
# Open htmlcov/index.html in browser

# XML report (for CI)
docker-compose exec itsm python -m pytest --cov=ServiceCatalogue --cov-report=xml
```

**Without Docker:**

```bash
# Terminal report
pytest --cov=ServiceCatalogue --cov-report=term-missing

# HTML report
pytest --cov=ServiceCatalogue --cov-report=html
# Open htmlcov/index.html in browser

# XML report (for CI)
pytest --cov=ServiceCatalogue --cov-report=xml
```

### Coverage Goals

- **Minimum**: 70% overall coverage
- **Target**: 85% for models and views
- **Critical paths**: 100% for authentication and authorization

## Testing Specific Components

```bash
# Test only model tests
docker-compose exec itsm python -m pytest ServiceCatalogue/tests.py::ServiceProviderModelTest -v

# Test only view tests
docker-compose exec itsm python -m pytest -k "ViewTest" -v

# Test a specific test method
docker-compose exec itsm python -m pytest ServiceCatalogue/tests.py::ServiceModelTest::test_service_creation -v

# Run tests matching a pattern
docker-compose exec itsm python -m pytest -k "service" -v

# Stop on first failure
docker-compose exec itsm python -m pytest -x
```

## Troubleshooting

### Common Issues

**1. Extension not found: pg_trgm**

The PostgreSQL database needs the `pg_trgm` extension:

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

In Docker, this is handled automatically by `postgres/init/01-init-django-db.sh`.

**2. Database does not exist**

Make sure the database container is running:

```bash
docker-compose ps | grep postgres
docker-compose up -d postgres
```

**3. Permission denied (Docker socket)**

Run Docker commands with sudo or add your user to the docker group:

```bash
sudo docker-compose exec itsm python -m pytest -v
```

**4. Import errors**

Ensure you're running from the correct directory:

```bash
cd apps/itsm
pytest
```

**5. Database connection errors**

Check environment variables:

```bash
echo $DB_HOST $DB_PORT $POSTGRES_DATABASE
```

**6. Migrations not applied**

For fresh test databases, run migrations first:

```bash
python manage.py migrate --settings=itsm_config.settings_test
```

## Test Configuration

### pytest.ini

The pytest configuration is in `apps/itsm/pytest.ini`:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = itsm_config.settings_test
testpaths = ServiceCatalogue
addopts = --verbose --strict-markers --tb=short -p no:warnings
```

### Test Settings

Test-specific Django settings are in `apps/itsm/itsm_config/settings_test.py`:

- Uses simplified password hashing for faster tests
- Disables caching
- Uses in-memory email backend
- Simplified authentication (no Keycloak/SSO)

## Test Data

### Fixtures

Test fixtures are in `apps/itsm/ServiceCatalogue/fixtures/`:

- `initial_test_data.json`: Minimal data for basic tests

Load fixtures:

```bash
python manage.py loaddata initial_test_data
```

### Generating Test Data

Use the management command for comprehensive test data:

```bash
python manage.py populate_test_data
```

This creates realistic service catalogue data including:
- Service providers and categories
- Multiple services with revisions
- Clientele groups and availability
- Fee structures
