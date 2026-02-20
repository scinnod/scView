"""
Management command to check URLs and internal links in service catalogue text fields.

Phase 1 – External URL availability
    Scans every ServiceRevision field auto-linked in templates via Django's ``|urlize``
    filter (description_internal, usage_information, details and their de/en
    translations) as well as the dedicated URLField (url).  Duplicate URLs are collapsed
    before checking so each address is only requested once.

Phase 2 – Internal ``[[...]]`` link validation
    Scans all text fields rendered with the ``|parse_internal_links`` template filter
    for ``[[...]]`` references and validates them using the same logic as the template
    filter (via :func:`_classify_internal_link` in ``templatetags/text_filters.py``):

    * ``[[email]]`` – no key separator → *soft link*, not validated → **warning**
    * ``[[INVALID-SERVICE]]`` – key separator present, no matching revision → **error**
    * ``[[COLLAB-EMAIL]]`` – matches one or more revisions → OK

Phase 3 – Markup in strict fields
    Scans the ``description`` and ``purpose`` fields for markup syntax that is not
    supported in those fields (per the field formatting overview in the documentation).

    * ``purpose``: Strict – no bold/italic, no lists, no URLs, no internal links
    * ``description``: Strict – no bold/italic, no lists, no URLs, but internal links
      ``[[...]]`` are allowed

    Any markup found in these fields produces a **warning** (not an error) because the
    formatting will not render and may confuse users reading the plain text.

Exit codes:
  0 – all URLs reachable and no broken internal links detected
  1 – at least one broken URL or broken internal link detected

Usage::

    python manage.py check_urls
    python manage.py check_urls --include-403
    python manage.py check_urls --timeout 20 --workers 10
    python manage.py check_urls --all-services
"""

import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from django.core.management.base import BaseCommand

# ---------------------------------------------------------------------------
# URL extraction
# ---------------------------------------------------------------------------

# Pattern modelled after Django's urlize: match http/https URLs in plain text.
# Trailing punctuation that is commonly not part of a URL is excluded.
_URL_RE = re.compile(
    r'https?://[^\s<>"\'()[\]{}|\\^`]*[^\s<>"\'()[\]{}|\\^`.,;:!?]',
    re.IGNORECASE,
)

# Pattern for [[internal link]] references (matches the same syntax as the template filter).
_INTERNAL_LINK_RE = re.compile(r'\[\[([^()]*?)\]\]')

# Patterns for detecting markup syntax in strict fields
_BOLD_RE = re.compile(r'\*\*[^*]+?\*\*')
_ITALIC_RE = re.compile(r'(?<!\*)\*[^*]+?\*(?!\*)')
_UL_RE = re.compile(r'^[-*]\s+', re.MULTILINE)
_OL_RE = re.compile(r'^\d+\.\s+', re.MULTILINE)


def _detect_markup(text: str, allow_internal_links: bool = False) -> list[str]:
    """Detect markup syntax in text that should be plain/strict.

    Returns a list of human-readable descriptions of the markup found.
    When *allow_internal_links* is True, ``[[...]]`` references are
    **not** reported (used for the ``description`` field which supports
    internal links but not other markup).
    """
    if not text:
        return []
    findings: list[str] = []
    if _BOLD_RE.search(text):
        findings.append('bold (**...**)')
    if _ITALIC_RE.search(text):
        findings.append('italic (*...*)')
    if _UL_RE.search(text):
        findings.append('unordered list (- ...)')
    if _OL_RE.search(text):
        findings.append('ordered list (1. ...)')
    if _URL_RE.search(text):
        findings.append('URL (https://...)')
    if not allow_internal_links and _INTERNAL_LINK_RE.search(text):
        findings.append('internal link ([[...]])')
    return findings


def _extract_urls(text: str) -> list[str]:
    """Return all http/https URLs found in *text*."""
    if not text:
        return []
    return _URL_RE.findall(text)


def _extract_internal_links(text: str) -> list[str]:
    """Return all [[...]] internal link references found in *text*."""
    if not text:
        return []
    return _INTERNAL_LINK_RE.findall(text)


# ---------------------------------------------------------------------------
# Field configuration
# Fields that templates render with |urlize → plain-text URLs become links.
# Format: (model_field_name, display_label, is_translated)
# ---------------------------------------------------------------------------

