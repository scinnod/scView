"""ITSM Service Catalogue URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include, reverse
from django.contrib.auth import views as auth_views
from ServiceCatalogue.views import sso_login, logout_view

urlpatterns = [
    path('sso-login/', sso_login, name='sso_login'),  # SSO login endpoint for Keycloak
    path('sso-logout/', logout_view, name='sso_logout'),  # Unified logout for production and development
    path('', lambda request: redirect(reverse("index"), permanent=False)),
    ]

urlpatterns += i18n_patterns(
    path('sc/', include('ServiceCatalogue.urls')),
    path('admin/', admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
)
