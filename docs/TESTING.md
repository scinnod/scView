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

### Option 1: With Docker Compose Test Configuration (Recommended)

The easiest and most reliable way - uses a dedicated test database with proper permissions:

```bash
# Run all tests with coverage
docker-compose -f docker-compose.test.yml run --rm test

# Run tests and keep containers for inspection
docker-compose -f docker-compose.test.yml up

# Clean up test containers and volumes
docker-compose -f docker-compose.test.yml down -v
```

This test configuration:
- Uses `postgres` superuser (can create test databases)
- Installs test dependencies automatically
- Runs pytest with coverage reporting
- Uses tmpfs for faster database operations

### Option 2: With Production Docker Containers

If you want to run tests in the production containers (requires manual setup):

```bash
# Make sure containers are running
docker-compose up -d

# Install test dependencies (temporary, lost on container restart)
docker-compose exec itsm pip install -r requirements-test.txt

# Grant database creation permission (needed for Django test database)
docker-compose exec postgres psql -U postgres -c "ALTER USER itsm_user CREATEDB;"

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

# Run with verbose output and stop on first failure
docker-compose exec itsm python -m pytest -vx
```

**Important**: Production containers use `itsm_user` which doesn't have CREATEDB permission by default. You'll get "permission denied to create database" errors unless you grant it (see above).

### Option 3: Local Python Environment (Advanced)

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
pip install -r requirements.txt -r requirements-test.txt

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
[![Django Tests](https://github.com/scinnod/scview/actions/workflows/django-tests.yml/badge.svg)](https://github.com/scinnod/scview/actions/workflows/django-tests.yml)
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

## Management Command Tests

The test suite includes dedicated test classes for the operational management commands.  All HTTP calls are mocked so the tests run without network access.

### `CheckUrlsCommandTest`

Tests for `python manage.py check_urls` (`ServiceCatalogue/management/commands/check_urls.py`):

| Test class / method | What it verifies |
|---------------------|-----------------|
| `ExtractUrlsHelperTest` | Unit tests for the `_extract_urls()` helper (edge cases: empty input, multiple URLs, trailing punctuation, scheme filtering) |
| `CheckUrlsCommandTest.test_command_runs_without_data` | Command completes cleanly when no listed revisions exist |
| `test_url_field_checked` | `ServiceRevision.url` URLField is collected and checked |
| `test_404_url_reported_as_broken` | 404 responses cause exit code 1 and appear in the report |
| `test_403_not_reported_by_default` | 403 responses are NOT flagged without `--include-403` |
| `test_403_reported_with_flag` | 403 responses ARE flagged with `--include-403` |
| `test_connection_error_reported_as_broken` | Network errors are included in the broken-URL report |
| `test_urls_in_text_fields_extracted` | Plain URLs in text fields (e.g. `details_en`) are discovered |
| `test_duplicate_urls_deduplicated` | The same URL in multiple fields is only requested once |
| `test_head_405_falls_back_to_get` | HEAD 405 triggers a GET fallback |

### `TestAiSearchModelListingTest`

Tests for the model-listing step (check 7) added to `python manage.py test_ai_search`:

| Test method | What it verifies |
|-------------|-----------------|
| `test_configured_model_found_in_list` | Check passes and marks the model with "← configured" |
| `test_configured_model_missing_from_list` | Check fails with a helpful message when model is absent |
| `test_models_endpoint_prints_all_available_models` | Every model returned by the API is printed |
| `test_models_endpoint_404_skips_check` | 404 from `/models` is handled gracefully (check skipped) |
| `test_model_override_replaces_configured_model` | `--model` flag overrides configured model; both IDs appear in output |
| `test_model_override_absent_from_list_fails` | `--model` with an unavailable model ID causes exit code 1 |

### `CheckUrlsFilteringTest`

Tests for the default queryset scope of `python manage.py check_urls`:

| Test method | What it verifies |
|-------------|------------------|
| `test_currently_listed_included` | Active listed revisions are scanned by default |
| `test_currently_available_included` | Available-but-unlisted revisions are scanned by default |
| `test_future_listed_included` | Revisions with future `listed_from` are scanned by default |
| `test_future_available_included` | Revisions with future `available_from` are scanned by default |
| `test_no_dates_excluded_by_default` | Unscheduled drafts (no dates) are excluded from default scan |
| `test_no_dates_included_with_all_services` | `--all-services` includes unscheduled drafts |
| `test_past_listed_only_excluded` | Revisions with `listed_until` fully in the past and no availability are excluded |
| `test_past_listed_only_included_with_all_services` | `--all-services` includes past-only revisions |
| `test_listed_with_future_active_availability_included` | Past-listed but still-active availability keeps revision in the default scan |

### `ExtractInternalLinksHelperTest`

Unit tests for the `_extract_internal_links()` helper in `check_urls`:

| Test method | What it verifies |
|-------------|-----------------|
| `test_empty_returns_empty` | Empty string and `None` both return `[]` |
| `test_single_link` | A single `[[KEY-SVC]]` reference is extracted correctly |
| `test_soft_link_no_separator` | A `[[softlink]]` without separator is still extracted |
| `test_multiple_links` | Multiple `[[...]]` in one field are all collected |
| `test_no_links` | Text without any `[[...]]` returns an empty list |
| `test_link_with_version` | Version suffixes like `[[CAT-SVC-2.0]]` are extracted correctly |
| `test_link_with_parentheses_excluded` | `[[not(a)link]]` is not matched (mirrors the template filter) |
| `test_surrounding_text_preserved` | Multiple links in a sentence are all returned |
| `test_mixed_with_http_url` | HTTP URLs alongside `[[...]]` do not interfere with extraction |

### `ClassifyInternalLinkTest`

Unit tests for `_classify_internal_link()` in `templatetags/html_links.py`:

| Test method | What it verifies |
|-------------|-----------------|
| `test_no_keysep_returns_soft` | Link without key separator is classified `_ILINK_SOFT` |
| `test_soft_count_is_always_zero` | Soft classification always returns `match_count=0` |
| `test_broken_when_no_match` | Key with separator but no DB match → `_ILINK_BROKEN` |
| `test_unique_when_one_match` | Key matching exactly one listed revision → `_ILINK_UNIQUE` |
| `test_multi_when_multiple_matches` | Key matching multiple listed revisions → `_ILINK_MULTI` |
| `test_unlisted_revision_not_counted` | Draft revision (no `listed_from`) is not counted |
| `test_expired_revision_not_counted` | Revision with `listed_until` in the past is not counted |

### `CheckInternalLinksCommandTest`

Integration tests for Phase 2 (internal link validation) of `python manage.py check_urls`:

| Test method | What it verifies |
|-------------|-----------------|
| `test_no_internal_links_exits_clean` | Command exits 0 when no `[[...]]` references exist in fields |
| `test_broken_internal_link_exits_1` | A `[[KEY-NOEXIST]]` matching no revision causes exit code 1 |
| `test_soft_link_warning_exit_0` | A `[[softlink]]` without separator generates a warning, exit code stays 0 |
| `test_valid_internal_link_exit_0` | A `[[CAT-SVC]]` pointing to a real listed revision produces exit code 0 |
| `test_internal_links_in_translated_text_fields_detected` | `[[...]]` links in translated fields (e.g. `details_en`) are found |
| `test_broken_and_soft_reported_in_separate_sections` | Broken and soft links each appear in their own output section |
| `test_summary_mentions_internal_links` | Summary line explicitly names broken internal links |
| `test_broken_url_and_broken_ilink_both_exit_1` | Both a broken URL and a broken internal link in one revision cause exit 1 |
