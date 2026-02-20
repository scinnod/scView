# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
"""
Service Catalogue Models

Data models for the ITSM Service Catalogue application.
"""

import re
from datetime import date

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

# define seperators characters for key hierarchy:
keysep = "-"
keysep_order = ":"


def get_default_helpdesk_email():
    """Get default helpdesk email from settings"""
    return settings.HELPDESK_EMAIL


class ServiceProvider(models.Model):
    hierarchy = models.CharField(
        max_length=10,
        verbose_name=_("Hierarchy of service providing units"),
        help_text=_("Recommendation: seperation by 'dots'"),
    )
    name = models.CharField(max_length=80, verbose_name=_("Name"))
    acronym = models.CharField(
        blank=True,
        null=True,
        max_length=10,
        verbose_name=_("Acronym"),
        help_text=_("Not required, only if applies."),
    )

    def __str__(self):
        return "%s %s%s" % (
            self.hierarchy,
            self.name,
            " ({})".format(self.acronym) if self.acronym else "",
        )

    class Meta:
        verbose_name = _("_Service provider")
        verbose_name_plural = _("_Service Providers")
        ordering = ["hierarchy", "name"]
        indexes = [
            # GIN indices for fulltext search (used in staff search via service__service_providers__)
            GinIndex(fields=['name'], opclasses=['gin_trgm_ops'], name='serviceprov_name_gin'),
            GinIndex(fields=['acronym'], opclasses=['gin_trgm_ops'], name='serviceprov_acro_gin'),
        ]

    history = HistoricalRecords()


class Clientele(models.Model):
    order = models.CharField(
        max_length=10,
        verbose_name=_("Order in listings"),
        blank=True,
        null=True,
        help_text=_(
            "Can be used to adjust order of service providers. Otherwise names are used."
        ),
    )
    name = models.CharField(max_length=80, verbose_name=_("Name"))
    acronym = models.CharField(
        unique=True, max_length=10, verbose_name=_("Identifyer / Acronym")
    )

    def __str__(self):
        return "%s: %s" % (self.acronym, self.name)

    class Meta:
        verbose_name = _("_Clientele Group")
        verbose_name_plural = _("_Clientele Groups")
        ordering = ["order", "acronym"]


#    history = HistoricalRecords() -> activated in translation.py in order to also consider translated field


class ServiceCategory(models.Model):
    order = models.CharField(
        max_length=10,
        verbose_name=_("Order in listings"),
        blank=True,
        null=True,
        help_text=_(
            "Can be used to adjust order of service providers. Otherwise names are used."
        ),
    )
    name = models.CharField(max_length=80, verbose_name=_("Name"))
    acronym = models.CharField(
        unique=True, max_length=10, verbose_name=_("Identifyer / Acronym")
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Service category description shown in catalogues"),
    )
    #    responsible = models.ForeignKey(User,blank=True, null=True,on_delete=models.RESTRICT, verbose_name=_("Responsible person / category manager"))
    responsible = models.CharField(
        max_length=80,
        blank=True,
        null=True,
        verbose_name=_("Responsible / category owner"),
    )

    def __str__(self):
        return "%s %s" % (self.key, self.name)

    class Meta:
        verbose_name = _("  Service Category")
        verbose_name_plural = _("  Service Categories")
        ordering = ["order", "acronym"]

    @property
    def key(self):
        return "%s" % (self.acronym)

    @property
    def order_key(self):
        return "%s%s%s" % (self.order, keysep_order, self.key)


#    history = HistoricalRecords() -> activated in translation.py in order to also consider translated field


