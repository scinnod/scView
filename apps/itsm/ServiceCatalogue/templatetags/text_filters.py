import datetime
import re
from re import sub

from django import template
from django.template.defaultfilters import stringfilter
from django.urls import reverse
from django.utils.html import conditional_escape, escape
from django.utils.safestring import mark_safe
# Note: Translation in template filters does not currently work despite proper setup.
# gettext is imported for future Django versions that might fix this issue.
# The translations remain in django.po for when this starts working.
from django.utils.translation import gettext as _

from ServiceCatalogue.models import ServiceRevision, keysep

register = template.Library()


# ---------------------------------------------------------------------------
# Simple Markdown formatting helpers
# ---------------------------------------------------------------------------

def _parse_simple_markdown_text(html):
    """
    Parse a limited subset of Markdown-like syntax in already-HTML text
    (i.e. after Django's ``linebreaks`` filter has run).

    Supported syntax (and **only** this syntax):

    * **Bold**: ``**text**`` → ``<strong>text</strong>``
    * *Italic*: ``*text*`` → ``<em>text</em>``
    * Unordered lists: lines starting with ``- `` or ``* ``
    * Ordered lists: lines starting with ``1. ``, ``2. ``, etc.

    All other Markdown elements (headings, images, code blocks, tables, etc.)
    are intentionally **not** supported.  The input fields are meant to stay
    human-readable plain text with only light formatting.

    **Design note:** This function operates on HTML that has already been
    processed by Django's ``linebreaks`` filter, so list items appear as
    ``<p>- item1<br>- item2</p>`` patterns.  The function detects these
    patterns and converts them into proper ``<ul>``/``<ol>`` elements.
    """
    # Step 1: Bold – **text** → <strong>text</strong>
    # Must be processed before italic to avoid conflicts.
    # Avoid matching inside HTML tags or across paragraphs.
    html = re.sub(
        r'\*\*([^*<>]+?)\*\*',
        r'<strong>\1</strong>',
        html,
    )

    # Step 2: Italic – *text* → <em>text</em>
    # Single asterisk, but not part of a list marker (handled by list logic).
    # Also must not match already-converted <strong> markers.
    html = re.sub(
        r'(?<!\*)\*([^*<>]+?)\*(?!\*)',
        r'<em>\1</em>',
        html,
    )

    # Step 3: Lists
    # After ``linebreaks``, content looks like:
    #   <p>- item 1<br>- item 2<br>- item 3</p>
    # or mixed with normal paragraphs.  We process each <p>…</p> block and
    # check whether it consists entirely of list items.
    html = _convert_lists(html)

    return html


def _convert_lists(html):
    """
    Convert list-like ``<p>`` blocks into proper ``<ul>`` / ``<ol>`` elements.

    A paragraph is treated as a list if **every** line inside it starts with
    a recognised list marker:

    * ``- `` or ``* `` for unordered lists
    * ``1. ``, ``2. ``, etc. for ordered lists

    Mixed list types within a single paragraph are not supported and will be
    left untouched.
    """
    # Pattern for unordered list item markers (- or * at start of line)
    # We use a regex that matches the bullet followed by a space.
    UL_MARKER = re.compile(r'^(?:[-*])\s+', re.MULTILINE)
    # Pattern for ordered list item markers (digits followed by . and space)
    OL_MARKER = re.compile(r'^\d+\.\s+', re.MULTILINE)

    def _process_paragraph(match):
        inner = match.group(1)
        # Split on <br>, <br/>, <br /> variants
        lines = re.split(r'<br\s*/?>', inner)
        lines = [line.strip() for line in lines if line.strip()]

        if not lines:
            return match.group(0)

        # Check if all lines are unordered list items
        all_ul = all(re.match(r'^[-*]\s+', line) for line in lines)
        # Check if all lines are ordered list items
        all_ol = all(re.match(r'^\d+\.\s+', line) for line in lines)

        if all_ul:
            items = [re.sub(r'^[-*]\s+', '', line) for line in lines]
            return '<ul>\n' + ''.join(f'<li>{item}</li>\n' for item in items) + '</ul>'
        elif all_ol:
            items = [re.sub(r'^\d+\.\s+', '', line) for line in lines]
            return '<ol>\n' + ''.join(f'<li>{item}</li>\n' for item in items) + '</ol>'
        else:
            return match.group(0)

    # Process each <p>…</p> block
    html = re.sub(r'<p>(.*?)</p>', _process_paragraph, html, flags=re.DOTALL)
    return html

# ---------------------------------------------------------------------------
# Internal-link classification constants
# ---------------------------------------------------------------------------

