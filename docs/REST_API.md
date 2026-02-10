# REST API & External Integration (SharePoint et al.)

This document describes the public REST API shipped with scView and how to
consume it from SharePoint or other external systems.

---

## 1.  REST API

### 1.1  Design Principles

| Principle | Detail |
|-----------|--------|
| **Read-only** | `GET` only – the API never modifies data. |
| **No authentication** | The API itself does not require login. |
| **Access-gated** | Each endpoint is gated by the **same** `*_REQUIRE_LOGIN` setting that controls the corresponding web page.<br>If a page requires login the API endpoint returns **403**. |
| **Field-safe** | Exposed fields are strictly limited to those visible on the respective public page.<br>`SERVICECATALOGUE_FIELD_*` settings are respected; disabled fields are never included. |
| **Cached** | Responses are cached for 15 minutes (metadata for 1 hour). |

### 1.2  Endpoints

All paths are relative to the application root, typically `/sc/`.

| Endpoint | Description | Gated by | Parameters |
|----------|-------------|----------|------------|
| `api/metadata/` | Self-description, available filters, enabled endpoints | *(always available)* | `lang` |
| `api/online-services/` | Online services directory (services with URLs) | `ONLINE_SERVICES_REQUIRE_LOGIN` | `lang`, `clientele` |
| `api/service-catalogue/` | Full listed service catalogue | `SERVICE_CATALOGUE_REQUIRE_LOGIN` | `lang`, `clientele` |
| `api/service/{id}/` | Single service detail | `SERVICE_CATALOGUE_REQUIRE_LOGIN` | `lang` |
| `api/service-by-key/{key}/` | Single service detail by key (e.g. `ITD-EMAIL`) | `SERVICE_CATALOGUE_REQUIRE_LOGIN` | `lang` |

### 1.3  What Each Endpoint Exposes

**Online services directory** mirrors the online-services jump page and
contains:

- service name, key, category, version
- direct URL to the service
- link to the service detail page
- `is_new` flag (service became available within the last 7 days)
- `discontinuation_warning` (if `available_until` is within 4 weeks)

It does **not** include purpose, description, contact, or any optional fields.

**Service catalogue / service detail** mirrors the catalogue list page and
contains:

- service key, name, purpose, category, version
- description
- URL and contact (if set)
- availability dates and clienteles (including cost info)
- only the optional fields enabled via `SERVICECATALOGUE_FIELD_*`
  (usage\_information, requirements, details, options, service\_level)
- link to the service detail page

It does **not** include `responsible`, `service_providers`,
`description_internal`, `keywords`, or any other staff-only information.

### 1.4  Quick Test

```bash
# metadata (always available)
curl https://your-domain.com/sc/api/metadata/

# online services (only if ONLINE_SERVICES_REQUIRE_LOGIN=False)
curl "https://your-domain.com/sc/api/online-services/?lang=en"

# catalogue (only if SERVICE_CATALOGUE_REQUIRE_LOGIN=False)
curl "https://your-domain.com/sc/api/service-catalogue/?lang=de"
curl "https://your-domain.com/sc/api/service-by-key/ITD-EMAIL/?lang=en"
```

A `403` response means the corresponding page requires login and the API
correctly refuses to expose the data.

### 1.5 Example API Response (online services)

```json
{
  "success": true,
  "timestamp": "2026-02-10T10:30:00",
  "language": "en",
  "total_count": 42,
  "categories": [
    {
      "name": "Category Name",
      "acronym": "CAT",
      "services": [
        {
          "id": 123,
          "service_key": "CAT-SRV",
          "service_name": "Service Name",
          "category": { "name": "Category Name", "acronym": "CAT" },
          "version": "1.0",
          "url": "https://service.example.com",
          "detail_url": "https://your-domain.com/sc/service/123",
          "is_new": false
        }
      ]
    }
  ]
}
```

### 1.6  CORS Configuration

If SharePoint (or any other external domain) calls the API from the browser,
CORS must allow that origin.  `django-cors-headers` is included and
pre-configured — you only need to set one environment variable:

```bash
# env/itsm.env
CORS_ALLOWED_ORIGINS=https://yourcompany.sharepoint.com
```

Multiple origins (comma-separated):

```bash
CORS_ALLOWED_ORIGINS=https://yourcompany.sharepoint.com,https://intranet.example.com
```

CORS headers are scoped to `/sc/api/` paths only; all other pages are
unaffected.  When `CORS_ALLOWED_ORIGINS` is empty (the default), no
cross-origin requests are permitted — there is no security impact if
the API is unused.

---

## 2.  SharePoint Integration Options

### 2.1  Comparison

