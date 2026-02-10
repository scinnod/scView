from django.urls import path
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect

from . import views
from . import api_views

# app_name = "servicecatalogue"

urlpatterns = [
    path(
        "", lambda request: redirect("services_jump", permanent=False), name="index"
    ),
    path("services", (views.ServiceListedView.as_view()), name="services_listed"),
    path("services/<int:clientele_id>", (views.ServiceListedView.as_view()), name="services_listed_clientele"),
    path(
        "service/<int:pk>",
        (views.ServiceDetailView.as_view()),
        name="service_detail",
    ),
    path(
        "service_by_key/<str:service_key>/",
        views.service_detail_by_key,
        name="service_detail_by_key",
    ),
    path(
        "online_services_jump_page",
        (views.ServiceJumpView.as_view()),
        name="services_jump_depreciated",
    ),
    path(
        "online_services_jump_page/<int:clientele_id>",
        (views.ServiceJumpView.as_view()),
    ),
    path(
        "online_services_directory",
        (views.ServiceJumpView.as_view()),
        name="services_jump",
    ),
    path(
        "online_services_directory/<int:clientele_id>",
        (views.ServiceJumpView.as_view()),
        name="services_jump_clientele",
    ),
    path(
        "services_under_revision",
        (views.ServiceUnderRevisionView.as_view()),
        name="services_under_revision",
    ),
    path(
        "services_under_revision/<int:clientele_id>",
        (views.ServiceUnderRevisionView.as_view()),
        name="services_under_revision_clientele",
    ),
    path(
        "services_available",
        (views.ServiceAvailableView.as_view()),
        name="services_available",
    ),
    path(
        "services_available/<int:clientele_id>",
        (views.ServiceAvailableView.as_view()),
        name="services_available_clientele",
    ),
    path(
        "services_retired",
        (views.ServiceRetiredView.as_view()),
        name="services_retired",
    ),
    path(
        "services_retired/<int:clientele_id>",
        (views.ServiceRetiredView.as_view()),
        name="services_retired_clientele",
    ),
    path(
        "services_upcoming",
        (views.ServiceUpcomingView.as_view()),
        name="services_upcoming",
    ),
    path(
        "services_upcoming/<int:clientele_id>",
        (views.ServiceUpcomingView.as_view()),
        name="services_upcoming_clientele",
    ),
    path("services_pdf", views.export_pdf, name="export_pdf"),
    path(
        "export_xlsx",
        views.export_xlsx,
        name="export_excel",
    ),
    # AI-Assisted Search
    path(
        "ai_search/",
        views.ai_search_view,
        name="ai_search"
    ),
    path(
        "ai_search/initiate/",
        views.ai_search_initiate,
        name="ai_search_initiate"
    ),
    path(
        "ai_search/status/<str:request_id>/",
        views.ai_search_status,
        name="ai_search_status"
    ),
    path(
        "ai_search/clear/<str:request_id>/",
        views.ai_search_clear,
        name="ai_search_clear"
    ),
    # REST API endpoints for external integrations (SharePoint, etc.)
    path(
        "api/online-services/",
        api_views.api_online_services,
        name="api_online_services"
    ),
    path(
        "api/service-catalogue/",
        api_views.api_service_catalogue,
        name="api_service_catalogue"
    ),
    path(
        "api/service/<int:service_id>/",
        api_views.api_service_detail,
        name="api_service_detail"
    ),
    path(
        "api/service-by-key/<str:service_key>/",
        api_views.api_service_by_key,
        name="api_service_by_key"
    ),
    path(
        "api/metadata/",
        api_views.api_metadata,
        name="api_metadata"
    ),
]
