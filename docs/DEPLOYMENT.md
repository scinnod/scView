<!--
SPDX-License-Identifier: AGPL-3.0-or-later
SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
-->

# Deployment Guide

Comprehensive guide for deploying the ITSM Service Catalogue with Docker and an upstream proxy.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Upstream Proxy (nginx proxy manager, Traefik, etc.)    │
│ - SSL/TLS termination                                   │
│ - Domain routing                                        │
│ - Network: proxy (external)                             │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│ nginx (itsm_nginx)                                      │
│ - Serves static files                                   │
│ - Proxies to Django                                     │
│ - Networks: proxy, app_itsm                             │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│ Django App (itsm_app)                                   │
│ - Gunicorn on port 8000                                 │
│ - Networks: app_itsm, net_db                            │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│ PostgreSQL (postgres)                                   │
│ - Network: net_db (internal only)                       │
└─────────────────────────────────────────────────────────┘
```

## Network Security

### Three-Tier Isolation

1. **External Layer (proxy network)**
   - Only nginx container
   - Accessible from upstream proxy
   - No database or Django access

2. **Application Layer (app_itsm network)**
   - nginx ↔ Django communication
   - Internal only
   - No database access from nginx

3. **Database Layer (net_db network)**
   - Django ↔ PostgreSQL only
   - No access from nginx or proxy

### Access Control

The application uses Django-based authorization (not proxy-level authentication).

**Public pages (no authentication required):**
- Online Services landing page: `/sc/`
  - Displays quick links to external online services
  - Search box visible but requires login to use

**Protected pages (authentication required):**
- Service Catalogue: `/sc/services/`
  - Full service catalogue with search
  - All catalogue views (available, upcoming, retired, etc.)
- AI-assisted search: `/sc/ai-search/` (if enabled)
- Service details (internal view): `/sc/service/<id>/internal/`
- All Django admin pages: `/admin/`

**Visual indicators:**
- Menu items requiring login show a lock icon (🔒) when users are not authenticated
- The lock icon disappears after successful login

## Setup Instructions

### 1. Create Proxy Network

```bash
# Only needed once per host
docker network create proxy
```

### 2. Configure Environment

Edit `env/itsm.env`:

**Production:**
```bash
DJANGO_ENV=production
ALLOWED_HOSTS=your-domain.com
CSRF_TRUSTED_ORIGINS=https://your-domain.com
POSTGRES_PASSWORD=strong_random_password
ORGANIZATION_NAME=Your Organization
ORGANIZATION_ACRONYM=ORG
PRIMARY_COLOR=0d6efd
LOGO_FILENAME=logo.png
```

**Development:**
```bash
DJANGO_ENV=development
FORCE_SCRIPT_NAME=/dev
ALLOWED_HOSTS=localhost,itsm.local
CSRF_TRUSTED_ORIGINS=https://localhost
```

### 3. Build and Start

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 4. Configure Upstream Proxy

#### nginx Proxy Manager

1. Create new Proxy Host:
   - **Domain:** `your-domain.com`
   - **Scheme:** `http`
   - **Forward Host:** `itsm_nginx`
   - **Forward Port:** `80`
   - **SSL:** Request Let's Encrypt certificate

#### Traefik

Add labels to nginx in `docker-compose.yml`:

```yaml
nginx:
  labels:
    - "traefik.enable=true"
    - "traefik.http.routers.itsm.rule=Host(`your-domain.com`)"
    - "traefik.http.routers.itsm.entrypoints=websecure"
    - "traefik.http.routers.itsm.tls.certresolver=letsencrypt"
```

#### Caddy

Caddyfile:
```
your-domain.com {
    reverse_proxy itsm_nginx:80
}
```

## Service Management

### Starting/Stopping

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart specific service
docker-compose restart itsm
docker-compose restart nginx
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f itsm
docker-compose logs -f nginx
docker-compose logs -f postgres

# Last 100 lines
docker-compose logs --tail=100 itsm
```

### Django Management

```bash
# Create superuser
docker-compose exec itsm python manage.py createsuperuser

# Run migrations
docker-compose exec itsm python manage.py migrate

# Collect static files
docker-compose exec itsm python manage.py collectstatic --noinput

# Django shell
docker-compose exec itsm python manage.py shell

# Database shell
docker-compose exec itsm python manage.py dbshell
```

## Database Management

### Backup

```bash
# Create backup directory
mkdir -p postgres/dumps

# Take backup
docker-compose exec postgres pg_dump -U postgres itsm > postgres/dumps/backup_$(date +%Y%m%d).sql
```

### Restore

```bash
# Stop Django (close connections)
docker-compose stop itsm

# Restore
docker-compose exec -T postgres psql -U postgres itsm < postgres/dumps/backup.sql

# Restart
docker-compose start itsm
```

### PostgreSQL Shell

```bash
docker-compose exec postgres psql -U postgres -d itsm
```

## Volumes

### Persistent Data

