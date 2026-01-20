<!--
SPDX-License-Identifier: AGPL-3.0-or-later
SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
-->

# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |
| Older   | :x:                |

We recommend always using the latest version for security updates.

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly:

**Contact:** [david.kleinhans@jade-hs.de](mailto:david.kleinhans@jade-hs.de)

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact assessment
- Any suggested fixes (optional)

### Response Timeline

- **Acknowledgment**: Within 5 business days
- **Initial Assessment**: Within 10 business days
- **Resolution**: Depends on severity and complexity

### Important Notes

- **Do not** disclose vulnerabilities publicly until they have been addressed
- **Do not** exploit vulnerabilities beyond what is necessary to demonstrate the issue
- This project is maintained by a university team with limited resources; response times may vary

## Security Best Practices

When deploying this application:

1. **Never enable DEBUG in production** - exposes sensitive information
2. **Use environment variables** for all secrets (SECRET_KEY, database passwords, API keys)
3. **Deploy behind the Edge-Auth Stack** for proper authentication
4. **Keep dependencies updated** - run `pip list --outdated` regularly
5. **Use HTTPS** - SSL/TLS should be terminated at the edge proxy
6. **Configure ALLOWED_HOSTS** - list only your actual domains
7. **Set CSRF_TRUSTED_ORIGINS** - match your production domains

## Authentication Security

This application is designed to work with the [Edge-Auth Stack](https://github.com/YOUR_USERNAME/edge-auth-stack) which provides:

- Keycloak SSO authentication
- OAuth2-proxy session management
- nginx-based request filtering

See the Edge-Auth Stack documentation for security configuration details.