| Approach | Coding | Setup time | Data freshness | UX | Cost |
|----------|--------|------------|----------------|----|------|
| **SPFx web part** (recommended) | TypeScript/React | 3-5 days first time | Real-time | Excellent | Free (in-house) |
| **Power Automate → SharePoint list** | None | 1-2 hours | Scheduled sync | Good | Free (M365) |
| **Power Apps** | Low-code | 1-2 days | Real-time | Good | May need license |
| **iFrame** | None | Minutes | Real-time | Poor | Free |

**Recommendation:** Start with **Power Automate** for a quick win.  Move to
an **SPFx web part** for the best long-term solution.  Avoid iFrames
(authentication issues, poor UX, not supported in modern SharePoint).

### 2.2  Power Automate (No-Code, Quick Win)

1. **Create a SharePoint list** "IT Services" with columns:
   `ServiceKey` (text), `ServiceName` (text), `Category` (text),
   `URL` (hyperlink), `Version` (text), `IsNew` (yes/no).

2. **Create a scheduled cloud flow** (e.g. daily at 06:00):

   | Step | Action | Configuration |
   |------|--------|---------------|
   | 1 | HTTP GET | `https://your-domain.com/sc/api/online-services/?lang=en` |
   | 2 | Parse JSON | Use schema generated from sample response |
   | 3 | Get Items → Delete Items | Clear old list items |
   | 4 | Apply to each → Create Item | Loop categories → services, map fields |

3. **Add a List web part** to your SharePoint page and select the view.

### 2.3  SPFx Web Part (Best UX)

Below is a minimal working example.  Adapt colours and layout to your needs.

**Prerequisites:** Node.js 18 LTS, `npm install -g yo @microsoft/generator-sharepoint`

```bash
yo @microsoft/sharepoint    # React, "ServiceCatalogue"
cd service-catalogue-webpart
```

**API service** (`src/services/ServiceCatalogueService.ts`):

```typescript
export async function fetchOnlineServices(baseUrl: string, lang = 'en'): Promise<any> {
  const res = await fetch(`${baseUrl}/sc/api/online-services/?lang=${lang}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}
```

**React component** (`src/components/ServiceCatalogue.tsx`, abbreviated):

```tsx
import * as React from 'react';
import { fetchOnlineServices } from '../services/ServiceCatalogueService';

export default function ServiceCatalogue({ apiBaseUrl, lang }: { apiBaseUrl: string; lang: string }) {
  const [data, setData] = React.useState<any>(null);
  const [error, setError] = React.useState('');

  React.useEffect(() => {
    fetchOnlineServices(apiBaseUrl, lang).then(setData).catch(e => setError(e.message));
  }, [apiBaseUrl, lang]);

  if (error) return <div>Error: {error}</div>;
  if (!data) return <div>Loading…</div>;

  return (
    <div>
      {data.categories.map((cat: any) => (
        <div key={cat.acronym}>
          <h3>{cat.name}</h3>
          {cat.services.map((svc: any) => (
            <div key={svc.id}>
              <a href={svc.url} target="_blank" rel="noopener">{svc.service_name}</a>
              {svc.is_new && <span className="badge">New</span>}
              {svc.discontinuation_warning && (
                <span className="warning" title={svc.discontinuation_warning.message}>⚠</span>
              )}
              <a href={svc.detail_url}>ℹ</a>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
```

**Build & deploy:**

```bash
gulp bundle --ship && gulp package-solution --ship
# Upload sharepoint/solution/*.sppkg to App Catalog
# Add web part to page, configure API Base URL in property pane
```

**Web part property pane** – expose `apiBaseUrl` and `lang` as configurable
properties so site owners can point at their instance.

### 2.4  Can You Do This Yourself?

| Approach | Skills needed | Answer |
|----------|--------------|--------|
| Power Automate | Basic SharePoint knowledge | Yes, anyone can do this |
| SPFx web part | Basic TypeScript / following docs | Yes, with the code above |
| External developer | — | €2 000 – 5 000 typical |

Microsoft provides extensive documentation and tutorials:
[SharePoint Framework overview](https://learn.microsoft.com/sharepoint/dev/spfx/sharepoint-framework-overview)

---

## 3.  Security Summary

- The API **never** bypasses access control.  If a page requires login, the
  API returns 403.
- The API only exposes fields visible on the corresponding public page.
  `SERVICECATALOGUE_FIELD_*` settings are respected.
- Internal fields (`description_internal`, `responsible`, `service_providers`,
  `keywords`, `eol`, `search_keys`) are **never** exposed.
- CORS should be configured to allow only your SharePoint domain.
- API responses are cached; no user-specific data is ever included.
