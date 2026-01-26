<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
-->

# Configuration Guide

Detailed configuration reference for the ITSM Service Catalogue.

## Environment Variables

All configuration is managed through `env/itsm.env`. Copy from `env/itsm.env.example` to get started.

### Core Settings

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `DJANGO_ENV` | Environment mode | `development` | `production` or `development` |
| `DEBUG` | Enable debug mode | `True` (dev), `False` (prod) | `True` |
| `ALLOWED_HOSTS` | Allowed domains (comma-separated) | `localhost` | `your-domain.com,www.your-domain.com` |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for CSRF | - | `https://your-domain.com` |

### Access Control Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `AUTO_CREATE_USERS` | Auto-create users on SSO login | `True` |
| `STAFF_ONLY_MODE` | Restrict access to staff users | `False` |
| `ONLINE_SERVICES_REQUIRE_LOGIN` | Landing page requires login | `False` |
| `SERVICE_CATALOGUE_REQUIRE_LOGIN` | Catalogue requires login | `True` |
| `AI_SEARCH_REQUIRE_LOGIN` | AI search requires login | `True` |

### Database Settings

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `DB_HOST` | PostgreSQL host | `postgres` | `postgres` |
| `DB_PORT` | PostgreSQL port | `5432` | `5432` |
| `POSTGRES_DATABASE` | Database name | `itsm` | `itsm` |
| `POSTGRES_USER` | Database user | `postgres` | `postgres` |
| `POSTGRES_PASSWORD` | Database password | - | `strong_random_password` |

