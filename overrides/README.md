<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
-->

# Overrides Directory

This directory contains your **organization-specific files** that replace the defaults in `apps/itsm/user_files/`.

## ⚠️ Not Version Controlled

**This directory's contents are gitignored.** Only the structure (`.gitkeep` files and this README) is tracked. Your organization's files stay local and are never committed to the repository.

## How It Works

```
overrides/                          →  Mounted into  →  user_files/
├── static/logos/logo.png                              /app/user_files/static/logos/
├── static/css/custom.css                              /app/user_files/static/css/
└── latex_templates/header.tex                         /app/user_files/latex_templates/
```

The `docker-compose.override.yml` file mounts your files **directly into** the `user_files/` directory, replacing the defaults. This makes it explicit what gets overwritten.

## Directory Structure

Mirror the structure of `apps/itsm/user_files/`:

```
overrides/
├── README.md              # This file (tracked)
├── static/
│   ├── logos/
│   │   ├── .gitkeep       # Tracked (preserves directory structure)
│   │   └── logo.png       # YOUR logo (not tracked)
│   ├── css/
│   │   ├── .gitkeep
│   │   └── custom.css     # YOUR styles (not tracked)
│   └── images/
│       ├── .gitkeep
│       └── banner.jpg     # YOUR images (not tracked)
└── latex_templates/
    ├── .gitkeep
    └── header.tex         # YOUR PDF templates (not tracked)
```

## Quick Start

### 1. Set up the override file

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
```

### 2. Add your logo

```bash
cp /path/to/your-logo.png overrides/static/logos/logo.png
```

### 3. Configure the logo filename

Edit `env/itsm.env`:
```bash
LOGO_FILENAME=logo.png
```

### 4. Start the application

```bash
docker-compose up -d
```

## What Can Be Overridden

| Override Location | Replaces | Purpose |
|-------------------|----------|---------|
| `overrides/static/logos/` | `user_files/static/logos/` | Organization logo |
| `overrides/static/css/` | `user_files/static/css/` | Custom stylesheets |
| `overrides/static/images/` | `user_files/static/images/` | Additional images |
| `overrides/latex_templates/` | `user_files/latex_templates/` | PDF export templates |

## Why This Approach?

1. **Explicit** - Reading `docker-compose.override.yml` shows exactly what's replaced
2. **Simple** - No app-level path layering, just filesystem mounts
3. **Clean** - Organization files stay separate from the repository
4. **Safe** - Gitignored content can't accidentally be committed

## See Also

- [docker-compose.override.yml.example](../docker-compose.override.yml.example) - Mount configuration
- [apps/itsm/user_files/README.md](../apps/itsm/user_files/README.md) - Default files documentation
