<!--
SPDX-License-Identifier: AGPL-3.0-or-later
SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
-->

# User Files Directory

This directory contains **customizable files** for organization-specific branding.

## Directory Structure

```
apps/itsm/user_files/
├── README.md              # This file
├── static/
│   ├── logos/             # Organization logo for web and PDF
│   ├── css/               # Custom stylesheets
│   └── images/            # Additional images
└── latex_templates/       # LaTeX templates for PDF export
```

## How Customization Works

The repository ships with empty placeholder directories. To add your organization's files:

### Option 1: Direct Override via Docker (Recommended)

Use `docker-compose.override.yml` to mount your files:

```yaml
# Your files in overrides/static/logos/ replace user_files/static/logos/
- ./overrides/static/logos:/app/user_files/static/logos:ro
```

**Benefits:**
- Organization files stay separate from the repository
- `overrides/` is gitignored, so your files are never committed
- Easy to update the repository without conflicts
- Explicit: the mount shows exactly what's replaced

See [docker-compose.override.yml.example](../../../docker-compose.override.yml.example) for details.

### Option 2: Edit Directly (Development Only)

For quick testing, you can add files directly here:

```bash
cp /path/to/logo.png apps/itsm/user_files/static/logos/logo.png
```

⚠️ **Warning:** These files will be tracked by git unless you add them to `.gitignore`.

## Available Customizations

### Logos (`static/logos/`)

| Setting | Description |
|---------|-------------|
| **Location** | `static/logos/logo.png` |
| **Format** | PNG (with transparency), JPG, or EPS (for LaTeX) |
| **Size** | ~400×80px recommended for web header |
| **Config** | Set `LOGO_FILENAME=logo.png` in `env/itsm.env` |

Used in:
- Web interface navigation header
- PDF exports (via LaTeX)

### Custom CSS (`static/css/`)

Override default styles with your branding colors:

```css
/* custom.css */
:root {
  --primary-color: #0066cc;
  --secondary-color: #ff6600;
}
```

### LaTeX Templates (`latex_templates/`)

Custom fragments for PDF export styling:
- `header.tex` - Page headers
- `footer.tex` - Page footers
- `colors.tex` - Color definitions
- `titlepage.tex` - Title page layout

## After Making Changes

```bash
# Collect static files
docker-compose exec itsm python manage.py collectstatic --noinput

# Restart services
docker-compose restart itsm nginx
```

## See Also

- [overrides/README.md](../../../overrides/README.md) - Override directory documentation
- [docker-compose.override.yml.example](../../../docker-compose.override.yml.example) - Mount configuration
- [static/README.md](static/README.md) - Static files details
- [latex_templates/README.md](latex_templates/README.md) - LaTeX template details
