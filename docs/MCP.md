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

The `itsm_mcp` container is part of the standard Compose stack and always
starts alongside the other services.  Whether it actually serves MCP
requests is controlled exclusively by `MCP_ENABLED` in `env/itsm.env`.

When `MCP_ENABLED=false` (the default) the container runs `sleep infinity`
instead of the MCP server.  This keeps the Docker-internal hostname
`itsm_mcp` permanently resolvable so that nginx can start and reload
without a *"host not found in upstream"* error.  nginx returns `502` for
`/sc/mcp` in this state, which is the intended graceful-degradation signal.

### Step 1 — Enable in the environment file

In `env/itsm.env`:

```
MCP_ENABLED=true
```

### Step 2 — Build and start

First time (builds the image):

```bash
docker compose up -d --build itsm_mcp
```

Subsequent starts (image already built):

```bash
docker compose restart itsm_mcp
```

### Step 3 — Verify

```bash
# Check the container is running
docker-compose ps itsm_mcp

# Check startup logs
docker logs itsm_mcp

# Test LLM discovery file (served at the root, not under /sc/)
curl https://your-domain.com/llms.txt

# Test MCP endpoint is reachable (expected: 405 Method Not Allowed on GET)
curl -I https://your-domain.com/sc/mcp
```

---

## Disabling at Runtime

In `env/itsm.env`:

```
MCP_ENABLED=false
```

```bash
docker compose restart itsm_mcp
```

The container keeps running (it switches to `sleep infinity`) so that
nginx can resolve the `itsm_mcp` hostname without errors.  nginx returns
`502` for `/sc/mcp` while the server is disabled.  To re-enable, set
`MCP_ENABLED=true` and restart again.

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

### Direct HTTP (testing / curl)

The MCP [Streamable HTTP transport](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http)
requires a short handshake before tool calls can be made.  The server
assigns a **session ID** in the response headers of the `initialize` request;
this ID must be included as `mcp-session-id` in every subsequent request.

All responses are Server-Sent Events (`text/event-stream`), even for
non-streaming calls.  Each event line looks like:
```
event: message
data: {"jsonrpc":"2.0","id":1,"result":{...}}
```

#### Step 1 — Initialize (obtain session ID)

```bash
curl -k -s -X POST https://your-domain.com/sc/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -D /tmp/mcp_headers.txt \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": {"name": "curl-test", "version": "1.0"}
    }
  }'
```

Extract the session ID from the response headers:

```bash
SESSION_ID=$(grep -i '^mcp-session-id:' /tmp/mcp_headers.txt \
  | awk '{print $2}' | tr -d '\r\n')
echo "Session ID: $SESSION_ID"
```

#### Step 2 — Complete the handshake

```bash
curl -k -s -o /dev/null -w "HTTP status: %{http_code}\n" \
  -X POST https://your-domain.com/sc/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc": "2.0", "method": "notifications/initialized"}'
```

Expected: `HTTP status: 202`

#### Step 3 — List available tools

```bash
curl -k -s -X POST https://your-domain.com/sc/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}'
```

Expected: SSE event containing all five tools.

#### Step 4 — Call a tool

```bash
curl -k -s -X POST https://your-domain.com/sc/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "get_api_metadata",
      "arguments": {"lang": "en"}
    }
  }'
```

Expected: SSE event with `result.content[0].text` containing the catalogue
metadata as a JSON string.

#### Step 5 — Close the session

```bash
curl -k -s -o /dev/null -w "HTTP status: %{http_code}\n" \
  -X DELETE https://your-domain.com/sc/mcp \
  -H "mcp-session-id: $SESSION_ID"
```

Expected: `HTTP status: 200`

> **Note:** `-k` skips TLS certificate verification and is only appropriate
> for local testing with self-signed certificates.  Omit it in production.

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