### Branding & Customization

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `ORGANIZATION_NAME` | Full organization name | - | `Technical University of Example` |
| `ORGANIZATION_ACRONYM` | Short name/acronym | - | `TUE` |
| `LOGO_FILENAME` | Logo file in `overrides/static/logos/` | `logo.png` | `university-logo.png` |
| `PRIMARY_COLOR` | Main brand color (hex, no #) | `0d6efd` | `003366` |
| `SECONDARY_COLOR` | Accent color (hex, no #) | `6610f2` | `0066cc` |

### Contact Information

| Variable | Description | Example |
|----------|-------------|---------|
| `HELPDESK_EMAIL` | Support email address | `support@your-domain.com` |
| `HELPDESK_PHONE` | Support phone number | `+49 123 456789` |

### AI Search Settings

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `AI_SEARCH_ENABLED` | Enable AI-assisted search | `False` | `True` |
| `OPENAI_API_KEY` | OpenAI API key | - | `sk-...` |
| `OPENAI_MODEL` | GPT model to use | `gpt-4o-mini` | `gpt-4o` |

### Performance Settings

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `GUNICORN_WORKERS` | Number of Gunicorn workers | `2` | `4` (formula: 2×CPU+1) |
| `CACHING_TIME_SECONDS` | Template fragment cache time | `300` | `600` |

## Authentication Configuration

### Production Mode (Keycloak SSO)

When `DJANGO_ENV=production`, the application expects to run behind the Edge-Auth Stack with OAuth2-proxy providing authentication headers.

**Required headers from OAuth2-proxy:**
- `X-Remote-User` - Username from Keycloak
- `X-Remote-Email` - Email address from Keycloak

**Login URLs:**
| URL | Purpose |
|-----|---------|
| `/sso-login/` | SSO login endpoint (triggers OAuth2-proxy) |
| `/sso-logout/` | Logout (clears Django + Keycloak sessions) |

**Login flow:**
1. User accesses protected page → redirected to `/sso-login/`
2. nginx intercepts and checks OAuth2-proxy session
3. If not authenticated, OAuth2-proxy redirects to Keycloak
4. After Keycloak login, user returns with session headers
5. Django creates/updates user and redirects to original page

### Development Mode

When `DJANGO_ENV=development`, standard Django authentication is used.

**Login URLs:**
| URL | Purpose |
|-----|---------|
| `/admin/login/` | Django admin login |
| `/sso-logout/` | Logout (redirects to home) |

Create users via Django admin at `/admin/`.

### Access Control

The application provides flexible access control at two levels:
1. **User-level:** Control who can access the system at all
2. **View-level:** Control which views require authentication

#### User Access Control (Initial Setup / Restricted Access)

These settings are useful during initial setup, maintenance periods, or when access should be restricted to a controlled group of users.

| Variable | Description | Default |
|----------|-------------|---------|
| `AUTO_CREATE_USERS` | Automatically create users on first SSO login | `True` |
| `STAFF_ONLY_MODE` | Restrict all access to staff users only | `False` |

**AUTO_CREATE_USERS:**
- When `True` (default): Users are automatically created in Django when they first authenticate via Keycloak/SSO
- When `False`: Only pre-existing users (created manually via Django admin) can log in. New users will see a 403 "Insufficient Privileges" page explaining that their account does not exist

**STAFF_ONLY_MODE:**
- When `False` (default): All authenticated users can access non-staff views
- When `True`: Only users with `is_staff=True` can access the application. Non-staff users see a 403 "Insufficient Privileges" page with their username, options to log out and try a different account, or request privileges from administrators

**Example: Restricted Initial Setup**
```bash
# During initial setup, only allow specific pre-created staff users
AUTO_CREATE_USERS=False
STAFF_ONLY_MODE=True
```

**Example: Staff-Only Maintenance Mode**
```bash
# Allow automatic user creation but restrict access to staff
AUTO_CREATE_USERS=True
STAFF_ONLY_MODE=True
```

#### View Access Control Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ONLINE_SERVICES_REQUIRE_LOGIN` | Online Services landing page (`/sc/`) | `False` (public) |
| `SERVICE_CATALOGUE_REQUIRE_LOGIN` | Service Catalogue (`/sc/services/`) and Service Details (`/sc/service/<id>/`) | `True` (protected) |
| `AI_SEARCH_REQUIRE_LOGIN` | AI-Assisted Search (`/sc/ai-search/`) | `True` (protected) |

**Important:** AI search **always requires login if the service catalogue requires login**, regardless of the `AI_SEARCH_REQUIRE_LOGIN` setting. This prevents information leakage - if services are protected, searching through them must also be protected. The `AI_SEARCH_REQUIRE_LOGIN` setting can only make access MORE restrictive, not less.

#### Default Configuration

With default settings:
- **Public:** Online Services landing page (`/sc/`)
- **Protected:** Service Catalogue, Service Details, AI Search, Admin

#### Examples

Make the full catalogue and service details publicly accessible:
```bash
SERVICE_CATALOGUE_REQUIRE_LOGIN=False
# AI search will also become available to unauthenticated users
# (assuming AI_SEARCH_REQUIRE_LOGIN=False as well)
```

Require login for everything (including landing page):
```bash
ONLINE_SERVICES_REQUIRE_LOGIN=True
```

Keep catalogue protected but make AI search more restrictive:
```bash
SERVICE_CATALOGUE_REQUIRE_LOGIN=True
AI_SEARCH_REQUIRE_LOGIN=True
# Both settings must be True for AI search to require login
# If catalogue is public, AI search can still require login
```

> ⚠️ **Security Warning:** Opening AI search to unauthenticated users requires careful consideration:
> 
> **API Abuse Risks:**
> - Each search consumes API tokens and costs money
> - No rate limiting on unauthenticated requests by default
> - Potential denial of service through excessive requests
> - No user accountability for searches (anonymous usage)
> 
> **Information Leakage Prevention:**
> - AI search automatically requires login if `SERVICE_CATALOGUE_REQUIRE_LOGIN=True`
> - This prevents unauthenticated users from searching protected services
> - To make AI search public, you must ALSO set `SERVICE_CATALOGUE_REQUIRE_LOGIN=False`
>
> **Recommendation:** If you enable public AI search, implement additional rate limiting at the nginx or network level.

#### Visual Indicators

Menu items requiring login show a lock icon (🔒) when users are not authenticated. The lock icon automatically disappears after login, and only appears if the corresponding view actually requires authentication based on the settings.

## Customization

### Logo

1. Place your logo in `overrides/static/logos/`
2. Recommended format: PNG with transparency, approximately 400×80px
3. Set `LOGO_FILENAME=your-logo.png` in `env/itsm.env`
4. Enable the override: `cp docker-compose.override.yml.example docker-compose.override.yml`
5. Restart: `docker-compose up -d`

The `docker-compose.override.yml` file is automatically merged by Docker Compose:

```yaml
services:
  itsm:
    volumes:
      - ./overrides/static:/app/overrides/static:ro
```

See [overrides/README.md](../overrides/README.md) for detailed customization instructions.

### Brand Colors

Colors are specified as hex values without the `#` symbol:

```bash
PRIMARY_COLOR=003366      # Main brand color (buttons, links)
SECONDARY_COLOR=0066cc    # Accent color
```

### LaTeX Templates

Custom PDF templates can be placed in `overrides/latex_templates/`. See [overrides/README.md](../overrides/README.md) for customization instructions and the built-in templates in `apps/itsm/ServiceCatalogue/templates/ServiceCatalogue/latex/` for reference.

## Project Structure

```
.
├── apps/itsm/               # Django application
│   ├── itsm_config/        # Settings and custom auth backend
│   ├── ServiceCatalogue/   # Main app
│   │   ├── ai_prompts/     # AI search prompt templates
│   │   ├── fixtures/       # Sample data
│   │   ├── management/     # Django management commands
│   │   ├── migrations/     # Database migrations
│   │   ├── templates/      # HTML templates
│   │   └── templatetags/   # Custom template tags
│   └── static/             # Default static files
├── docs/                    # Documentation
│   ├── CONFIGURATION.md    # This file
│   ├── DEPLOYMENT.md       # Deployment guide
│   ├── LOGIN_FLOW.md       # Authentication flow
│   └── LOGOUT_KEYCLOAK.md  # Keycloak logout setup
├── env/
│   ├── itsm.env            # Configuration (create from example)
│   └── itsm.env.example    # Example configuration
├── nginx/                   # nginx configuration
├── overrides/               # Organization-specific customizations
│   ├── static/logos/       # Custom logo
│   └── latex_templates/    # Custom PDF templates
├── postgres/
│   └── init/               # Database initialization scripts
└── docker-compose.yml
```

## Common Management Tasks

### Django Commands

```bash
# Django shell
docker-compose exec itsm python manage.py shell

# Database migrations
docker-compose exec itsm python manage.py migrate

# Collect static files
docker-compose exec itsm python manage.py collectstatic --noinput

# Create superuser
docker-compose exec itsm python manage.py createsuperuser
```

### Data Management

```bash
# Export catalogue data (JSON)
docker-compose exec itsm python manage.py export_data --format json

# Import catalogue data
docker-compose exec itsm python manage.py import_data backup.json

# Load sample data
docker-compose exec itsm python manage.py populate_test_data

# Backup PostgreSQL
docker-compose exec postgres pg_dump -U postgres itsm > backup.sql
```

### Service Management

```bash
# View logs
docker-compose logs -f itsm

# Restart services
docker-compose restart itsm
docker-compose restart nginx

# Stop all services
docker-compose down

# Rebuild after changes
docker-compose build itsm
docker-compose up -d
```

## Sample Data

The `populate_test_data` command loads generic university service catalogue data:

- **4 permission groups** - Editors, Publishers, Administrators, Viewers
- **4 clientele groups** - Students, Staff, Researchers, External
- **5 categories** - Communication, Data, Infrastructure, Computing, Identity
- **14 services** - Email, File Sharing, Wiki, Video Conferencing, HPC, Cloud, etc.

All data uses localhost URLs. Customize via Django admin after loading.

## Troubleshooting

### Static files not loading

```bash
docker-compose exec itsm python manage.py collectstatic --noinput --clear
docker-compose restart nginx
```

### Database connection issues

```bash
docker-compose exec itsm python manage.py check --database default
docker-compose logs postgres
```

### "Proxy network not found"

```bash
docker network create proxy
docker-compose up -d
```

### Container won't start

```bash
docker-compose logs itsm
docker-compose config  # Validate configuration
```

## Technology Stack

- **Django 5.2** - Web framework
- **Python 3.11** - Programming language
- **PostgreSQL 15** - Database with full-text search
- **Gunicorn** - WSGI application server
- **nginx** - Reverse proxy and static file serving
- **django-modeltranslation** - Database-level translations
- **django-tex** - LaTeX PDF generation
- **OpenAI-compatible API** - AI-assisted search (GWDG chat-ai, KISSKI, OpenAI, etc.)