- **`postgres_data`**: Database files
- **`staticfiles_itsm`**: Static files (CSS/JS/images)
- **`django_secrets`**: Secret key (mounted at `/secrets`)

### Backup Volumes

```bash
# Backup volume data
docker run --rm \
  -v 2_itsm_postgres_data:/source \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/postgres_$(date +%Y%m%d).tar.gz -C /source .
```

## Performance Tuning

### Gunicorn Workers

Adjust in `env/itsm.env`:
```bash
GUNICORN_WORKERS=4  # Formula: (2 x CPU cores) + 1
```

### PostgreSQL Memory

In `docker-compose.yml`:
```yaml
postgres:
  shm_size: '512mb'  # Adjust based on RAM
```

## Security

### Secret Management

- Django secret key auto-generated on first run
- Stored in `/secrets/django_secret_key` volume
- Never in code or environment files
- Regenerate: `docker-compose down -v && docker-compose up -d`

### File Permissions

```bash
# Set ownership
chown -R 1000:1000 apps/itsm

# Protect secrets
chmod 600 env/itsm.env
```

## Monitoring

### Health Checks

```bash
# Check Django
docker-compose exec itsm python manage.py check --database default

# Check PostgreSQL
docker-compose exec postgres pg_isready -U postgres

# Test connectivity
docker-compose exec itsm nc -zv postgres 5432
docker-compose exec nginx nc -zv itsm 8000
```

### Resource Usage

```bash
# Real-time stats
docker stats itsm_app itsm_nginx postgres

# Disk usage
docker system df -v
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs itsm

# Validate config
docker-compose config

# Check environment
docker-compose exec itsm env | grep DJANGO
```

### Static Files Not Loading

```bash
# Recollect
docker-compose exec itsm python manage.py collectstatic --noinput --clear

# Verify volume
docker-compose exec nginx ls -la /vol/staticfiles_itsm/

# Restart nginx
docker-compose restart nginx
```

### Database Connection Errors

```bash
# Check database running
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Test connection
docker-compose exec postgres psql -U postgres -d itsm -c "SELECT 1"
```

### "Proxy Network Not Found"

```bash
docker network create proxy
docker-compose up -d
```

## Testing

```bash
# Run all tests
docker-compose -f docker-compose.test.yml run --rm test

# With coverage
docker-compose -f docker-compose.test.yml run --rm test sh -c "
  coverage run --source='.' manage.py test &&
  coverage report
"
```

## Updates

### Update Dependencies

```bash
# Edit requirements.txt
# Rebuild
docker-compose build itsm

# Apply migrations
docker-compose exec itsm python manage.py migrate

# Restart
docker-compose restart itsm
```

### Update nginx

```bash
docker-compose pull nginx
docker-compose up -d nginx
```

## Production Checklist

Before deploying to production:

- [ ] Set `DJANGO_ENV=production`
- [ ] Configure `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`
- [ ] Set strong PostgreSQL password
- [ ] Create `proxy` network
- [ ] Configure upstream proxy (SSL/TLS)
- [ ] Set up database backup cron job
- [ ] Configure monitoring/alerts
- [ ] Test Keycloak SSO authentication
- [ ] Adjust `GUNICORN_WORKERS`
- [ ] Set up log rotation
- [ ] Document recovery procedures
- [ ] Test backup/restore procedures

## Backup Strategy

### Recommended Schedule

```bash
# Daily database backup (add to crontab)
0 2 * * * cd /path/to/project && docker-compose exec -T postgres pg_dump -U postgres itsm > postgres/dumps/daily_$(date +%Y%m%d).sql

# Weekly full volume backup
0 3 * * 0 cd /path/to/project && docker run --rm -v 2_itsm_postgres_data:/source -v /backup:/backup alpine tar czf /backup/weekly_$(date +%Y%m%d).tar.gz -C /source .
```

### ServiceCatalogue Data

```bash
# Export as JSON (version control friendly)
docker-compose exec itsm python manage.py export_data --format json

# Commit to git
git add servicecatalogue_backup_*.json
git commit -m "ServiceCatalogue backup"
```

## Request Flow

### Production (Keycloak SSO)

```
User → HTTPS → Edge-Auth Stack (SSL + OAuth2-proxy + Keycloak)
              → HTTP → nginx (static or proxy?)
                     → Static: Serve from volume
                     → Dynamic: HTTP → Django (RemoteUser auth)
                                     → PostgreSQL
                                     → Render response
```

### Development

```
User → HTTP → nginx (/dev/static or /dev/*)
            → Static: Serve from volume
            → Dynamic: HTTP → Django (simple auth)
                            → PostgreSQL
                            → Render response
```

## Port Configuration

| Service | Internal Port | Exposed To | Purpose |
|---------|--------------|------------|---------|
| nginx | 80 | proxy network | Upstream proxy |
| Django | 8000 | app_itsm network | nginx only |
| PostgreSQL | 5432 | net_db network | Django only |

**No ports exposed to host!**