class Service(models.Model):
    order = models.CharField(
        max_length=10,
        verbose_name=_("Order in listings"),
        blank=True,
        null=True,
        help_text=_(
            "Can be used to adjust order of service providers. Otherwise names are used."
        ),
    )
    category = models.ForeignKey(
        ServiceCategory, on_delete=models.RESTRICT, verbose_name=_("Service Category")
    )
    name = models.CharField(max_length=80, verbose_name=_("Name (public, search, ai)"))
    acronym = models.CharField(max_length=10, verbose_name=_("Identifyer / Acronym"))
    purpose = models.TextField(
        verbose_name=_("Main purpose / added value of this service (public, search, ai)"),
        help_text=_(
            "Why is this service offered? What is the intended particular benefit for the user? (brief description only)"
        ),
    )
    #    responsible = models.ForeignKey(User, blank=True, null=True,on_delete=models.RESTRICT, verbose_name=_("Responsible person / service manager"))
    responsible = models.CharField(
        max_length=80,
        blank=True,
        null=True,
        verbose_name=_("Responsible / service owner"),
        help_text=_(
            "Contact person with overall responsibility for aligning the service with the needs of the users, the quality and the improvement of the service"
        ),
    )
    service_providers = models.ManyToManyField(
        ServiceProvider,
        blank=True,
        verbose_name=_("Teams involved in service provision"),
    )

    def __str__(self):
        return "%s %s" % (self.key, self.name)

    class Meta:
        verbose_name = _(" Service")
        verbose_name_plural = _(" Services")
        unique_together = (
            "category",
            "acronym",
        )
        ordering = ["category__order", "order", "acronym"]
        indexes = [
            # GIN indices for fulltext search on Service fields
            GinIndex(fields=['name_de'], opclasses=['gin_trgm_ops'], name='service_name_de_gin'),
            GinIndex(fields=['name_en'], opclasses=['gin_trgm_ops'], name='service_name_en_gin'),
            GinIndex(fields=['purpose_de'], opclasses=['gin_trgm_ops'], name='service_purp_de_gin'),
            GinIndex(fields=['purpose_en'], opclasses=['gin_trgm_ops'], name='service_purp_en_gin'),
            GinIndex(fields=['acronym'], opclasses=['gin_trgm_ops'], name='service_acro_gin'),
            GinIndex(fields=['responsible'], opclasses=['gin_trgm_ops'], name='service_resp_gin'),
        ]

    @property
    def key(self):
        return "{}{}{}".format(self.category.key, keysep, self.acronym)

    @property
    def order_key(self):
        return "{}{}{}{}".format(
            self.category.key,
            keysep,
            self.order + keysep_order if self.order else "",
            self.acronym,
        )



#    history = HistoricalRecords() -> activated in translation.py in order to also consider translated field


