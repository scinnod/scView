# Contributing Guide

This document outlines development guidelines and design principles for this Django project.

## Development Philosophy

- **Simplicity**: Keep solutions straightforward - avoid over-engineering
- **Django Best Practices**: Follow Django's recommended patterns
- **Docker-Native**: Solutions should work naturally in containerized environments
- **Portability**: Code runs identically in dev, staging, and production

## Django Framework

### Version Compliance

- Use **latest Django LTS version**
- **Never use deprecated methods** - check Django docs for current LTS
- Stay informed about deprecation warnings
- Test compatibility when upgrading

### Project Organization

Follow Django's recommended structure:
- Apps should be focused and single-purpose
- Settings organized via environment variables
- Static files managed through Django's system
- Templates in app directories
- Management commands in `management/commands/`

## Internationalization

**All user-facing text must be translatable:**
- Use `gettext_lazy()` or `_()` for strings
- Mark template strings with `{% trans %}` or `{% blocktrans %}`
- Maintain `.po` files for all supported languages
- Compile to `.mo` files before deployment
- Console/log output excluded from translation

## Code Quality

### Comments

- Explain **what** and **why**, not detailed implementation
- **Do not reveal system internals:**
  - ✗ Don't mention: "Django framework", "DeepL API", specific packages
  - ✓ Do mention: "Validates input", "Formats date", "Handles submission"
- Keep comments concise and relevant

### Clean Code

- No workarounds or hacks - use proper solutions
- Write maintainable code others can understand
- Optimize for performance without premature optimization
- Prefer straightforward solutions over clever tricks

## Docker & Deployment

### Docker Compose

- Include `docker-compose.yml` for orchestration
- Services run in `proxy` network without encryption
- Default internal port: **8000**
- Designed for upstream proxy (nginx proxy manager, Traefik, Caddy)
- Include **nginx service** for static files and proxying
- Use network isolation:
  - `proxy`: External network for upstream proxy
  - Internal networks: For service-to-service communication

### Dockerfile

- Use **python:3.x-slim** for Django apps
- Use **Alpine images** for supporting services (e.g., `nginx:alpine`)
- Minimize layers and image size
- Set proper permissions

### Entrypoint Script

The entrypoint must handle **automatic secret generation:**

```bash
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
fi

export DJANGO_SECRET_KEY=$(cat "$SECRET_KEY_FILE")

python manage.py migrate --noprofile
python manage.py collectstatic --noinput --clear

exec "$@"
```

**Key requirements:**
- Secret key path: `/secrets/django_secret_key`
- Store secrets outside app directory
- Generate if missing, export to environment
- Never hardcode secrets

### Docker Best Practices

- Use volumes for persistent data (databases, secrets, uploads)
- Mount secrets outside app directory (`/secrets/`)
- Use networks for service isolation
- Configure via environment variables
- Never mount code in production
- Use health checks for monitoring

## Database

- **SQLite**: Small projects, low concurrency
- **PostgreSQL**: Production, higher load
- Configuration via environment variables
- All migrations must be version-controlled

## Testing

- Write tests for business logic and critical paths
- Test with production database engine
- Test in containerized environment
- Ensure migrations are reversible

## Version Control

- **Mercurial** for version control
- Clear, descriptive commit messages
- Never commit secrets or credentials
- Maintain `.hgignore` for artifacts
- Document breaking changes

## Code Review Checklist

- ✓ Uses latest Django LTS (no deprecated code)
- ✓ User-facing strings are translatable
- ✓ Follows Django conventions
- ✓ Works in Docker environment
- ✓ Configuration via environment variables
- ✓ Comments helpful but don't reveal internals
- ✓ Code is simple and maintainable
- ✓ No hardcoded secrets

## Documentation

- Maintain essential documentation (README, guides)
- Document complex or non-obvious behavior
- Focus on practical guides
- Avoid excessive documentation for routine changes
