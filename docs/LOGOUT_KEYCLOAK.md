<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
-->

# Keycloak Logout Configuration

## Problem
When users click "Logout" in production, they're logged out of Django but can immediately re-login with a single click because their Keycloak session is still active.

## Solution
Configure OAuth2-proxy to perform **OIDC RP-Initiated Logout** which ends the Keycloak session when users log out.

## OAuth2-proxy Configuration

OAuth2-proxy needs to be configured with OIDC provider settings to support full logout. Here are the required parameters:

### Required Parameters

```bash
# OIDC Provider Configuration
--provider=oidc
--oidc-issuer-url=https://your-keycloak-server/realms/your-realm-name

# Application URLs
--redirect-url=https://your-app-domain/oauth2/callback

# Headers for Django RemoteUserBackend
--pass-user-headers=true
--set-xauthrequest=true

# Skip OAuth2-proxy login page (direct to Keycloak)
--skip-provider-button=true

# Allowed redirect domains (important for logout)
--whitelist-domain=.your-domain.com
```

### How OIDC Logout Works

When a user visits `/oauth2/sign_out?rd=/`:

1. **OAuth2-proxy** clears its own session cookie
2. **OAuth2-proxy** redirects to Keycloak's `end_session_endpoint` with:
   - `id_token_hint` - the user's ID token
   - `post_logout_redirect_uri` - where to go after logout (the `rd` parameter)
3. **Keycloak** ends the user's SSO session
4. **Keycloak** redirects back to the `post_logout_redirect_uri`

### Example Full Configuration

```bash
oauth2-proxy \
  --provider=oidc \
  --oidc-issuer-url=https://keycloak.example.com/realms/myrealm \
  --client-id=my-itsm-client \
  --client-secret=your-client-secret \
  --cookie-secret=random-32-byte-string \
  --redirect-url=https://itsm.example.com/oauth2/callback \
  --email-domain=* \
  --upstream=http://itsm-nginx:8000 \
  --pass-user-headers=true \
  --set-xauthrequest=true \
  --skip-provider-button=true \
  --whitelist-domain=.example.com \
  --cookie-secure=true \
  --cookie-httponly=true
```

## Django Configuration

The Django app is already configured correctly in `views.py`:

```python
if settings.IS_PRODUCTION:
    # Redirects to /oauth2/sign_out?rd=/
    # OAuth2-proxy will handle the full OIDC logout
    return redirect('/oauth2/sign_out?rd=/')
```

## Keycloak Client Configuration

In your Keycloak client settings:

1. **Valid Redirect URIs**: Add `https://your-app-domain/oauth2/callback`
2. **Valid Post Logout Redirect URIs**: Add `https://your-app-domain/*`
3. **Client Authentication**: ON (for confidential clients)
4. **Standard Flow**: Enabled

## Testing

After configuration, test the logout flow:

1. Log in to the application
2. Click "Logout"
3. Try to access a protected page
4. You should be redirected to Keycloak login (not automatically logged in)

If you're still automatically logged in, check:
- OAuth2-proxy logs for OIDC logout redirect
- Keycloak session is actually being terminated
- Browser cookies are being cleared
- The `--whitelist-domain` includes your application domain

## Troubleshooting

### Still logged in after logout
- Check if `--oidc-issuer-url` is correctly set
- Verify `--whitelist-domain` matches your domain
- Check OAuth2-proxy logs for OIDC logout attempts

### Redirect loop after logout
- Ensure `--whitelist-domain` is set correctly
- Check Keycloak's "Valid Post Logout Redirect URIs"

### Can't log back in after logout
- Check if `--redirect-url` matches Keycloak's "Valid Redirect URIs"
- Verify cookie settings (`--cookie-secure`, `--cookie-domain`)

## References

- [OAuth2-proxy OIDC Configuration](https://oauth2-proxy.github.io/oauth2-proxy/configuration/providers/oidc)
- [OIDC RP-Initiated Logout](https://openid.net/specs/openid-connect-rpinitiated-1_0.html)
- [Keycloak OIDC Logout](https://www.keycloak.org/docs/latest/securing_apps/#logout)
