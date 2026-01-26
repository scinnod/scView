<!--
SPDX-License-Identifier: AGPL-3.0-or-later
SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
-->

# User Files Directory (App-Level)

This directory (`apps/itsm/user_files/`) contains **template and example files** for customization.

## Directory Structure

```
apps/itsm/user_files/
├── static/              # Static files collected by Django
│   └── logos/           # Logo files for web and PDF
├── latex_templates/     # LaTeX template fragments
└── README.md            # This file
```

## Purpose

This directory provides:
1. **Template files** - Example structure for customization
2. **Development files** - Quick testing without external mounts
3. **Fallback content** - Used when no external files are mounted

## Two Ways to Customize

### Option 1: Edit Files Directly (Development)

Edit files in this directory for immediate use:

```bash
# Add your logo
cp /path/to/logo.png apps/itsm/user_files/static/logos/logo.png

# Set in env/itsm.env:
LOGO_FILENAME=logo.png

# Restart to apply
docker-compose restart itsm
```

### Option 2: Mount External Files (Production)

Use `docker-compose.override.yml` to mount organization-specific files:

```yaml
services:
  itsm:
    volumes:
      - /opt/organization/logos:/app/user_files/static/logos:ro
      - /opt/organization/latex:/app/user_files/latex_templates:ro
```

This keeps organization-specific content separate from the application code.

## Logos

Place your organization's logo files here for use in:
- PDF exports (via LaTeX)
- Web interface header

**Supported formats:**
- PNG (recommended for web, supports transparency)
- JPG (good for photos/complex images)
- EPS (vector format for LaTeX, best print quality)

**Recommended specifications:**
- Resolution: 300 DPI for print, 150 DPI for web
- Width: 2000-3000 pixels for flexibility
- Maintain high-resolution source files elsewhere

**Configuration:**
```bash
# In env/itsm.env:
LOGO_FILENAME=your_logo.png
```

## LaTeX Templates

Custom LaTeX fragments for PDF generation:

- Header/footer layouts
- Title page design  
- Font selections
- Color schemes

Place `.tex` files here to customize PDF output.

## Static Files

Additional static files for the web interface:

- Custom CSS for branding
- Organization-specific images
- Custom JavaScript
- Favicon/app icons

Files are served via Django's static file system.

## Version Control

This directory IS tracked in git (unlike `user_files/` at project root).

Files here serve as:
- Examples and templates
- Development placeholders
- Default fallbacks

For production, mount your organization's files externally.

## After Changes

Restart the application to pick up changes:

```bash
docker-compose restart itsm
```

For static files, also run:

```bash
docker-compose exec itsm python manage.py collectstatic --noinput
```