class ServiceRevision(models.Model):
    service = models.ForeignKey(
        Service, on_delete=models.RESTRICT, verbose_name=_("Service")
    )
    version = models.CharField(max_length=10, verbose_name=_("Version / Revision"))
    keywords = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Search keywords (search)"),
        help_text=_(
            "Additional keywords for fulltext search (words separated by spaces). These keywords are used for searching but not visible to users."
        ),
    )
    submitted = models.BooleanField(
        default=False,
        verbose_name=_("Submitted for public listing?"),
        help_text=_(
            "Submitted services revisions become visible for staff users. Contact an editor for final publication or if further changes are required."
        ),
    )
    listed_from = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Listed from"),
        help_text=_(
            "Date, when this service is listed initially and can be ordered. Not listed if blank."
        ),
    )
    available_from = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Available from"),
        help_text=_(
            "Date, when this service is available for users. Should not be empty."
        ),
    )
    description_internal = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Internal description / configuration"),
        help_text=_(
            "For instance: details on hardware, configuration details, pitfalls, documentation requirements etc. May contain links to external sources. "
            "Supports formatting: **bold**, *italic*, lists (- item / 1. item), URLs (auto-linked), and internal links ([[SERVICE-KEY]])."
        ),
    )
    description = models.TextField(
        verbose_name=_("Service description (public, search, ai)"),
        help_text=_(
            "Self-contained service description. Please avoid links to external sources, if possible."
        ),
    )
    usage_information = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Please Note (public, search, ai)"),
        help_text=_(
            "Important information for using this service, e.g. regarding compliance with data privacy, information security and/or AI regulations (EU AI Act). This text is displayed highlighted in the service description. "
            "Supports formatting: **bold**, *italic*, lists (- item / 1. item), URLs (auto-linked), and internal links ([[SERVICE-KEY]])."
        ),
    )
    requirements = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Requirements for use of service, if any. (public, search, ai)"),
        help_text=_(
            "Supports formatting: **bold**, *italic*, lists (- item / 1. item), URLs (auto-linked), and internal links ([[SERVICE-KEY]])."
        ),
    )
    details = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Service details (public, search, ai)"),
        help_text=_(
            "Detailed description and notes on availability / service levels and support during operation, etc. if applicable. May contain links to external sources. "
            "Supports formatting: **bold**, *italic*, lists (- item / 1. item), URLs (auto-linked), and internal links ([[SERVICE-KEY]])."
        ),
    )
    options = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Available options (public, search, ai)"),
        help_text=_(
            "Can be used to harmonize user-specific requirements and wishes, at least to some extent. "
            "Supports formatting: **bold**, *italic*, lists (- item / 1. item), URLs (auto-linked), and internal links ([[SERVICE-KEY]])."
        ),
    )
    service_level = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Service level / SLA (public, ai)"),
        help_text=_(
            "Service level agreement, availability guarantees, support hours, uptime commitments, and response time expectations. "
            "Supports formatting: **bold**, *italic*, lists (- item / 1. item), URLs (auto-linked), and internal links ([[SERVICE-KEY]])."
        ),
    )
    contact = models.EmailField(
        max_length=80,
        blank=True,
        null=True,
        default=get_default_helpdesk_email,
        verbose_name=_("Contact Email"),
        help_text=_(
            "Email address which should be used for service requests. If possible helpdesk or other institutional email address, if not applicable also personal email adresses can be used (but might require effort in maintenance)."
        ),
    )
    url = models.URLField(
        max_length=250,
        blank=True,
        null=True,
        verbose_name=_("URL to service"),
        help_text=_(
            "If available. Please include http://  or https:// and make sure the URL is safe, i.e. it does not contain malicious code and it is maintained."
        ),
    )
    listed_until = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Listed until"),
        help_text=_(
            "Date, when this service is removed from the catalogue and is not avaliable to new users any more."
        ),
    )
    available_until = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Available until / EOL"),
        help_text=_(
            "Date, when this service is discontinued for all users. Should be known and set when service is removed from the catalogue."
        ),
    )
    eol = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("What should happen at EOL?"),
        help_text=_(
            "Give some hints what to do with this service at end of life, e.g. which which revision to transfer to or which action to take. "
            "Supports formatting: **bold**, *italic*, lists (- item / 1. item), URLs (auto-linked), and internal links ([[SERVICE-KEY]])."
        ),
    )
    search_keys = models.CharField(
        max_length=250,
        editable=False,
        blank=True,
        null=True,
        verbose_name=_("used for fulltext-search only, should not be editable"),
    )

    def __str__(self):
        return "%s %s" % (self.key, self.service.name)

    class Meta:
        permissions = (("can_publish_service", _("Can publish services")),)
        verbose_name = _("Service Revision / Detail")
        verbose_name_plural = _("Service Revisions / Details")
        unique_together = (
            "service",
            "version",
        )
        ordering = ["service__category__order", "service__order", "version"]
        indexes = [
            # GIN indices for fulltext search performance
            # These dramatically speed up SearchVector queries on text fields
            # Translatable fields (both de and en)
            GinIndex(fields=['description_de'], opclasses=['gin_trgm_ops'], name='servicerev_desc_de_gin'),
            GinIndex(fields=['description_en'], opclasses=['gin_trgm_ops'], name='servicerev_desc_en_gin'),
            GinIndex(fields=['keywords_de'], opclasses=['gin_trgm_ops'], name='servicerev_kw_de_gin'),
            GinIndex(fields=['keywords_en'], opclasses=['gin_trgm_ops'], name='servicerev_kw_en_gin'),
            GinIndex(fields=['requirements_de'], opclasses=['gin_trgm_ops'], name='servicerev_req_de_gin'),
            GinIndex(fields=['requirements_en'], opclasses=['gin_trgm_ops'], name='servicerev_req_en_gin'),
            GinIndex(fields=['usage_information_de'], opclasses=['gin_trgm_ops'], name='servicerev_uinf_de_gin'),
            GinIndex(fields=['usage_information_en'], opclasses=['gin_trgm_ops'], name='servicerev_uinf_en_gin'),
            GinIndex(fields=['details_de'], opclasses=['gin_trgm_ops'], name='servicerev_det_de_gin'),
            GinIndex(fields=['details_en'], opclasses=['gin_trgm_ops'], name='servicerev_det_en_gin'),
            GinIndex(fields=['options_de'], opclasses=['gin_trgm_ops'], name='servicerev_opt_de_gin'),
            GinIndex(fields=['options_en'], opclasses=['gin_trgm_ops'], name='servicerev_opt_en_gin'),
            GinIndex(fields=['service_level_de'], opclasses=['gin_trgm_ops'], name='servicerev_slvl_de_gin'),
            GinIndex(fields=['service_level_en'], opclasses=['gin_trgm_ops'], name='servicerev_slvl_en_gin'),
            # Non-translatable text fields
            GinIndex(fields=['description_internal'], opclasses=['gin_trgm_ops'], name='servicerev_dint_gin'),
            GinIndex(fields=['version'], opclasses=['gin_trgm_ops'], name='servicerev_ver_gin'),
            GinIndex(fields=['eol'], opclasses=['gin_trgm_ops'], name='servicerev_eol_gin'),
            GinIndex(fields=['search_keys'], opclasses=['gin_trgm_ops'], name='servicerev_skeys_gin'),
        ]

    def clean(self):
        # Don't allow until date without from date.
        if self.listed_until is not None and self.listed_from is None:
            raise ValidationError(
                _(
                    'If "listed until" is set please also indicate "listed from". Alternatively remove "listed until".'
                )
            )
        # check validity of date for availability
        elif (
            self.listed_until is not None
            and self.listed_from is not None
            and self.listed_until < self.listed_from
        ):
            raise ValidationError(
                _('"listed until" cannot be earlier than "listed from".')
            )
        elif self.listed_until is not None and self.available_until is None:
            raise ValidationError(
                _(
                    'If setting "listed_until" please also indicate end of availabiliy of service ("available_until").'
                )
            )
        elif self.available_until is not None and self.eol == "":
            raise ValidationError(
                _(
                    'Please indicate what to do at EOL with remaining users (if any) and fill field "What should happen att EOL?".'
                )
            )
        if self.available_until is not None and self.available_from is None:
            raise ValidationError(
                _(
                    'If "available until" is set please also indicate "available from". Alternatively remove "available until".'
                )
            )
        # check validity of date for availability
        elif (
            self.available_until is not None
            and self.available_from is not None
            and self.available_until < self.available_from
        ):
            raise ValidationError(
                _('"available until" cannot be earlier than "available from".')
            )

    # uses for readonly field in admin interface
    @property
    def service_purpose(self):
        return self.service.purpose if self.service else ""

    service_purpose.fget.short_description = _("service main purpose / added value")

    @property
    def key(self):
        return "{}{}{}".format(self.service.key, keysep, self.version)

    @property
    def short_name(self):
        return "{} {}".format(
            self.key,
            self.service.name[:37] + "..."
            if len(self.service.name) > 40
            else self.service.name,
        )

    @property
    def status_listing(self):
        today = date.today()
        if self.listed_from is None and not self.submitted:
            return _("0-not yet submitted")
        elif self.listed_from is None and self.submitted:
            return _("1-submitted but not yet scheduled")
        elif self.listed_from > today:
            return _("2-listing at {}").format(self.listed_from)
        elif (self.listed_until) and (self.listed_until <= today):
            return _("4-not more listed since {}").format(self.listed_until)
        else:
            return _("3-currently listed")

    @property
    def status_availablility(self):
        today = date.today()
        if self.available_from is None:
            return _("0-availability not scheduled")
        elif self.available_from > today:
            return _("1-available at {}").format(self.available_from)
        elif self.available_until and (self.available_until < today):
            return _("4-not more available since {}").format(self.available_until)
        elif self.available_until:
            return _("3-available, EOL {}").format(self.available_until)
        else:
            return _("2-available, EOL unknown")

    def generate_search_keys(self):
        """Generate search_keys from service metadata and URL.
        
        Called automatically by pre_save signal to ensure search_keys
        are always up-to-date, even during fixture loading.
        """
        
        # Extract searchable keywords from URL
        url_keywords = ""
        if self.url:
            # Remove protocol and www, take first 100 chars
            url_clean = re.sub(r'^https?://(www\.)?', '', str(self.url)[:100])
            # Split by common URL delimiters and convert to lowercase
            words = re.split(r'[/\-_.?=&#+]', url_clean.lower())
            # Filter out common TLDs, empty strings, and very short words
            common_tlds = {'com', 'de', 'org', 'net', 'edu', 'gov', 'io', 'co', 'uk'}
            url_keywords = " ".join(
                word for word in words 
                if word and len(word) > 1 and word not in common_tlds
            )
        
        self.search_keys = " ".join(filter(None, [
            self.key,
            self.service.key,
            self.service.category.acronym,
            url_keywords
        ]))

    def save(self, *args, **kwargs):
        """Reset submission flag if service is listed and/or available."""
        if self.listed_from or self.available_from:
            self.submitted = False
        super(ServiceRevision, self).save(*args, **kwargs)


