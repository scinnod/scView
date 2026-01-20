<!--
SPDX-License-Identifier: AGPL-3.0-or-later
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
| `LOGO_FILENAME` | Logo file in `user_files/static/logos/` | `logo.png` | `university-logo.png` |
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

**Public pages (no authentication required):**
- Online Services landing page: `/sc/`

**Protected pages (authentication required):**
- Service Catalogue: `/sc/services/`
- AI-assisted search: `/sc/ai-search/` (if enabled)
- Service details (internal view): `/sc/service/<id>/internal/`
- All Django admin pages: `/admin/`

## Customization

### Logo

1. Place your logo in `apps/itsm/user_files/static/logos/`
2. Recommended format: PNG with transparency, approximately 400×80px
3. Set `LOGO_FILENAME=your-logo.png` in `env/itsm.env`
4. Restart: `docker-compose restart itsm`

For production deployments, mount your organization's files via `docker-compose.override.yml`:

```yaml
services:
  itsm:
    volumes:
      - ./user_files/static/logos:/app/user_files/static/logos:ro
```

### Brand Colors

Colors are specified as hex values without the `#` symbol:

```bash
PRIMARY_COLOR=003366      # Main brand color (buttons, links)
SECONDARY_COLOR=0066cc    # Accent color
```

### LaTeX Templates

Custom PDF templates can be placed in `apps/itsm/user_files/latex_templates/`. See [apps/itsm/user_files/README.md](../apps/itsm/user_files/README.md) for template documentation.

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
│   └── user_files/         # Customization files (logos, LaTeX templates)
├── docs/                    # Documentation
│   ├── CONFIGURATION.md    # This file
│   ├── DEPLOYMENT.md       # Deployment guide
│   ├── LOGIN_FLOW.md       # Authentication flow
│   └── LOGOUT_KEYCLOAK.md  # Keycloak logout setup
├── env/
│   ├── itsm.env            # Configuration (create from example)
│   └── itsm.env.example    # Example configuration
├── nginx/                   # nginx configuration
├── postgres/
│   └── init/               # Database initialization scripts
├── user_files/             # Organization-specific files (gitignored)
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
- **OpenAI GPT** - AI-assisted search (optional)
