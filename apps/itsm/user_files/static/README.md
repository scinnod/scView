<!--
SPDX-License-Identifier: AGPL-3.0-or-later
SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
-->

# Static Files Directory

This directory contains static files for organization-specific branding.

## Directory Structure

```
static/
├── README.md      # This file
├── logos/         # Organization logos
├── css/           # Custom stylesheets
└── images/        # Additional images
```

## Customization

### Recommended: Use Overrides

Place your files in `overrides/static/` and mount via `docker-compose.override.yml`:

```yaml
- ./overrides/static/logos:/app/user_files/static/logos:ro
```

This keeps organization files separate from the repository.

### Logos

| File | Purpose |
|------|---------|
| `logo.png` | Primary logo (web header, PDF) |
| `favicon.ico` | Browser favicon |

**Configuration:** Set `LOGO_FILENAME=logo.png` in `env/itsm.env`

### Custom CSS

Create `css/custom.css` for branding:

```css
:root {
  --primary-color: #0066cc;
}

.navbar {
  background-color: var(--primary-color) !important;
}
```

## After Changes

```bash
docker-compose exec itsm python manage.py collectstatic --noinput
docker-compose restart itsm nginx
```

## See Also

- [../README.md](../README.md) - User files overview
- [overrides/README.md](../../../../overrides/README.md) - Override directory
