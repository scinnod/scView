from django.contrib import admin
from ServiceCatalogue.models import *
from datetime import date
from django.db.models import Q
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _l
from modeltranslation.admin import TranslationAdmin
from django.urls import reverse
from django.conf import settings

# Register your models here.
# inline models


class ServiceRevisionAdminInline(admin.TabularInline):
    model = ServiceRevision
    fields = (
        "short_name",
        "status_listing",
        "status_availablility",
    )
    readonly_fields = (
        "short_name",
        "status_listing",
        "status_availablility",
    )
    extra = 0
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


class ServiceAdminInline(admin.TabularInline):
    model = Service
    fields = (
        "key",
        "name",
        "responsible",
    )
    readonly_fields = (
        "key",
        "name",
        "responsible",
    )
    extra = 0
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


class AvailabilityAdminInline(admin.TabularInline):
    model = Availability
    extra = 0


class ROAvailabilityAdminInline(admin.TabularInline):
    model = Availability
    extra = 0
    fields = ("servicerevision", "charged", "fee", "fee_unit")
    readonly_fields = ("servicerevision", "charged", "fee", "fee_unit")

    def has_add_permission(self, request, obj=None):
        return False


class ServiceProviderListFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.

    title = _l("Service Providers")

    # Parameter for the filter that will be used in the URL query.
    parameter_name = "sp"

    def lookups(self, request, model_admin):
        """
        Only show the lookups if there actually is
        anyone born in the corresponding decades.
        """
        serviceproviders = ServiceProvider.objects.all()
        return [
            (sp.hierarchy, sp.hierarchy + " " + sp.name)
            for sp in serviceproviders
            if (len(sp.hierarchy) <= 3 and not self.value())
            or (
                self.value()
                and (
                    all([i == j for i, j in zip(sp.hierarchy, self.value())])
                    and (len(sp.hierarchy) - len(self.value()) <= 2)
                )
            )
        ]

    def queryset(self, request, queryset):
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        if self.value():
            return queryset.filter(
                service_providers__hierarchy__startswith=self.value()
            ).distinct()
        else:
            return queryset.all()


class ServiceAdmin(SimpleHistoryAdmin, TranslationAdmin):
    model = Service
    search_fields = (
        "name",
        "acronym",
        "category__acronym",
    )
    list_display = (
        "order_key",
        "name",
        "responsible",
        "revisions",
        "listed",
        "available",
    )
    list_display_links = (
        "order_key",
        "name",
    )
    list_filter = (
        "category",
        ServiceProviderListFilter,
    )
    readonly_fields = ("add_link",)
    inlines = (ServiceRevisionAdminInline,)

    def revisions(self, obj):
        today = date.today()
        return obj.servicerevision_set.count()

    def listed(self, obj):
        today = date.today()
        return (
            obj.servicerevision_set.filter(listed_from__lte=today)
            .exclude(listed_until__lt=today)
            .count()
        )

    def available(self, obj):
        today = date.today()
        return (
            obj.servicerevision_set.filter(available_from__lte=today)
            .exclude(available_until__lt=today)
            .count()
        )

    def add_link(self, obj):
        if obj and obj.id:
            return format_html(
                '<a href="%s?service=%s">%s</a>'
                % (
                    reverse("admin:ServiceCatalogue_servicerevision_add"),
                    obj.id,
                    _("Link to add form (empty new service revision)"),
                )
            )
        else:
            return _("Please save this new service first. Link will be available then.")

    add_link.short_description = _l("Add new revision")


admin.site.register(Service, ServiceAdmin)


class ListedListFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _l("Published")

    # Parameter for the filter that will be used in the URL query.
    parameter_name = "pub"

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return (
            ("0-notsub", _("not yet submitted")),
            ("1-sub", _("submitted but not scheduled")),
            ("2-scheduled", _("scheduled for listing")),
            ("3-current", _("currently listed")),
            ("4-notanymore", _("not anymore more listed")),
        )

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        today = date.today()
        if self.value() == "0-notsub":
            return queryset.filter(listed_from=None, submitted=False)
        if self.value() == "1-sub":
            return queryset.filter(listed_from=None, submitted=True)
        if self.value() == "2-scheduled":
            return queryset.filter(
                listed_from__gt=today,
            )
        if self.value() == "3-current":
            return queryset.exclude(listed_until__lt=today).filter(
                listed_from__lte=today,
            )
        if self.value() == "4-notanymore":
            return queryset.filter(
                listed_until__lt=today,
            )


class AvailableListFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _("Available")

    # Parameter for the filter that will be used in the URL query.
    parameter_name = "avail"

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return (
            ("0-notyet", _("not yet scheduled")),
            ("1-scheduled", _("scheduled")),
            ("2-current", _("available")),
            ("2-current-eol", _("available, EOL scheduled")),
            ("3-notanymore", _("EOL reached")),
        )

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        today = date.today()
        if self.value() == "0-notyet":
            return queryset.filter(
                available_from=None,
            )
        if self.value() == "1-scheduled":
            return queryset.filter(
                available_from__gt=today,
            )
        if self.value() == "2-current":
            return queryset.filter(
                available_from__lte=today,
                available_until__isnull=True,
            )
        if self.value() == "2-current-eol":
            return queryset.filter(
                available_from__lte=today,
                available_until__gte=today,
            )
        if self.value() == "3-notanymore":
            return queryset.filter(
                available_until__lt=today,
            )


# Build ServiceRevision fields list based on settings
def _build_servicerevision_fields():
    """Construct fields tuple for ServiceRevisionAdmin based on settings."""
    fields = [
        "service",
        "service_purpose",
        "version",
        "submitted",
        "listed_from",
        "available_from",
        "description",
        "description_internal",
    ]
    
    if settings.SERVICECATALOGUE_FIELD_KEYWORDS:
        fields.append("keywords")
    if settings.SERVICECATALOGUE_FIELD_USAGE_INFORMATION:
        fields.append("usage_information")
    if settings.SERVICECATALOGUE_FIELD_REQUIREMENTS:
        fields.append("requirements")
    if settings.SERVICECATALOGUE_FIELD_DETAILS:
        fields.append("details")
    if settings.SERVICECATALOGUE_FIELD_OPTIONS:
        fields.append("options")
    if settings.SERVICECATALOGUE_FIELD_SERVICE_LEVEL:
        fields.append("service_level")
    
    fields.extend([
        "contact",
        "url",
        "listed_until",
        "available_until",
        "eol",
    ])
    
    return tuple(fields)


class ServiceRevisionAdmin(SimpleHistoryAdmin, TranslationAdmin):
    model = ServiceRevision
    search_fields = (
        "service__name",
        "service__acronym",
        "service__category__acronym",
        "version",
    )
    list_display = (
        "short_name",
        "status_listing",
        "status_availablility",
    )
    list_display_links = ("short_name",)
    # Fields constructed at module load based on settings
    fields = _build_servicerevision_fields()
    readonly_fields = ("service_purpose",)
    autocomplete_fields = ("service",)
    list_filter = (
        "service__category",
        ListedListFilter,
        AvailableListFilter,
    )
    inlines = (AvailabilityAdminInline,)
    save_as = True

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        # remove option to save for records scheduled for publication for users without publication permission (authors), copying of records still possible.
        context.update(
            {
                "show_save": request.user.has_perm(
                    "ServiceCatalogue.can_publish_service"
                )
                or not (
                    obj and (obj.available_from or obj.listed_from or obj.submitted)
                ),
                "show_save_and_continue": request.user.has_perm(
                    "ServiceCatalogue.can_publish_service"
                )
                or not (
                    obj and (obj.available_from or obj.listed_from or obj.submitted)
                ),
            }
        )
        return super().render_change_form(request, context, add, change, form_url, obj)

    def get_readonly_fields(self, request, obj=None):
        # readonly fields also are emptied upon copying of records -> copies remain unpiublished
        readonly_fields = self.readonly_fields
        if not request.user.has_perm("ServiceCatalogue.can_publish_service"):
            readonly_fields += (
                "available_from",
                "available_until",
                "listed_from",
                "listed_until",
            )
        if (
            not request.user.has_perm("ServiceCatalogue.can_publish_service")
            and obj
            and obj.submitted
        ):
            readonly_fields += ("submitted",)
        return readonly_fields

    def has_delete_permission(self, request, obj=None):
        if (
            not request.user.has_perm("ServiceCatalogue.can_publish_service")
            and obj
            and (obj.available_from or obj.listed_from or obj.submitted)
        ):
            # users without publish permission can only delete services before they are marked for publication
            return False
        elif (
            obj
            and obj.available_from
            and obj.available_from <= date.today()
            and not (obj.available_until and obj.available_until < date.today())
        ):
            # nobody can delete services while they are online
            return False
        elif (
            obj
            and obj.listed_from
            and obj.listed_from <= date.today()
            and not (obj.listed_until and obj.listed_until < date.today())
        ):
            # nobody can delete services while they are online
            return False
        else:
            return request.user.has_perm("ServiceCatalogue.delete_servicerevision")


