<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
-->

# Overrides Directory

This directory contains your organization-specific customizations that override the default files shipped with scView.

## How It Works

When you run the application with Docker, files placed here automatically override the defaults:

1. **Docker Compose automatically merges** `docker-compose.override.yml` with `docker-compose.yml`
2. **Your custom files are mounted** into the container, replacing the built-in defaults
3. **No code changes needed** — just add your files and restart

## Directory Structure

```
overrides/
├── README.md              # This file
├── static/
│   ├── logos/
│   │   └── logo.png       # Your organization's logo
│   ├── css/
│   │   └── custom.css     # Custom stylesheets (optional)
│   └── images/
│       └── banner.jpg     # Additional images (optional)
└── latex_templates/
    └── custom_header.tex  # Custom LaTeX templates for PDF export (optional)
```

## Quick Start

### 1. Add Your Logo

```bash
# Create the logos directory
mkdir -p overrides/static/logos

# Copy your logo (recommended: PNG with transparency, ~400x80px)
cp /path/to/your-logo.png overrides/static/logos/logo.png
```

### 2. Enable the Override

```bash
# Copy the example override file
cp docker-compose.override.yml.example docker-compose.override.yml

# Edit and uncomment the volume mounts you need
# (The file contains detailed instructions)
```

### 3. Configure the Environment

Edit `env/itsm.env`:

```bash
# If your logo has a different filename:
LOGO_FILENAME=your-logo.png
```

### 4. Restart the Application

```bash
docker-compose down
docker-compose up -d
```

## Available Customizations

### Logo

- **Location:** `overrides/static/logos/logo.png`
- **Format:** PNG with transparency recommended
- **Size:** Approximately 400×80px for best results
- **Used in:** Navigation header, PDF exports

### Custom CSS

- **Location:** `overrides/static/css/custom.css`
- **Purpose:** Override default styles, add branding

### LaTeX Templates

- **Location:** `overrides/latex_templates/`
- **Purpose:** Customize PDF export appearance
- **See:** Built-in templates in `apps/itsm/ServiceCatalogue/templates/ServiceCatalogue/latex/` for reference

## Important Notes

- This `overrides/` directory is **gitignored** — your customizations won't be committed
- Default files are baked into the Docker image and work out of the box
- Only create `docker-compose.override.yml` if you need customizations
- Docker Compose automatically loads `docker-compose.override.yml` when present

## Troubleshooting

### Logo not appearing?

1. Check the path: `overrides/static/logos/logo.png`
2. Verify `docker-compose.override.yml` is set up correctly
3. Ensure `LOGO_FILENAME` matches your file name
4. Restart: `docker-compose restart itsm nginx`

### Static files not updating?

```bash
docker-compose exec itsm python manage.py collectstatic --noinput --clear
docker-compose restart nginx
```

## See Also

- [docs/CONFIGURATION.md](docs/CONFIGURATION.md) — Full configuration reference
- [docker-compose.override.yml.example](docker-compose.override.yml.example) — Override template
