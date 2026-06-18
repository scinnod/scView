# MCP Server (Model Context Protocol)

scView includes a standalone MCP server that exposes the service catalogue
as five tools consumable by AI assistants (Claude, Copilot, Cursor, etc.)
and any MCP-compatible agent framework.

The server is a separate Docker container (`itsm_mcp`).  It accesses the
service catalogue exclusively through the existing public REST API and has
no direct database access.

---

## What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io) is an open
standard for connecting AI assistants to external data sources and tools.
By exposing the service catalogue as MCP tools, users can ask their AI
assistant questions like:

- "What IT services are available for students?"
- "Show me the details of the email service."
- "Which services will be discontinued soon?"

---

## Architecture

```
User / AI client
     │
     │ HTTPS  /sc/mcp
     ▼
nginx (itsm_nginx)          ← rewrites /sc/mcp → /mcp
     │
     │ HTTP   /mcp  (app_itsm internal network)
     ▼
itsm_mcp container          ← FastMCP, Streamable HTTP, port 8080
     │
     │ HTTP  /sc/api/...  (app_itsm internal network)
     ▼
itsm container (Django)     ← public REST API
     │
     ▼
PostgreSQL
```

The MCP container joins the same `app_itsm` internal bridge network as
nginx and the Django application.  It has no database access and no
internet access.

---

## Enabling the MCP Server

The MCP server is controlled by a Docker Compose **profile**.  It does
not start unless explicitly requested.

### Step 1 — Create the environment file

```bash
cp env/mcp.env.example env/mcp.env
# Edit env/mcp.env if you need non-default settings (defaults work out of the box)
```

### Step 2 — Build and start

```bash
docker-compose --profile mcp up -d --build itsm_mcp
```

Or start everything including the MCP server at once:

```bash
docker-compose --profile mcp up -d
```

### Step 3 — Verify

```bash
# Check the container is running
docker-compose ps itsm_mcp

# Check startup logs
docker logs itsm_mcp

# Test MCP endpoint is reachable (expected: 405 Method Not Allowed on GET)
curl -I https://your-domain.com/sc/mcp

# Test LLM discovery file
curl https://your-domain.com/llms.txt
```

---

## Disabling at Runtime

Set `MCP_ENABLED=false` in `env/mcp.env` and restart the container:

```bash
# env/mcp.env
MCP_ENABLED=false
```

```bash
docker-compose --profile mcp restart itsm_mcp
```

The container exits cleanly (exit code 0).  Because the restart policy is
`unless-stopped`, Docker will not automatically restart a cleanly-exited
container.  To re-enable, set `MCP_ENABLED=true` and restart again.

To stop without disabling:

```bash
docker-compose stop itsm_mcp
```

---

## Tools Reference

Call `get_api_metadata` first to discover which tools are currently
enabled and what parameter values are accepted.

### `get_api_metadata`

Returns API self-description including available endpoints, supported
languages, clientele groups, and service categories.  Always available
regardless of `*_REQUIRE_LOGIN` settings.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lang` | string | `en` | Response language (`de` or `en`) |

### `list_online_services`

Returns services that have a direct access URL, grouped by category.
Each entry includes the service name, version, URL, and a flag for
newly-available services.

Availability mirrors the `ONLINE_SERVICES_REQUIRE_LOGIN` setting.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lang` | string | `en` | Response language |
| `clientele` | string | — | Filter by clientele acronym (e.g. `STAFF`) |

### `search_service_catalogue`

Returns the full service catalogue with detailed information per service
including purpose, description, contact, availability dates, and cost
information per clientele.