#    history = HistoricalRecords() -> activated in translation.py in order to also consider translated field


class FeeUnit(models.Model):
    name = models.CharField(max_length=50, verbose_name=_("Label"))

    def __str__(self):
        return "%s" % (self.name)

    class Meta:
        verbose_name = _("_Charging unit")
        verbose_name_plural = _("_Charging units")


#    history = HistoricalRecords() -> activated in translation.py in order to also consider translated field


class Availability(models.Model):
    servicerevision = models.ForeignKey(ServiceRevision, on_delete=models.CASCADE)
    clientele = models.ForeignKey(Clientele, on_delete=models.CASCADE)
    comment = models.TextField(blank=True, null=True, verbose_name=_("Comment"))
    charged = models.BooleanField(default=False, verbose_name=_("Subject to charges?"))
    fee = models.DecimalField(
        decimal_places=2, max_digits=10, default=0, verbose_name=_("User fee")
    )
    fee_unit = models.ForeignKey(
        FeeUnit,
        on_delete=models.RESTRICT,
        blank=True,
        null=True,
        verbose_name=_("Unit"),
    )

    def __str__(self):
        return "%s: %s" % (self.servicerevision.key, self.clientele.name)

    class Meta:
        verbose_name = _("Availability")
        verbose_name_plural = _("Availabilities")
        unique_together = (
            "servicerevision",
            "clientele",
        )
        ordering = [
            "clientele__order",
            "clientele__acronym",
        ]

    history = HistoricalRecords()

    @property
    def clientele_name_with_costs(self):
        # used in templates
        if self.charged:
            if self.fee > 0:
                return "{} ({} {}{})".format(
                    self.clientele.name,
                    self.fee,
                    self.fee_unit,
                    ", {}".format(self.comment) if self.comment else "",
                )
            else:
                return "{} ({}{})".format(
                    self.clientele.name,
                    self.fee_unit,
                    ", {}".format(self.comment) if self.comment else "",
                )
        else:
            return "{}{}".format(
                self.clientele.name,
                " ({})".format(self.comment) if self.comment else "",
            )