_ILINK_SOFT   = 'soft'    # no key separator – unvalidated fulltext search (warning)
_ILINK_UNIQUE = 'unique'  # exactly one currently-listed revision matched
_ILINK_MULTI  = 'multi'   # multiple currently-listed revisions matched
_ILINK_BROKEN = 'broken'  # key separator present but no matching revision (error)


def _classify_internal_link(link_text):
    """
    Classify an internal ``[[...]]`` link reference without generating HTML.

    Returns ``(kind, match_count)`` where *kind* is one of the ``_ILINK_*``
    constants defined in this module:

    * ``_ILINK_SOFT``   – no key separator; link is not validated (warning only)
    * ``_ILINK_UNIQUE`` – exactly one currently-listed revision found
    * ``_ILINK_MULTI``  – more than one currently-listed revision found
    * ``_ILINK_BROKEN`` – key separator present but no matching revision (error)

    This function is the shared classification kernel used by both the HTML
    template filters (:func:`_resolve_internal_link`) and the ``check_urls``
    management command.  It performs a single DB query (or zero for the soft
    case).
    """
    if keysep not in link_text:
        return _ILINK_SOFT, 0

    try:
        today = datetime.date.today()
        match_count = (
            ServiceRevision.objects
            .filter(search_keys__icontains=link_text, listed_from__lte=today)
            .exclude(listed_until__lt=today)
            .count()
        )
        if match_count == 1:
            return _ILINK_UNIQUE, 1
        elif match_count > 1:
            return _ILINK_MULTI, match_count
        else:
            return _ILINK_BROKEN, 0
    except Exception:
        return _ILINK_BROKEN, 0


def _resolve_internal_link(link_text, for_detail_view=False):
    """
    Resolve an internal link to determine the best target, icon, and display text.
    
    Intended for linking to services using CATEGORY-SERVICE(-REVISION) format:
    - CATEGORY-SERVICE: Links to unique service if only one revision is listed
    - CATEGORY-SERVICE-REVISION: Links to specific revision
    - If multiple revisions exist, shows search results for all available revisions
    - Without key separator: Initiates normal fulltext search (not validated)
    
    Args:
        link_text: The reference text from [[...]]
        for_detail_view: If True, redirect to list view instead of same page
    
    Returns a tuple of (url, icon, title, display_text):
    - url: The target URL (either direct service link or search)
    - icon: HTML icon markup for decoration
    - title: Tooltip text explaining the link type
    - display_text: The text to display in the link
    """
    
    # Check if link_text contains the key separator
    if keysep not in link_text:
        # Soft warning - text not checked, redirect to general search
        base_url = reverse('services_listed') if for_detail_view else ''
        url = f'{base_url}?q={link_text}'
        icon = '<i class="bi bi-info-circle text-muted small ms-1"></i>'
        # Force evaluation of lazy translation to string for proper formatting
        title = escape(str(_('Reference does not contain key separator "{}" - not validated. Click to search.')).format(keysep))
        return url, icon, title, link_text
    
    # Search for matching service revisions
    try:
        today = datetime.date.today()
        matches = ServiceRevision.objects.filter(
            search_keys__icontains=link_text,
            listed_from__lte=today
        ).exclude(
            listed_until__lt=today
        ).select_related('service')
        
        match_count = matches.count()
        
        if match_count == 1:
            # Unique match - direct link to service detail
            sr = matches.first()
            url = reverse('service_detail', args=[sr.id])
            icon = '<i class="bi bi-link-45deg small ms-1"></i>'
            title = escape(str(_('Direct link to service: {}')).format(sr.service.name))
            # Use "Service Name (SERVICE-KEY)" as display text
            display_text = f'{sr.service.name} ({sr.key})'
            return url, icon, title, display_text
            
        elif match_count > 1:
            # Multiple matches - search link with search icon
            base_url = reverse('services_listed') if for_detail_view else ''
            url = f'{base_url}?q=key::{link_text}'
            icon = '<i class="bi bi-search small ms-1"></i>'
            title = escape(str(_('Search for "{}" ({} matches)')).format(link_text, match_count))
            return url, icon, title, link_text
            
        else:
            # No matches - broken link with warning icon
            base_url = reverse('services_listed') if for_detail_view else ''
            url = f'{base_url}?q=key::{link_text}'
            icon = '<i class="bi bi-exclamation-triangle text-warning small ms-1"></i>'
            title = escape(str(_('No service found for "{}"')).format(link_text))
            return url, icon, title, link_text
            
    except Exception:
        # Fallback to simple search on any error
        base_url = reverse('services_listed') if for_detail_view else ''
        url = f'{base_url}?q=key::{link_text}'
        icon = '<i class="bi bi-search small ms-1"></i>'
        title = escape(str(_('Search for "{}"')).format(link_text))
        return url, icon, title, link_text


