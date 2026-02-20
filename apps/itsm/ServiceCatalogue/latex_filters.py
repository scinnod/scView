# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
"""
Custom Jinja2 filters for LaTeX templates (used via django_tex).

These filters complement the built-in ``latex_escape`` filter provided by
django_tex and add support for:

* **Simple Markdown formatting** (``latex_escape_markdown``): bold, italic,
  and numbered/unnumbered lists in LaTeX syntax.
* **Internal link labels** (``latex_service_label``, ``latex_revision_label``):
  generate ``\\label{}`` / ``\\hyperref[]{}`` commands for cross-referencing
  services within the PDF catalogue.
* **Internal link resolution** (``latex_internal_links``): parse ``[[ref]]``
  syntax and convert matching references into ``\\hyperref`` cross-references.
"""

import re

from django_tex.filters import do_latex_escape


# ---------------------------------------------------------------------------
# Simple Markdown → LaTeX
# ---------------------------------------------------------------------------

def do_latex_escape_markdown(value: str) -> str:
    """
    Convert a limited Markdown subset to LaTeX, operating on **raw** (not yet
    latex-escaped) text.

    Supported syntax:

    * ``**bold**`` → ``\\textbf{bold}``
    * ``*italic*`` → ``\\textit{italic}``
    * Lines starting with ``- `` or ``* `` → ``\\begin{itemize}`` list
    * Lines starting with ``1. ``, ``2. `` … → ``\\begin{enumerate}`` list

    Everything else is left untouched (including newlines, which are handled
    by the existing ``linebreaks`` or ``latex_escape`` filters in the
    template).

    This filter should be applied **instead of** plain ``latex_escape`` on
    fields where rich formatting is desired.  It performs its own LaTeX
    escaping on the non-markup parts of the text so that special characters
    remain safe.
    """
    if not value:
        return ''

    lines = value.split('\n')
    result_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Detect unordered list block
        if re.match(r'^[-*]\s+', line):
            result_lines.append('\\begin{itemize}')
            while i < len(lines) and re.match(r'^[-*]\s+', lines[i]):
                item_text = re.sub(r'^[-*]\s+', '', lines[i])
                result_lines.append(f'  \\item {_escape_markdown_line(item_text)}')
                i += 1
            result_lines.append('\\end{itemize}')
            continue

        # Detect ordered list block
        if re.match(r'^\d+\.\s+', line):
            result_lines.append('\\begin{enumerate}')
            while i < len(lines) and re.match(r'^\d+\.\s+', lines[i]):
                item_text = re.sub(r'^\d+\.\s+', '', lines[i])
                result_lines.append(f'  \\item {_escape_markdown_line(item_text)}')
                i += 1
            result_lines.append('\\end{enumerate}')
            continue

        # Normal line – escape and apply inline formatting
        result_lines.append(_escape_markdown_line(line))
        i += 1

    return '\n'.join(result_lines)


def _escape_markdown_line(text: str) -> str:
    """
    Apply LaTeX escaping to a single line while preserving bold/italic
    Markdown markers, then convert those markers to LaTeX commands.
    """
    # Step 1: Find bold/italic spans and protect them
    # We split the text into segments: markdown markers and plain text.
    # Process bold first (**…**), then italic (*…*).

    parts = []
    last_end = 0

    # Find **bold** spans
    for m in re.finditer(r'\*\*([^*]+?)\*\*', text):
        # Escape text before this match
        parts.append(do_latex_escape(text[last_end:m.start()]))
        # Add bold LaTeX command with escaped content
        parts.append(f'\\textbf{{{do_latex_escape(m.group(1))}}}')
        last_end = m.end()

    # Remaining text after last bold match
    remaining = text[last_end:]

    if parts:
        # Process remaining text for italic
        parts.append(_apply_italic(remaining))
    else:
        # No bold found – process entire text for italic
        parts.append(_apply_italic(text))

    return ''.join(parts)


def _apply_italic(text: str) -> str:
    """Convert *italic* spans in text, LaTeX-escaping non-italic parts."""
    parts = []
    last_end = 0

    for m in re.finditer(r'(?<!\*)\*([^*]+?)\*(?!\*)', text):
        parts.append(do_latex_escape(text[last_end:m.start()]))
        parts.append(f'\\textit{{{do_latex_escape(m.group(1))}}}')
        last_end = m.end()

    parts.append(do_latex_escape(text[last_end:]))
    return ''.join(parts)


# ---------------------------------------------------------------------------
# Internal link labels and cross-references for LaTeX
# ---------------------------------------------------------------------------

def _sanitize_label(text: str) -> str:
    """
    Sanitize a string for use as a LaTeX label.

    Only alphanumeric characters, hyphens, dots, and colons are kept;
    everything else is replaced with a hyphen.  The result is lowercased.
    """
    return re.sub(r'[^a-zA-Z0-9.:-]', '-', text).lower().strip('-')


def do_latex_service_label(service_key: str) -> str:
    """
    Generate a LaTeX ``\\label{}`` command for a service.

    Usage in templates::

        \\label{ {{- sr.service.key | latex_service_label -}} }

    Produces e.g. ``\\label{svc:comm-email}``
    """
    return f'\\label{{svc:{_sanitize_label(service_key)}}}'


def do_latex_revision_label(revision_key: str) -> str:
    """
    Generate a LaTeX ``\\label{}`` command for a service revision.

    Usage in templates::

        \\label{ {{- sr.key | latex_revision_label -}} }

    Produces e.g. ``\\label{rev:comm-email-2.0}``
    """
    return f'\\label{{rev:{_sanitize_label(revision_key)}}}'


def do_latex_internal_links(value: str) -> str:
    r"""
    Parse ``[[reference]]`` syntax in LaTeX text and convert to
    ``\hyperref[label]{display text}`` cross-references.

    References containing the key separator ``-`` are treated as service
    keys and linked via ``\hyperref[svc:…]{…}``.  References without a
    key separator are rendered as bold text (since there is no search
    functionality in a PDF).

    This filter should be applied **after** ``latex_escape`` or
    ``latex_escape_markdown``.

    Examples::

        [[COMM-EMAIL]]     → \hyperref[svc:comm-email]{COMM-EMAIL}
        [[email service]]  → \textbf{email service}
    """
    if not value:
        return ''

    def _replace(match):
        ref = match.group(1)
        if '-' in ref:
            label = _sanitize_label(ref)
            escaped_ref = do_latex_escape(ref)
            return f'\\hyperref[svc:{label}]{{{escaped_ref}}}'
        else:
            return f'\\textbf{{{do_latex_escape(ref)}}}'

    return re.sub(r'\[\[([^\[\]]+?)\]\]', _replace, value)
