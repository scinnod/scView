<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
-->

# Service Catalogue Management

This document explains the content model, user roles, and workflow for managing the Service Catalogue.

## Content Model

The Service Catalogue separates **strategic service definitions** from **technical implementation details**:

### Services
- Define *what* is offered—technology-independent descriptions
- Contain the service name, purpose, category, and responsible person
- Intended as stable outputs of a service strategy (involving boards, management decisions)
- Editable only by **Editors** and **Administrators**
- A service without active revisions is not visible in the catalogue

### Service Revisions
- Define *how* a service is delivered—technical solution details
- Contain version, description, requirements, availability, pricing, and lifecycle dates
- More dynamic, reflecting changes in technology or capacity
- Editable by **Authors**, **Authors Plus**, and above
- Only revisions with `listed_from` ≤ today and no `listed_until` are publicly visible
- Multiple revisions enable smooth transitions and lifecycle management

**Key principle:** Services provide stability and governance; revisions provide flexibility and lifecycle tracking.

**Frontend User Experience:** The distinction between Services and Service Revisions is **not transparent** to end users. They see a unified service entry combining the service definition (name, purpose, category) with the active revision's details (description, availability, pricing). This separation exists for content management and governance, not for user-facing presentation.

## User Roles

Initialize the permission groups with:

```bash
docker-compose exec itsm python manage.py initialize_groups
```

### Role Hierarchy

| Role | Description |
|------|-------------|
| **Administrators** | Full access including user management |
| **Editors** | Can edit services and revisions, and publish |
| **Authors Plus** | Can edit revisions (including online ones) and publish |
| **Authors** | Can edit draft revisions only—cannot publish |
| **Viewers** | Read-only access via Django admin |

### Access Levels

| User Type | Access |
|-----------|--------|
| Unauthenticated | Public catalogue (if enabled), Online Services landing page |
| Authenticated (no group) | Same as unauthenticated, plus protected views if enabled |
| Group members | Django admin access based on group permissions |
| Staff users | Full admin interface access |

## Publishing Workflow

1. **Create Service** (Editors only)
   - Define service metadata: name, purpose, category
   - Service remains invisible until a revision is published

2. **Create Revision** (Authors and above)
   - Add technical details, availability, pricing
   - Set `listed_from` date for publication timing
   - Mark as "submitted" when ready for review

3. **Review & Publish** (Authors Plus, Editors, Administrators)
   - Review submitted revisions
   - Set appropriate `listed_from` date to publish
   - Service becomes visible when at least one revision is active

4. **Lifecycle Management**
   - Set `listed_until` to remove from public catalogue
   - Set `available_until` for end-of-life
   - Add `eol` field with migration instructions
   - Create new revision for major changes (version history preserved)

## Visibility Rules

A service is visible in the public catalogue when:
- It has at least one revision where `listed_from` ≤ today
- That revision has no `listed_until` or `listed_until` > today

A revision is considered:
- **Draft**: No `listed_from` date, or `listed_from` > today
- **Online**: `listed_from` ≤ today and (no `listed_until` or `listed_until` > today)
- **Retired**: `listed_until` ≤ today

## Initial Setup

1. Run `initialize_groups` to create permission groups
2. Assign staff users to appropriate groups via Django admin
3. Create service categories (Administrators/Editors)
4. Create clientele definitions (target user groups)
5. Begin adding services and revisions

See [CONFIGURATION.md](CONFIGURATION.md) for access control settings.