@register.filter(needs_autoescape=True)
@stringfilter
def parse_internal_links(text, autoescape=True):
    """
    Parse [[reference]] syntax into smart internal links for list views.
    
    Redirects to the same page with query parameters.
    
    - CATEGORY-SERVICE with unique revision: Direct link showing "Service Name (CATEGORY-SERVICE)"
    - CATEGORY-SERVICE-REVISION: Direct link to specific revision
    - Multiple revisions: Search link showing all available revisions
    - No matches: Search link with warning icon
    - No key separator: Soft warning, fulltext search (not validated)
    
    Examples:
        [[COLLAB-EMAIL]] → Direct link showing "Email Service (COLLAB-EMAIL)"
        [[COMPUTE-HPC-2.1]] → Direct link to specific revision
        [[COLLAB-FILES]] → Search link if multiple revisions exist
        [[INVALID-SERVICE]] → Search link with warning if no matches
        [[email]] → Soft info icon, fulltext search (no validation)
    """
    if autoescape:
        esc = conditional_escape
    else:
        esc = lambda x: x
    
    def replace_link(match):
        link_text = match[0][2:-2]  # Extract text between [[ and ]]
        url, icon, title, display_text = _resolve_internal_link(link_text, for_detail_view=False)
        # Escape the display text for HTML safety
        escaped_text = escape(display_text)
        return f'<a href="{url}" title="{title}">{escaped_text}{icon}</a>'
    
    result = sub(r"\[\[[^()]*?\]\]", replace_link, esc(text))
    return mark_safe(result)


@register.filter(needs_autoescape=True)
@stringfilter
def parse_internal_links_detail(text, autoescape=True):
    """
    Parse [[reference]] syntax into smart internal links for detail views.
    
    Redirects to the list view with query parameters instead of the same page.
    
    - CATEGORY-SERVICE with unique revision: Direct link showing "Service Name (CATEGORY-SERVICE)"
    - CATEGORY-SERVICE-REVISION: Direct link to specific revision
    - Multiple revisions: Search link to list view showing all available revisions
    - No matches: Search link to list view with warning icon
    - No key separator: Soft warning, fulltext search on list view (not validated)
    
    Examples:
        [[COLLAB-EMAIL]] → Direct link showing "Email Service (COLLAB-EMAIL)"
        [[COMPUTE-HPC-2.1]] → Direct link to specific revision
        [[COLLAB-FILES]] → Link to list view search if multiple revisions exist
        [[INVALID-SERVICE]] → Link to list view search with warning if no matches
        [[email]] → Soft info icon, fulltext search on list view (no validation)
    """
    if autoescape:
        esc = conditional_escape
    else:
        esc = lambda x: x
    
    def replace_link(match):
        link_text = match[0][2:-2]  # Extract text between [[ and ]]
        url, icon, title, display_text = _resolve_internal_link(link_text, for_detail_view=True)
        # Escape the display text for HTML safety
        escaped_text = escape(display_text)
        return f'<a href="{url}" title="{title}">{escaped_text}{icon}</a>'
    
    result = sub(r"\[\[[^()]*?\]\]", replace_link, esc(text))
    return mark_safe(result)


@register.filter(is_safe=True)
@stringfilter
def parse_simple_markdown(text):
    """
    Apply limited Markdown-like formatting to HTML text.

    Intended to run **after** ``linebreaks`` (and optionally ``urlize``) but
    **before** the internal-link filters.  The filter chain for fields that
    support rich formatting is::

        {{ field|linebreaks|urlize|parse_simple_markdown|parse_internal_links_detail }}

    Only the following Markdown elements are supported:

    * ``**bold**`` → **bold**
    * ``*italic*`` → *italic*
    * Lines starting with ``- `` or ``* `` → unordered list
    * Lines starting with ``1. ``, ``2. `` … → ordered list

    All other Markdown syntax (headings, images, code blocks, tables, block
    quotes, horizontal rules, etc.) is intentionally **not** supported.
    The text fields are meant to remain human-readable plain text with only
    light formatting.

    Examples::

        >>> from django.template.defaultfilters import linebreaks
        >>> parse_simple_markdown(linebreaks("**bold** and *italic*"))
        '<p><strong>bold</strong> and <em>italic</em></p>'

        >>> parse_simple_markdown(linebreaks("- first\\n- second\\n- third"))
        '<ul>\\n<li>first</li>\\n<li>second</li>\\n<li>third</li>\\n</ul>'

        >>> parse_simple_markdown(linebreaks("1. one\\n2. two"))
        '<ol>\\n<li>one</li>\\n<li>two</li>\\n</ol>'
    """
    return mark_safe(_parse_simple_markdown_text(text))
