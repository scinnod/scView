<!--
SPDX-License-Identifier: AGPL-3.0-or-later
SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
-->

# ITSM Service Catalogue

A Django-based IT Service Management (ITSM) service catalogue application with multilingual support, Keycloak SSO authentication, and PDF export capabilities.

**Author:** David Kleinhans, [Jade University of Applied Sciences](https://www.jade-hs.de/)  
**License:** [AGPL-3.0-or-later](LICENSE)  
**Contact:** david.kleinhans@jade-hs.de

## Features

- 📚 Hierarchical service catalogue with versioning
- 🌍 Multilingual support (German/English)
- 🔐 Keycloak SSO via OAuth2-proxy (production) and simple auth (development)
- 📄 PDF export via LaTeX integration
- 🔍 Full-text search with PostgreSQL
- 🐳 Docker-based deployment with upstream proxy support
- 🎨 Corporate identity customization

## Quick Start

### Prerequisites

- Docker and Docker Compose
- [Edge-Auth Stack](https://github.com/YOUR_USERNAME/edge-auth-stack) for production (Keycloak SSO)
  - See [docs/LOGIN_FLOW.md](docs/LOGIN_FLOW.md) for authentication details

### Installation

1. **Create external proxy network:**
   ```bash
   docker network create proxy
   ```

2. **Configure environment:**
   ```bash
   cp env/itsm.env.example env/itsm.env
   # Edit env/itsm.env with your settings
   ```

3. **Add branding (optional):**
   ```bash
   # Add your logo
   cp /path/to/logo.png apps/itsm/user_files/static/logos/logo.png
   
   # Update env/itsm.env:
   # ORGANIZATION_NAME=Your Organization
   # ORGANIZATION_ACRONYM=ORG
   # LOGO_FILENAME=logo.png
   # PRIMARY_COLOR=0d6efd
   ```

4. **Start services:**
   ```bash
   docker-compose up -d
   ```

5. **Initialize database:**
   ```bash
   # Create admin user
   docker-compose exec itsm python manage.py createsuperuser
   
   # Load sample data (optional)
   docker-compose exec itsm python manage.py populate_test_data
   ```

6. **Configure upstream proxy** to route your domain to `itsm_nginx:80`
   - In production, configure OAuth2-proxy to pass `X-Remote-User` and `X-Remote-Email` headers
   - See the [Edge-Auth Stack documentation](https://github.com/YOUR_USERNAME/edge-auth-stack) for configuration

### Development Mode

```bash
# In env/itsm.env:
DJANGO_ENV=development
FORCE_SCRIPT_NAME=/dev

# Access at http://localhost/dev/
```

## Architecture

```
Internet
   ↓
Upstream Proxy (SSL/TLS termination + OAuth2-proxy + Keycloak)
   ↓ [proxy network]
nginx (static files, reverse proxy)
   ↓ [app_itsm network]
Django + Gunicorn
   ↓ [net_db network]
PostgreSQL 15
```

**Security features:**
- Three-tier network isolation
- Secrets in Docker volumes
- SSL/TLS at edge (upstream proxy)
- Keycloak SSO authentication (production)
- No direct database access from outside

## Authentication

This service is designed to work behind the [Edge-Auth Stack](https://github.com/YOUR_USERNAME/edge-auth-stack) - a production-ready authentication gateway combining nginx, Keycloak SSO, and OAuth2-proxy.

### Prerequisites

1. Deploy the Edge-Auth Stack first
2. Configure Keycloak realm and client
3. Set up nginx virtual host (see edge-auth-stack documentation)

### Authentication Pattern

This service uses **Pattern A** (Django-controlled) authentication:
- Django decides which pages require authentication via `@login_required` decorator
- Public pages are accessible without authentication
- Protected pages trigger Keycloak login via `/sso-login/` endpoint

See the [Edge-Auth Stack Django Integration Guide](https://github.com/YOUR_USERNAME/edge-auth-stack/blob/main/docs/django-integration.md) for detailed configuration.

### Production Mode
- **Keycloak SSO** via OAuth2-proxy (upstream authentication)
- **Login URL:** `/sso-login/`
- Users automatically created from Keycloak on first login
- Email addresses populated from Keycloak
- Username from Keycloak used as unique identifier
- Login flow:
  1. User accesses protected page → redirected to `/sso-login/`
  2. nginx intercepts and checks OAuth2-proxy session
  3. If not authenticated, OAuth2-proxy redirects to Keycloak
  4. After Keycloak login, user returns with session headers
  5. Django creates/updates user and redirects to original page

### Development Mode
- Django's built-in authentication (username/password)
- **Login URL:** `/admin/login/` (Django admin login)
- Create users via Django admin (`/admin/`)
- Login flow:
  1. User accesses protected page → redirected to `/admin/login/`
  2. User enters username/password
  3. Django authenticates and redirects to original page

**Important:** The `/sso-login/` endpoint is **not used in development mode** to avoid interference from the downstream proxy server, which may intercept this path for external authentication.

### Login URLs Reference

| URL | Purpose | Environment |
|-----|---------|-------------|
| `/sso-login/` | SSO login endpoint | Production only |
| `/admin/login/` | Django admin login | Development (and production fallback) |
| `/sc/login_required` | Login landing page (info messages) | Both (optional) |
| `/sso-logout/` | Logout endpoint | Both |

For detailed authentication configuration, see [docs/LOGIN_FLOW.md](docs/LOGIN_FLOW.md).

## Project Structure

```
.
├── apps/itsm/               # Django application
│   ├── itsm_config/        # Settings and custom auth backend
│   ├── ServiceCatalogue/   # Main app
│   └── user_files/         # Customization files (logos, LaTeX templates)
├── docs/                    # Documentation
│   ├── DEPLOYMENT.md       # Comprehensive deployment guide
│   ├── LOGIN_FLOW.md       # Authentication flow documentation
│   └── LOGOUT_KEYCLOAK.md  # Keycloak logout configuration
├── env/
│   ├── itsm.env            # Configuration (create from example)
│   └── itsm.env.example    # Example configuration
├── nginx/                   # nginx config
├── postgres/
│   └── init/               # Database initialization
└── docker-compose.yml
```

## Common Tasks

### Management Commands

```bash
# Django shell
docker-compose exec itsm python manage.py shell

# Database migrations
docker-compose exec itsm python manage.py migrate

# Collect static files
docker-compose exec itsm python manage.py collectstatic
```

### Data Management

```bash
# Export data (JSON/SQL)
docker-compose exec itsm python manage.py export_data --format json

# Import data
docker-compose exec itsm python manage.py import_data backup.json

# Backup database
docker-compose exec postgres pg_dump -U postgres itsm > backup.sql
```

### Service Management

```bash
# View logs
docker-compose logs -f itsm

# Restart service
docker-compose restart itsm

# Stop all services
docker-compose down
```

## Configuration

Key environment variables in `env/itsm.env`:

| Variable | Description | Example |
|----------|-------------|---------|
| `DJANGO_ENV` | Environment mode | `production` or `development` |
| `ALLOWED_HOSTS` | Allowed domains | `your-domain.com` |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins | `https://your-domain.com` |
| `ORGANIZATION_NAME` | Organization name | `Technical University` |
| `ORGANIZATION_ACRONYM` | Short name | `TU` |
| `PRIMARY_COLOR` | Brand color (hex) | `0d6efd` |
| `LOGO_FILENAME` | Logo file | `logo.png` |

See `env/itsm.env.example` for complete list.

## Customization

### User Files

The project has two `user_files/` directories:

| Location | Purpose | Git Status |
|----------|---------|------------|
| `user_files/` (project root) | Organization-specific files | **Gitignored** |
| `apps/itsm/user_files/` | Templates and examples | **Tracked** |

For production deployments, use `docker-compose.override.yml` to mount your organization's files. See [apps/itsm/user_files/README.md](apps/itsm/user_files/README.md) for details.

### Brand Colors

```bash
# In env/itsm.env:
PRIMARY_COLOR=0d6efd      # Main brand color (no # symbol)
SECONDARY_COLOR=6610f2    # Accent color
```

Colors apply to buttons, links, badges, and UI accents throughout the interface.

### Logo

1. Place logo in `apps/itsm/user_files/static/logos/`
2. Recommended: PNG with transparency, 400x80px
3. Set `LOGO_FILENAME=logo.png` in env file
4. Restart: `docker-compose restart itsm`

### Contact Information

```bash
HELPDESK_EMAIL=support@your-domain.com
HELPDESK_PHONE=+1-555-1234
```

## Sample Data

The `populate_test_data` command loads generic university service catalogue data:

- **4 permission groups** - Editors, Publishers, Administrators, Viewers
- **4 clientele groups** - Students, Staff, Researchers, External
- **5 categories** - Communication, Data, Infrastructure, Computing, Identity
- **14 services** - Email, File Sharing, Wiki, Video Conferencing, HPC, Cloud, etc.

All data is generic with localhost URLs. Customize via Django admin after loading.

## Technology Stack

- **Django 5.2.8** - Web framework
- **Python 3.11** - Programming language
- **PostgreSQL 15** - Database
- **Gunicorn** - WSGI server
- **nginx** - Reverse proxy and static files
- **django-modeltranslation** - Database translations
- **django-tex** - LaTeX PDF generation
- **Keycloak** - SSO authentication (production, via upstream OAuth2-proxy)

## Documentation

- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Comprehensive deployment guide
- **[docs/LOGIN_FLOW.md](docs/LOGIN_FLOW.md)** - Authentication flow documentation
- **[docs/LOGOUT_KEYCLOAK.md](docs/LOGOUT_KEYCLOAK.md)** - Keycloak logout configuration
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Development guidelines and design principles
- **[SECURITY.md](SECURITY.md)** - Security policy and vulnerability reporting

## Troubleshooting

### Static files not loading
```bash
docker-compose exec itsm python manage.py collectstatic --noinput --clear
docker-compose restart nginx
```

### Database connection issues
```bash
docker-compose exec itsm python manage.py check --database default
```

### "Proxy network not found"
```bash
docker network create proxy
docker-compose up -d
```

## Security

- Auto-generated Django secret key (stored in volume)
- Network isolation (proxy → app → database)
- SSL/TLS handled by upstream proxy
- Keycloak SSO via OAuth2-proxy in production
- RemoteUserBackend authentication (trusted proxy headers)

## License

This project is licensed under the **GNU Affero General Public License v3.0 or later** (AGPL-3.0-or-later).

See [LICENSE](LICENSE) for the full license text.

## Author & Support

**Author:** David Kleinhans  
**Affiliation:** [Jade University of Applied Sciences](https://www.jade-hs.de/)  
**Contact:** david.kleinhans@jade-hs.de

This is a university infrastructure project with limited external support capacity.

For issues or questions:
- Check logs: `docker-compose logs -f`
- Verify config: `docker-compose config`
- Review documentation in this repository
- Report issues via GitHub Issues

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines and [SECURITY.md](SECURITY.md) for security policy.
