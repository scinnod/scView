# ITSM Service Catalogue

A Django-based IT Service Management (ITSM) service catalogue application with multilingual support, Keycloak SSO authentication, and PDF export capabilities.

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
- Upstream authentication stack (nginx + OAuth2-proxy + Keycloak)
  - See [DJANGO_INTEGRATION.md](DJANGO_INTEGRATION.md) for authentication setup

### Installation

1. **Create external proxy network:**
   ```bash
   docker network create proxy
   ```

2. **Configure environment:**
   ```bash
   cp env/itsm.env.production.example env/itsm.env
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
   - See [DJANGO_INTEGRATION.md](DJANGO_INTEGRATION.md) for detailed authentication configuration

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

### Production Mode
- **Keycloak SSO** via OAuth2-proxy (upstream authentication)
- Users automatically created from Keycloak on first login
- Email addresses populated from Keycloak
- Username from Keycloak used as unique identifier

### Development Mode
- Django's built-in authentication (username/password)
- Create users via Django admin

For detailed authentication configuration, see [DJANGO_INTEGRATION.md](DJANGO_INTEGRATION.md)

## Project Structure

```
.
├── apps/itsm/               # Django application
│   ├── itsm_config/        # Settings and custom auth backend
│   ├── ServiceCatalogue/   # Main app
│   └── user_files/         # Customization files
│       ├── static/logos/   # Your logos
│       └── latex_templates/
├── env/
│   └── itsm.env           # Configuration
├── nginx/                  # nginx config
├── postgres/
│   └── dumps/             # Database backups
├── DJANGO_INTEGRATION.md   # Authentication documentation
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

See `env/itsm.env.production.example` for complete list.

## Customization

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

- **[DJANGO_INTEGRATION.md](DJANGO_INTEGRATION.md)** - Authentication setup and configuration
- **[DJANGO_QUICKREF.md](DJANGO_QUICKREF.md)** - Quick reference for Django + Keycloak
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Development guidelines and design principles
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Comprehensive deployment guide

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

[Add your license here]

## Support

For issues or questions:
- Check logs: `docker-compose logs -f`
- Verify config: `docker-compose config`
- Review documentation in this repository