Availability mirrors the `SERVICE_CATALOGUE_REQUIRE_LOGIN` setting.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lang` | string | `en` | Response language |
| `clientele` | string | — | Filter by clientele acronym |

### `get_service`

Returns full details of a single service by its numeric revision ID.
Obtain IDs from a catalogue or online-services listing.

Availability mirrors `SERVICE_CATALOGUE_REQUIRE_LOGIN`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `service_id` | integer | ✓ | Positive integer revision ID |
| `lang` | string | — | Response language |

### `get_service_by_key`

Returns full details of a single service by its unique key.
The key format is `CATEGORY-ACRONYM` (e.g. `ITD-EMAIL`, `COMPUTE-HPC`).
Keys are case-insensitive.

Availability mirrors `SERVICE_CATALOGUE_REQUIRE_LOGIN`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `service_key` | string | ✓ | Service key, e.g. `ITD-EMAIL` |
| `lang` | string | — | Response language |

---

## Graceful Degradation

The MCP server handles partial and full API unavailability gracefully.

| Situation | Behaviour |
|-----------|-----------|
| API unreachable (network error) | Tool returns a descriptive message; server stays running |
| API timeout | Tool returns a timeout message |
| Endpoint gated by `*_REQUIRE_LOGIN` | Tool returns a login-required explanation; no HTTP call made |
| Service not found (404) | Tool returns a not-found message |
| Server started before Django is ready | Works — metadata probe is retried on the first tool call |

The server uses a 60-second metadata cache.  Calling `get_api_metadata`
always forces a cache refresh.

---

## Connecting AI Clients

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or the equivalent on your OS:

```json
{
  "mcpServers": {
    "scview": {
      "url": "https://your-domain.com/sc/mcp",
      "transport": "streamable-http"
    }
  }
}
```

### VS Code (GitHub Copilot MCP extension)

Add to your VS Code `settings.json`:

```json
{
  "mcp.servers": {
    "scview": {
      "type": "http",
      "url": "https://your-domain.com/sc/mcp"
    }
  }
}
```

### Cursor

In Cursor settings → MCP → Add Server:

- **Name**: scView Service Catalogue
- **URL**: `https://your-domain.com/sc/mcp`
- **Transport**: Streamable HTTP

### Direct HTTP (testing)

```bash
# MCP initialize request
curl -X POST https://your-domain.com/sc/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}'
```

---

## LLM Discovery (`llms.txt`)

The file `nginx/llms.txt` is served at `https://your-domain.com/llms.txt`
following the [llmstxt.org](https://llmstxt.org) convention.

It lists the MCP endpoint and REST API endpoints so that AI crawlers and
agents can discover the machine-readable interfaces without parsing HTML.

**Update the placeholder domain** in `nginx/llms.txt` before deploying:

```
# Replace 'your-domain.com' with your actual domain
```

---

## Security

- The MCP endpoint is public (no authentication) — consistent with the
  public service catalogue it exposes.
- If any `*_REQUIRE_LOGIN` setting is `true`, the corresponding tool
  returns a descriptive message instead of data.  The API gating is
  enforced server-side; the MCP server merely surfaces the result.
- The container runs as a non-root user (`mcpuser`).
- The container is on the `app_itsm` internal network only — no internet
  access, no database access.
- All tool inputs (language codes, clientele acronyms, service keys,
  service IDs) are validated before being used in API requests.
- Nginx applies a rate limit of 30 requests/minute per IP on `/sc/mcp`.
  Adjust `rate` and `burst` in `nginx/nginx.conf` for your load.

---

## Testing

### Local (fast, no Docker needed)

```bash
cd apps/mcp
pip install -r requirements.txt -r tests/requirements-test.txt
python -m pytest tests/ -v
```

### Docker (matches CI exactly)

```bash
docker-compose -f docker-compose.test.yml run --rm mcp_test
```

### GitHub Actions

MCP tests run automatically on every push and pull request to `main`
and `develop` as a separate `mcp-test` job in the `Django Tests`
workflow, in parallel with the Django test job.  No database or
system dependencies are required.

---

## Configuration Reference

See [CONFIGURATION.md](CONFIGURATION.md#mcp-server) for the full list
of environment variables.