_TEXT_URL_FIELDS = [
    ('description_internal', 'description_internal', False),
    ('usage_information',    'usage_information',    True),
    ('requirements',         'requirements',         True),
    ('details',              'details',              True),
    ('options',              'options',              True),
    ('service_level',        'service_level',        True),
    ('eol',                  'eol',                  False),
]

# Fields scanned for [[internal link]] references.
# These correspond to all ServiceRevision fields rendered with |parse_internal_links
# in the templates (service.purpose is on Service, not ServiceRevision, and is omitted).
_INTERNAL_LINK_FIELDS = [
    ('description_internal', 'description_internal', False),
    ('description',          'description',          True),
    ('usage_information',    'usage_information',    True),
    ('requirements',         'requirements',         True),
    ('details',              'details',              True),
    ('options',              'options',              True),
    ('service_level',        'service_level',        True),
    ('eol',                  'eol',                  False),
]
_LANGUAGES = ['de', 'en']


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        'Phase 1: Check all URLs in service catalogue text fields (those rendered with '
        '|urlize in templates) and the ServiceRevision.url URLField for availability.  '
        'Phase 2: Validate all [[...]] internal link references in text fields rendered '
        'with |parse_internal_links – broken references (key separator present, no match) '
        'cause exit code 1; soft links (no key separator) produce a warning only.  '
        'Phase 3: Warn about markup syntax (bold, italic, lists, URLs, internal links) '
        'found in strict fields (description, purpose) where it is not supported.  '
        'Use --include-403 to also flag HTTP 403 responses as broken.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--include-403',
            action='store_true',
            default=False,
            help=(
                'Treat HTTP 403 (Forbidden) responses as broken.  '
                'By default 403 responses are noted separately but not counted as '
                'broken, because they may result from authentication requirements '
                'rather than missing content.'
            ),
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=10,
            metavar='SECONDS',
            help='Per-request timeout in seconds (default: 10).',
        )
        parser.add_argument(
            '--workers',
            type=int,
            default=5,
            metavar='N',
            help='Number of parallel HTTP worker threads (default: 5).',
        )
        parser.add_argument(
            '--all-services',
            action='store_true',
            default=False,
            help=(
                'Also check URLs in service revisions that have no listing/availability '
                'dates at all, or where both end-dates are fully in the past (retired / '
                'unpublished drafts).  '
                'By default these are excluded; the default scan covers all revisions '
                'that are currently listed, currently available, or scheduled for future '
                'listing or availability.'
            ),
        )

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        include_403: bool = options['include_403']
        timeout: int     = options['timeout']
        workers: int     = options['workers']
        all_services: bool = options['all_services']

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Service Catalogue URL Availability Check ===\n'))
        self.stdout.write(
            f'Settings: timeout={timeout}s  workers={workers}  '
            f'include_403={include_403}  all_services={all_services}'
        )

        # ------------------------------------------------------------------
        # 1. Collect URLs
        # ------------------------------------------------------------------
        from django.db.models import Q
        from ServiceCatalogue.models import ServiceRevision
        import datetime

        today = datetime.date.today()
        qs = ServiceRevision.objects.select_related('service', 'service__category')

        if not all_services:
            # Include a revision if it has an active or future *listing* or an
            # active or future *availability*.  This covers:
            #   • currently listed  (listed_from <= today, listed_until not past)
            #   • currently available to staff  (available_from <= today, available_until not past)
            #   • scheduled for future listing  (listed_from > today)
            #   • scheduled for future availability  (available_from > today)
            #   • listed without availability date set yet
            # Excluded by default:
            #   • no listing/availability dates set at all
            #   • both listed_until and available_until fully in the past (retired)
            has_active_or_future_listing = Q(listed_from__isnull=False) & (
                Q(listed_until__isnull=True) | Q(listed_until__gte=today)
            )
            has_active_or_future_availability = Q(available_from__isnull=False) & (
                Q(available_until__isnull=True) | Q(available_until__gte=today)
            )
            qs = qs.filter(has_active_or_future_listing | has_active_or_future_availability)
        # else: --all-services → no filter, scan everything

        service_revisions = list(qs)
        scope_label = 'all revisions' if all_services else 'active/future revisions'
        self.stdout.write(f'\nScanning {len(service_revisions)} service revision(s) ({scope_label})...')

        # url → list[(service_key, field_label)]
        url_occurrences: dict[str, list[tuple[str, str]]] = defaultdict(list)

        for sr in service_revisions:
            service_key = sr.key

            # Dedicated URLField
            if sr.url:
                url_occurrences[str(sr.url)].append((service_key, 'url'))

            # Text fields rendered with |urlize in templates
            for field_name, label, is_translated in _TEXT_URL_FIELDS:
                if is_translated:
                    for lang in _LANGUAGES:
                        value = getattr(sr, f'{field_name}_{lang}', None)
                        for url in _extract_urls(value):
                            url_occurrences[url].append((service_key, f'{label} ({lang})'))
                else:
                    value = getattr(sr, field_name, None)
                    for url in _extract_urls(value):
                        url_occurrences[url].append((service_key, label))

        total_refs   = sum(len(v) for v in url_occurrences.values())
        total_unique = len(url_occurrences)
        self.stdout.write(
            f'Found {total_refs} URL reference(s) across all fields '
            f'→ {total_unique} unique URL(s) to check.\n'
        )

        if total_unique == 0:
            self.stdout.write(self.style.SUCCESS('No URLs found in the selected service revisions.'))

        # ------------------------------------------------------------------
        # 2. Check URLs (parallel)
        # ------------------------------------------------------------------
        _headers = {'User-Agent': 'ITSM-ServiceCatalogue-URLChecker/1.0'}

        def _check(url: str) -> tuple[str, int | None, str | None]:
            """Return (url, http_status_or_None, error_message_or_None)."""
            try:
                resp = requests.head(
                    url, allow_redirects=True, timeout=timeout, headers=_headers
                )
                if resp.status_code == 405:
                    # HEAD not supported → fall back to GET (only read headers)
                    resp = requests.get(
                        url,
                        allow_redirects=True,
                        timeout=timeout,
                        headers=_headers,
                        stream=True,
                    )
                    resp.close()
                return url, resp.status_code, None
            except requests.exceptions.SSLError as exc:
                return url, None, f'SSL error: {exc}'
            except requests.exceptions.ConnectionError as exc:
                return url, None, f'Connection error: {exc}'
            except requests.exceptions.Timeout:
                return url, None, f'Timeout (>{timeout}s)'
            except Exception as exc:               # noqa: BLE001
                return url, None, f'Error: {exc}'

        results: dict[str, tuple[int | None, str | None]] = {}
        if total_unique > 0:
            self.stdout.write(
                f'Checking {total_unique} URL(s) with {workers} parallel worker(s)…'
            )
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(_check, url): url for url in url_occurrences}
                done = 0
                for future in as_completed(futures):
                    url, status, error = future.result()
                    results[url] = (status, error)
                    done += 1
                    if done % max(1, total_unique // 20) == 0 or done == total_unique:
                        self.stdout.write(f'  {done}/{total_unique} done…', ending='\r')
                        self.stdout.flush()
            self.stdout.write('')  # newline after in-place progress

        # ------------------------------------------------------------------
        # 3. Categorise
        # ------------------------------------------------------------------
        broken    = []   # (url, status, error, occurrences)  – always reported
        forbidden = []   # HTTP 403
        ok        = []   # 2xx / 3xx
        other     = []   # any other numeric status

        for url, (status, error) in results.items():
            occ = url_occurrences[url]
            if error:
                broken.append((url, status, error, occ))
            elif status == 404:
                broken.append((url, status, None, occ))
            elif status == 403:
                forbidden.append((url, status, None, occ))
            elif status is not None and 200 <= status < 400:
                ok.append((url, status, None, occ))
            else:
                other.append((url, status, None, occ))

        # ------------------------------------------------------------------
        # 4. Report
        # ------------------------------------------------------------------
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Results ===\n'))
        self.stdout.write(f'  ✓  OK (2xx / 3xx)          : {len(ok)}')
        self.stdout.write(f'  ✗  Broken (404 / unreachable): {len(broken)}')
        self.stdout.write(f'  ⚠  Forbidden (403)           : {len(forbidden)}')
        if other:
            self.stdout.write(f'  ?  Other status codes        : {len(other)}')

        # --- Broken URLs ---
        if broken:
            self.stdout.write(self.style.ERROR(f'\n--- Broken URLs ({len(broken)}) ---'))
            for url, status, error, occ in sorted(broken, key=lambda x: x[0]):
                reason = f'HTTP {status}' if status else error
                self.stdout.write(self.style.ERROR(f'\n  {url}'))
                self.stdout.write(f'  Status : {reason}')
                self.stdout.write(f'  Used in:')
                for svc_key, field in occ:
                    self.stdout.write(f'    • {svc_key}  [{field}]')
        else:
            self.stdout.write(self.style.SUCCESS('\nNo broken URLs found. ✓'))

        # --- Forbidden ---
        if forbidden:
            if include_403:
                self.stdout.write(self.style.ERROR(f'\n--- Forbidden / 403 URLs ({len(forbidden)}) ---'))
                for url, _status, _err, occ in sorted(forbidden, key=lambda x: x[0]):
                    self.stdout.write(self.style.ERROR(f'\n  {url}'))
                    self.stdout.write(f'  Status : HTTP 403')
                    self.stdout.write(f'  Used in:')
                    for svc_key, field in occ:
                        self.stdout.write(f'    • {svc_key}  [{field}]')
            else:
                self.stdout.write(self.style.WARNING(
                    f'\n{len(forbidden)} URL(s) returned HTTP 403 (Forbidden).  '
                    'These may be valid but require credentials that this tool does not '
                    'have.  Re-run with --include-403 to list them.'
                ))

        # --- Other status codes ---
        if other:
            self.stdout.write(self.style.WARNING(f'\n--- Unexpected status codes ({len(other)}) ---'))
            for url, status, _err, occ in sorted(other, key=lambda x: x[0]):
                self.stdout.write(self.style.WARNING(f'\n  {url}'))
                self.stdout.write(f'  Status : HTTP {status}')
                for svc_key, field in occ:
                    self.stdout.write(f'    • {svc_key}  [{field}]')

        # ------------------------------------------------------------------
        # 5. Internal link validation
        # ------------------------------------------------------------------
        from ServiceCatalogue.templatetags.text_filters import (
            _classify_internal_link, _ILINK_BROKEN, _ILINK_SOFT,
        )
        from ServiceCatalogue.models import keysep

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Internal Link Validation ===\n'))

        # link_text → list[(service_key, field_label)]
        ilink_occurrences: dict[str, list[tuple[str, str]]] = defaultdict(list)

        for sr in service_revisions:
            service_key = sr.key
            for field_name, label, is_translated in _INTERNAL_LINK_FIELDS:
                if is_translated:
                    for lang in _LANGUAGES:
                        value = getattr(sr, f'{field_name}_{lang}', None)
                        for link_text in _extract_internal_links(value):
                            ilink_occurrences[link_text].append((service_key, f'{label} ({lang})'))
                else:
                    value = getattr(sr, field_name, None)
                    for link_text in _extract_internal_links(value):
                        ilink_occurrences[link_text].append((service_key, label))

        total_ilink_refs   = sum(len(v) for v in ilink_occurrences.values())
        total_unique_ilinks = len(ilink_occurrences)
        self.stdout.write(
            f'Found {total_ilink_refs} internal link reference(s) '
            f'→ {total_unique_ilinks} unique reference(s) to validate.'
        )

        broken_ilinks: list[tuple[str, list]] = []
        soft_ilinks:   list[tuple[str, list]] = []
        ok_ilinks:     list[str]              = []

        for link_text, occ in ilink_occurrences.items():
            kind, _ = _classify_internal_link(link_text)
            if kind == _ILINK_BROKEN:
                broken_ilinks.append((link_text, occ))
            elif kind == _ILINK_SOFT:
                soft_ilinks.append((link_text, occ))
            else:
                ok_ilinks.append(link_text)

        self.stdout.write(f'  ✓  Valid references              : {len(ok_ilinks)}')
        self.stdout.write(f'  ✗  Broken references (no match)  : {len(broken_ilinks)}')
        self.stdout.write(f'  ⚠  Soft links (not validated)    : {len(soft_ilinks)}')

        # --- Broken internal links ---
        if broken_ilinks:
            self.stdout.write(self.style.ERROR(f'\n--- Broken Internal Links ({len(broken_ilinks)}) ---'))
            for link_text, occ in sorted(broken_ilinks, key=lambda x: x[0]):
                self.stdout.write(self.style.ERROR(f'\n  [[{link_text}]]'))
                self.stdout.write('  Reason : No currently-listed service revision matches this key')
                self.stdout.write('  Used in:')
                for svc_key, field in occ:
                    self.stdout.write(f'    • {svc_key}  [{field}]')
        else:
            self.stdout.write(self.style.SUCCESS('\nNo broken internal links found. ✓'))

        # --- Soft (unvalidated) links ---
        if soft_ilinks:
            self.stdout.write(self.style.WARNING(
                f'\n--- Soft (Unvalidated) Internal Links ({len(soft_ilinks)}) ---'
            ))
            self.stdout.write(self.style.WARNING(
                f'  These links do not contain the key separator "{keysep}" '
                'and are not validated against the service catalogue.\n'
            ))
            for link_text, occ in sorted(soft_ilinks, key=lambda x: x[0]):
                self.stdout.write(self.style.WARNING(f'  [[{link_text}]]'))
                for svc_key, field in occ:
                    self.stdout.write(f'    • {svc_key}  [{field}]')

        # ------------------------------------------------------------------
        # 6. Markup in strict fields
        # ------------------------------------------------------------------
        from ServiceCatalogue.models import Service

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Markup in Strict Fields ===\n'))
        self.stdout.write(
            'Checking description and purpose fields for unsupported markup…\n'
            '  • purpose: bold, italic, lists, URLs, internal links → all unsupported\n'
            '  • description: bold, italic, lists, URLs → unsupported (internal links OK)'
        )

        # Collect markup occurrences: (service_key, field_label, findings_list)
        markup_warnings: list[tuple[str, str, list[str]]] = []

        # -- ServiceRevision.description (translated, allows [[...]] but not other markup)
        for sr in service_revisions:
            service_key = sr.key
            for lang in _LANGUAGES:
                value = getattr(sr, f'description_{lang}', None)
                findings = _detect_markup(value, allow_internal_links=True)
                if findings:
                    markup_warnings.append((service_key, f'description ({lang})', findings))

        # -- Service.purpose (translated, no markup at all)
        # Collect unique services from the scanned revisions
        seen_services: set[int] = set()
        for sr in service_revisions:
            if sr.service_id in seen_services:
                continue
            seen_services.add(sr.service_id)
            service_key = sr.service.key
            for lang in _LANGUAGES:
                value = getattr(sr.service, f'purpose_{lang}', None)
                findings = _detect_markup(value, allow_internal_links=False)
                if findings:
                    markup_warnings.append((service_key, f'purpose ({lang})', findings))

        self.stdout.write(f'\n  ⚠  Fields with unsupported markup  : {len(markup_warnings)}')

        if markup_warnings:
            self.stdout.write(self.style.WARNING(
                f'\n--- Unsupported Markup ({len(markup_warnings)}) ---'
            ))
            self.stdout.write(self.style.WARNING(
                '  These fields are "strict" (plain text only). '
                'Markup syntax will not be rendered and may confuse readers.\n'
            ))
            for svc_key, field, findings in sorted(markup_warnings, key=lambda x: (x[0], x[1])):
                self.stdout.write(self.style.WARNING(f'  {svc_key}  [{field}]'))
                self.stdout.write(f'    Found: {", ".join(findings)}')
        else:
            self.stdout.write(self.style.SUCCESS('\nNo unsupported markup found in strict fields. ✓'))

        # ------------------------------------------------------------------
        # 7. Exit
        # ------------------------------------------------------------------
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Summary ===\n'))
        url_issues    = len(broken) + (len(forbidden) if include_403 else 0)
        ilink_issues  = len(broken_ilinks)
        markup_issues = len(markup_warnings)
        issues        = url_issues + ilink_issues
        if issues:
            parts = []
            if url_issues:
                parts.append(f'{url_issues} URL(s)')
            if ilink_issues:
                parts.append(f'{ilink_issues} internal link(s)')
            self.stdout.write(self.style.ERROR(
                f'❌ {", ".join(parts)} require attention.  '
                'Please update or remove them in the affected service revisions.'
            ))
        if markup_issues:
            self.stdout.write(self.style.WARNING(
                f'⚠  {markup_issues} field(s) contain unsupported markup (warnings only).'
            ))
        if not issues and not markup_issues:
            self.stdout.write(self.style.SUCCESS(
                '✅ All checked URLs are reachable, all internal links are valid, '
                'and no unsupported markup was found.\n'
            ))
        else:
            self.stdout.write('')
        sys.exit(1 if issues else 0)