# Signals for automatic search_keys generation and cascade updates

@receiver(pre_save, sender=ServiceRevision)
def update_servicerevision_search_keys(sender, instance, **kwargs):
    """Generate search_keys before saving ServiceRevision.
    
    This ensures search_keys are always up-to-date, even when:
    - Loading fixtures
    - Using bulk operations
    - Importing data via management commands
    """
    instance.generate_search_keys()


@receiver(post_save, sender=Service)
def update_service_revisions_on_service_change(sender, instance, **kwargs):
    """Update all ServiceRevision search_keys when Service changes.
    
    This handles cascade updates when service metadata changes
    (e.g., acronym, category) that affect the search_keys.
    """
    for sr in ServiceRevision.objects.filter(service=instance):
        sr.save()  # Triggers pre_save signal to regenerate search_keys


@receiver(post_save, sender=ServiceCategory)
def update_service_revisions_on_category_change(sender, instance, **kwargs):
    """Update all ServiceRevision search_keys when ServiceCategory changes.
    
    This handles cascade updates when category metadata changes
    (e.g., acronym) that affect the search_keys of all services in this category.
    """
    for sr in ServiceRevision.objects.filter(service__category=instance):
        sr.save()  # Triggers pre_save signal to regenerate search_keys


class AISearchLog(models.Model):
    """
    Logs AI-assisted search requests for analytics and monitoring.
    
    Does NOT store user input or AI responses for privacy reasons.
    Only stores metadata about the search process and results.
    """
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Timestamp"),
        help_text=_("When the AI search was initiated")
    )
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("User"),
        help_text=_("User who initiated the search")
    )
    step1_completed = models.BooleanField(
        default=False,
        verbose_name=_("Step 1 completed"),
        help_text=_("Whether the first AI call (initial evaluation) completed successfully")
    )
    step2_needed = models.BooleanField(
        default=False,
        verbose_name=_("Step 2 needed"),
        help_text=_("Whether detailed service information was requested")
    )
    services_requested = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Services requested for detailed evaluation"),
        help_text=_("List of service keys requested in step 1 for detailed evaluation in step 2")
    )
    services_recommended = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Services recommended"),
        help_text=_("List of service keys recommended to the user in the final response")
    )
    tokens_used_step1 = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Tokens used in step 1"),
        help_text=_("Number of tokens consumed in the first AI call")
    )
    tokens_used_step2 = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Tokens used in step 2"),
        help_text=_("Number of tokens consumed in the second AI call (if applicable)")
    )
    error_occurred = models.BooleanField(
        default=False,
        verbose_name=_("Error occurred"),
        help_text=_("Whether an error occurred during the search process")
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Error message"),
        help_text=_("Error message if an error occurred (for debugging)")
    )
    duration_seconds = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Duration (seconds)"),
        help_text=_("Total duration of the search process in seconds")
    )
    
    def __str__(self):
        return f"AI Search by {self.user} at {self.timestamp}"
    
    class Meta:
        verbose_name = _("AI Search Log")
        verbose_name_plural = _("AI Search Logs")
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
        ]