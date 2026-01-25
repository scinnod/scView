<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
-->

# ITSM Service Catalogue

**A modern, user-friendly IT Service Catalogue for universities and organizations**

Present your IT services professionally. Help users find what they need. Keep your documentation in one place.

**Author:** David Kleinhans, [Jade University of Applied Sciences](https://www.jade-hs.de/)  
**License:** [Apache-2.0](LICENSE)  
**Contact:** david.kleinhans@jade-hs.de

---

## Why This Project?

Most IT departments struggle with service documentation scattered across wikis, SharePoint sites, and outdated PDFs. Users can't find services, support teams answer the same questions repeatedly, and nobody knows what's actually available.

The ITSM Service Catalogue solves this by providing:

- **A single source of truth** for all IT services
- **User-friendly browsing** with categories and clientele filtering
- **Professional PDF exports** for governance and compliance
- **Multilingual support** out of the box
- **AI-powered search** that understands natural language queries

Built by a university IT department, for university IT departments—but works great for any organization.

---

## ✨ Key Features

### 📚 Comprehensive Service Catalogue
- Hierarchical categories for organized browsing
- Rich service descriptions with availability, contacts, and documentation links
- Service versioning with full revision history
- Distinguish between internal documentation and public-facing information

### 🌐 Online Services Portal
- Quick-access landing page for frequently used online services
- Direct links to service portals, support pages, and documentation
- Perfect for homepage integration or digital signage

### 🤖 AI-Assisted Search
- Natural language queries: *"How do I get more storage?"* or *"I need to host a website"*
- Uses OpenAI-compatible API—works with OpenAI, GWDG chat-ai, KISSKI, and other compatible services
- Two-stage approach: first identifies relevant services, then analyzes details to recommend the best matches
- Understands context and recommends relevant services
- Optional feature—works without AI configuration

### 🌍 Multilingual Support
- German and English out of the box
- Database-level translations (not just UI)
- Automatic language switching based on user preferences
- Extensible to additional languages

### 📄 Professional PDF Export
- LaTeX-based PDF generation
- Customizable templates for your organization
- Individual service datasheets or complete catalogue
- Perfect for audits, governance, and offline documentation

### 🎨 Corporate Identity
- Easy logo and color customization
- Responsive design for desktop and mobile
- Clean, modern Bootstrap 5 interface
- Consistent branding across all pages

### 🔐 Enterprise Authentication
- Keycloak SSO integration via OAuth2-proxy
- Automatic user provisioning from identity provider
- Role-based access (Staff, Editors, Publishers)
- Simple development mode with Django authentication

### 🐳 Docker Deployment
- Production-ready Docker Compose setup
- Three-tier network security (proxy → app → database)
- Works behind any reverse proxy (nginx, Traefik, Caddy)
- Automatic secret management

---

## 🖼️ Screenshots

*Coming soon*

---

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- A reverse proxy for SSL termination (nginx Proxy Manager, Traefik, Caddy, etc.)
- Optional: [Edge-Auth Stack](https://github.com/YOUR_USERNAME/edge-auth-stack) for Keycloak SSO

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/itsm-service-catalogue.git
cd itsm-service-catalogue

# 2. Create proxy network (once per host)
docker network create proxy

# 3. Configure environment
cp env/itsm.env.example env/itsm.env
# Edit env/itsm.env with your settings

# 4. Start services
docker-compose up -d

# 5. Create admin user
docker-compose exec itsm python manage.py createsuperuser

# 6. Optional: Load sample data
docker-compose exec itsm python manage.py populate_test_data
```

### Basic Configuration

Edit `env/itsm.env`:

```bash
# Required
DJANGO_ENV=production
ALLOWED_HOSTS=your-domain.com
CSRF_TRUSTED_ORIGINS=https://your-domain.com

# Branding
ORGANIZATION_NAME=Your University
ORGANIZATION_ACRONYM=YU
PRIMARY_COLOR=003366

# Optional: AI Search
AI_SEARCH_ENABLED=True
OPENAI_API_KEY=sk-your-key-here
```

Configure your reverse proxy to route traffic to `itsm_nginx:80`.

**That's it!** Access your catalogue at `https://your-domain.com/sc/`

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Comprehensive deployment guide |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Environment variables and customization |
| [docs/SERVICE_MANAGEMENT.md](docs/SERVICE_MANAGEMENT.md) | Content model, roles, and publishing workflow |
| [docs/TESTING.md](docs/TESTING.md) | Testing guide and CI/CD setup |
| [docs/LOGIN_FLOW.md](docs/LOGIN_FLOW.md) | Authentication flow documentation |
| [docs/LOGOUT_KEYCLOAK.md](docs/LOGOUT_KEYCLOAK.md) | Keycloak logout configuration |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development guidelines |
| [SECURITY.md](SECURITY.md) | Security policy |

---

## 🏗️ Architecture

```
Internet
    │
    ▼
┌─────────────────────────────────────┐
│  Reverse Proxy (SSL termination)   │  ← NOT included in this stack
│  + OAuth2-proxy + Keycloak (SSO)   │  ← See: github.com/javidkl/jade-django-0-nginx-auth-stack
└─────────────────────────────────────┘
    │
    ▼
═══════════════════════════════════════  ← THIS STACK STARTS HERE
┌─────────────────────────────────────┐
│  nginx (static files, routing)     │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  Django + Gunicorn                 │
│  (Service Catalogue Application)   │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  PostgreSQL (full-text search)     │
└─────────────────────────────────────┘
```

- **Network isolation**: Three separate Docker networks for security
- **Stateless app tier**: Scale Django horizontally if needed
- **Volume persistence**: Database and secrets survive container restarts

---

## 🛠️ Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Django 5.2, Python 3.11 |
| Database | PostgreSQL 15 (with full-text search) |
| Server | Gunicorn + nginx |
| Translations | django-modeltranslation |
| PDF Generation | django-tex (LaTeX) |
| AI Search | OpenAI-compatible API (GWDG chat-ai, KISSKI, OpenAI, etc.) |
| Authentication | Keycloak via OAuth2-proxy |
| Containerization | Docker, Docker Compose |

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

This is a university infrastructure project developed with limited resources. We appreciate:
- Bug reports and feature requests
- Documentation improvements
- Translations
- Code contributions

---

## 📄 License

This project is licensed under the **Apache License 2.0**.

This means:
- ✅ Free to use, modify, and distribute (including commercial use)
- ✅ Patent protection for contributors and users
- ✅ No requirement to share modifications (even for SaaS deployments)
- ✅ Must preserve copyright notices when redistributing source code

**Attribution appreciated:** While not legally required for web deployments, 
we'd love it if you keep "Powered by scView" in the footer with a link to 
this repository. It helps others discover this project and grow the community!

See [LICENSE](LICENSE) and [NOTICE](NOTICE) for the full license text and attributions.

---

## 👤 Author & Support

**David Kleinhans**  
IT Infrastructure, [Jade University of Applied Sciences](https://www.jade-hs.de/)  
📧 david.kleinhans@jade-hs.de

This is a university infrastructure project with limited external support capacity. Issues and pull requests are monitored, but response times may vary.

---

*Built with ❤️ for everyone who values clear service documentation and open source*
