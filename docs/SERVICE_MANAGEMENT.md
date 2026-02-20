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

### "Not Publicly Listed" Badge

In internal views (staff-only list and detail views), services that are **currently available** but **not publicly listed** in the catalogue are clearly marked with a warning badge:

> ⚠ **not publicly listed**

This badge appears when:
- The service has an active availability window (`available_from` ≤ today, `available_until` not past)
- But is **not** publicly listed (no `listed_from`, or `listed_from` > today, or `listed_until` < today)

This helps staff members quickly identify services that users can access but cannot discover through the public catalogue.

## Initial Setup

1. Run `initialize_groups` to create permission groups
2. Assign staff users to appropriate groups via Django admin
3. Create service categories (Administrators/Editors)
4. Create clientele definitions (target user groups)
5. Begin adding services and revisions

See [CONFIGURATION.md](CONFIGURATION.md) for access control settings.
## Text Formatting in Service Fields

The Service Catalogue supports limited text formatting in certain fields to improve readability while keeping the content human-readable as plain text. This section describes the available formatting options and which fields support them.

### Formatting Syntax

#### Bold and Italic

Wrap text in double or single asterisks for bold or italic emphasis:

```
**bold text** → bold text
*italic text* → italic text
```

#### Lists

Start lines with `- ` or `* ` for unordered (bullet) lists, or `1. `, `2. `, etc. for ordered (numbered) lists. Each item must be on its own line:

```
- First item
- Second item
- Third item

1. Step one
2. Step two
3. Step three
```

All items in a paragraph must use the same list type — mixing bullet and numbered markers in a single block is not supported.

#### Internal Links

Reference other services using double square brackets with the service key:

```
[[COMM-EMAIL]]          → links to the Email service (if unique)
[[COMM-EMAIL-2.0]]      → links to a specific revision
[[email]]               → soft link — triggers a fulltext search (not validated)
```

When a key contains the hierarchy separator (`-`), the system validates the reference against currently listed service revisions. References without a separator are treated as soft links (fulltext search triggers) and generate a warning during `check_urls` validation but do not cause errors.

See [CONFIGURATION.md](CONFIGURATION.md#url-and-internal-link-check) for `check_urls` validation details.

#### URLs

Plain-text URLs (e.g. `https://example.com`) are automatically converted into clickable links in fields that support URL auto-linking.

### Unsupported Syntax

The following Markdown elements are deliberately **not** supported to keep content simple and readable as plain text:

- Headings (`#`, `##`, …)
- Images (`![](…)`)
- Code blocks (`` ` `` or `~~~`)
- Tables
- Block quotes (`>`)
- Horizontal rules (`---`)

### Field Formatting Overview

Not all fields support the same formatting options. The table below summarises which formatting features are available in each field. "Strict" fields only render plain text with line breaks — they deliberately do not support bold, italic, lists, URL auto-linking, or internal links.

| Field | Bold / Italic | Lists | URLs | Internal Links | Notes |
|-------|:---:|:---:|:---:|:---:|-------|
| `purpose` | — | — | — | — | Strict — brief, self-consistent, technology-independent |
| `description` | — | — | — | ✓ | Strict — self-contained service description |
| `description_internal` | ✓ | ✓ | ✓ | ✓ | Internal only (staff view) |
| `usage_information` | ✓ | ✓ | ✓ | ✓ | Displayed highlighted |
| `requirements` | ✓ | ✓ | ✓ | ✓ | |
| `details` | ✓ | ✓ | ✓ | ✓ | |
| `options` | ✓ | ✓ | ✓ | ✓ | |
| `service_level` | ✓ | ✓ | ✓ | ✓ | |
| `eol` | ✓ | ✓ | ✓ | ✓ | End-of-life instructions |

> **Validation:** The `check_urls` management command (Phase 3) warns when markup syntax
> is found in strict fields (`purpose`, `description`).  See
> [CONFIGURATION.md](CONFIGURATION.md#url-and-internal-link-check) for details.

### LaTeX / PDF Output

The same formatting syntax works in LaTeX/PDF exports:

- **Bold/italic** are converted to `\textbf{}` / `\textit{}`
- **Lists** become `\begin{itemize}` / `\begin{enumerate}` environments
- **Internal links** become `\hyperref` cross-references using auto-generated `\label`s
- **URLs** are rendered as `\url{}` commands

Each service and service revision in the PDF receives a LaTeX label (`\label{svc:...}` and `\label{rev:...}`) that can be referenced by internal links.