<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
-->

# Open Source Publication Checklist

## Before Publishing to GitHub

- [ ] **Final security check**: No secrets in code (`git grep -i "password\|secret\|api_key\|token"`)
- [ ] **Verify .gitignore**: Check `env/itsm.env` is not staged (`git status`)
- [ ] **Update README.md**: Complete installation and deployment instructions
- [ ] **Update repository URL**: Replace `YOURUSERNAME` in NOTICE and settings.py

## Publishing to GitHub

- [ ] **Create repository**: Set visibility (Public/Private)
- [ ] **Add description**: "Django-based IT Service Management service catalogue"
- [ ] **Add topics**: django, itsm, service-catalogue, keycloak, docker
- [ ] **Verify license**: Apache-2.0 shown in repository
- [ ] **Push code**: `git push origin main`

## After Publication

- [ ] **Test fresh clone**: Clone and deploy on a clean system to verify instructions
- [ ] **Create release**: Tag version (e.g., v1.0.0)

## Notes

- The actual `env/itsm.env` file with real credentials is gitignored
- SSL certificates should be generated on deployment, not committed
- User-uploaded files (`user_files/` at project root) are organization-specific and gitignored
- Sample files in `apps/itsm/user_files/` are tracked as templates
