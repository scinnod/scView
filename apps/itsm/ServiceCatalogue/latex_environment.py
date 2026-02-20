# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
"""
Custom Jinja2 environment for django_tex LaTeX rendering.

Extends the default django_tex environment with additional filters for
simple Markdown formatting and internal cross-references in PDF output.

Registered filters (in addition to all built-in django_tex filters):

* ``latex_escape_markdown`` – bold, italic, and lists (Markdown subset → LaTeX, with escaping)
* ``latex_service_label``   – generate ``\\label{svc:…}`` for a service key
* ``latex_revision_label``  – generate ``\\label{rev:…}`` for a revision key
* ``latex_internal_links``  – parse ``[[ref]]`` → ``\\hyperref[svc:…]{…}``
"""

from django_tex.environment import environment as default_environment

from ServiceCatalogue.latex_filters import (
    do_latex_escape_markdown,
    do_latex_service_label,
    do_latex_revision_label,
    do_latex_internal_links,
)


def environment(**options):
    """
    Build a Jinja2 environment that includes both the default django_tex
    filters and the custom Service Catalogue filters.
    """
    env = default_environment(**options)
    env.filters.update({
        'latex_escape_markdown': do_latex_escape_markdown,
        'latex_service_label': do_latex_service_label,
        'latex_revision_label': do_latex_revision_label,
        'latex_internal_links': do_latex_internal_links,
    })
    return env