admin.site.register(ServiceRevision, ServiceRevisionAdmin)


class ClienteleAdmin(SimpleHistoryAdmin, TranslationAdmin):
    model = Clientele
    inlines = (ROAvailabilityAdminInline,)


admin.site.register(Clientele, ClienteleAdmin)


class ServiceCategoryAdmin(SimpleHistoryAdmin, TranslationAdmin):
    list_display = (
        "order_key",
        "name",
        "responsible",
        "services",
    )
    list_display_links = (
        "order_key",
        "name",
    )
    model = ServiceCategory
    inlines = (ServiceAdminInline,)
    readonly_fields = ("add_link_service",)

    def services(self, obj):
        return obj.service_set.count()

    def add_link_service(self, obj):
        if obj and obj.id:
            return format_html(
                '<a href="%s?category=%s">%s</a>'
                % (
                    reverse("admin:ServiceCatalogue_service_add"),
                    obj.id,
                    _("Link to add form (new service)"),
                )
            )
        else:
            return _("Please save this new category. Link will be available then.")

    add_link_service.short_description = _l("Add new service")


#    tbd: use this to enable responsible manager to edit...
#    def has_change_permission(self, request, obj=None):
#        return True

admin.site.register(ServiceCategory, ServiceCategoryAdmin)


class FeeUnitAdmin(SimpleHistoryAdmin, TranslationAdmin):
    model = FeeUnit


admin.site.register(FeeUnit, FeeUnitAdmin)


admin.site.register(ServiceProvider, SimpleHistoryAdmin)


# AI Search Log Admin
@admin.register(AISearchLog)
class AISearchLogAdmin(admin.ModelAdmin):
    """Admin interface for AI search logs."""
    list_display = (
        'timestamp',
        'user',
        'step1_completed',
        'step2_needed',
        'services_count',
        'recommendations_count',
        'total_tokens',
        'duration_seconds',
        'error_occurred',
    )
    list_filter = (
        'error_occurred',
        'step1_completed',
        'step2_needed',
        'timestamp',
    )
    search_fields = (
        'user__username',
        'user__email',
    )
    readonly_fields = (
        'timestamp',
        'user',
        'step1_completed',
        'step2_needed',
        'services_requested',
        'services_recommended',
        'tokens_used_step1',
        'tokens_used_step2',
        'error_occurred',
        'error_message',
        'duration_seconds',
    )
    date_hierarchy = 'timestamp'
    
    def services_count(self, obj):
        """Count of services requested for evaluation."""
        if obj.services_requested:
            return len(obj.services_requested)
        return 0
    services_count.short_description = _l('Services requested')
    
    def recommendations_count(self, obj):
        """Count of services recommended to user."""
        if obj.services_recommended:
            return len(obj.services_recommended)
        return 0
    recommendations_count.short_description = _l('Services recommended')
    
    def total_tokens(self, obj):
        """Total tokens used across both steps."""
        total = 0
        if obj.tokens_used_step1:
            total += obj.tokens_used_step1
        if obj.tokens_used_step2:
            total += obj.tokens_used_step2
        return total if total > 0 else None
    total_tokens.short_description = _l('Total tokens')
    
    def has_add_permission(self, request):
        """Prevent manual creation of log entries."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing of log entries."""
        return False

