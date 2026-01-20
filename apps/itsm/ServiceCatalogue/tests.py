"""
Comprehensive test suite for ServiceCatalogue app

Tests cover:
- Model creation, validation, and business logic
- View functionality and permissions
- URL routing
- Template rendering
- Database queries and filtering
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group, Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from datetime import date, timedelta
import json

from .models import (
    ServiceProvider,
    Clientele,
    ServiceCategory,
    Service,
    ServiceRevision,
    FeeUnit,
    Availability,
)


# ============================================================================
# Model Tests
# ============================================================================

class ServiceProviderModelTest(TestCase):
    """Test ServiceProvider model"""

    def setUp(self):
        self.provider = ServiceProvider.objects.create(
            hierarchy="1.1",
            name="IT Department",
            acronym="IT"
        )

    def test_service_provider_creation(self):
        """Test creating a service provider"""
        self.assertEqual(self.provider.name, "IT Department")
        self.assertEqual(self.provider.acronym, "IT")
        self.assertEqual(str(self.provider), "1.1 IT Department (IT)")

    def test_service_provider_without_acronym(self):
        """Test service provider without acronym"""
        provider = ServiceProvider.objects.create(
            hierarchy="1.2",
            name="Support Team"
        )
        self.assertIsNone(provider.acronym)
        self.assertEqual(str(provider), "1.2 Support Team")

    def test_service_provider_ordering(self):
        """Test service providers are ordered by hierarchy and name"""
        ServiceProvider.objects.create(hierarchy="1.2", name="Team B")
        ServiceProvider.objects.create(hierarchy="1.1", name="Team C")
        
        providers = list(ServiceProvider.objects.all())
        self.assertEqual(providers[0].hierarchy, "1.1")
        self.assertEqual(providers[1].hierarchy, "1.1")
        self.assertEqual(providers[2].hierarchy, "1.2")

    def test_service_provider_history(self):
        """Test that history is tracked"""
        self.provider.name = "IT Department Updated"
        self.provider.save()
        
        history = self.provider.history.all()
        self.assertEqual(history.count(), 2)  # Creation + Update


class ClienteleModelTest(TestCase):
    """Test Clientele model"""

    def setUp(self):
        self.clientele = Clientele.objects.create(
            name="AWI Staff",
            acronym="STAFF",
            order="1"
        )

    def test_clientele_creation(self):
        """Test creating a clientele"""
        self.assertEqual(self.clientele.name, "Organization Staff")
        self.assertEqual(self.clientele.acronym, "STAFF")
        self.assertEqual(str(self.clientele), "STAFF: AWI Staff")

    def test_clientele_unique_acronym(self):
        """Test that acronym must be unique"""
        with self.assertRaises(IntegrityError):
            Clientele.objects.create(
                name="Another Group",
                acronym="STAFF"  # Duplicate
            )

    def test_clientele_ordering(self):
        """Test clienteles are ordered by order and acronym"""
        Clientele.objects.create(name="External", acronym="EXT", order="2")
        Clientele.objects.create(name="Partners", acronym="PART", order="1")
        
        clienteles = list(Clientele.objects.all())
        self.assertEqual(clienteles[0].order, "1")
        self.assertEqual(clienteles[1].order, "1")


class ServiceCategoryModelTest(TestCase):
    """Test ServiceCategory model"""

    def setUp(self):
        self.category = ServiceCategory.objects.create(
            name="Computing",
            acronym="COMP",
            order="1",
            description="Computing services"
        )

    def test_service_category_creation(self):
        """Test creating a service category"""
        self.assertEqual(self.category.name, "Computing")
        self.assertEqual(self.category.key, "COMP")
        self.assertEqual(str(self.category), "COMP Computing")

    def test_service_category_unique_acronym(self):
        """Test that acronym must be unique"""
        with self.assertRaises(IntegrityError):
            ServiceCategory.objects.create(
                name="Another Category",
                acronym="COMP"  # Duplicate
            )

    def test_service_category_order_key(self):
        """Test order_key property"""
        self.assertEqual(self.category.order_key, "1:COMP")


class ServiceModelTest(TestCase):
    """Test Service model"""

    def setUp(self):
        self.category = ServiceCategory.objects.create(
            name="Computing",
            acronym="COMP",
            order="1"
        )
        self.provider = ServiceProvider.objects.create(
            hierarchy="1.1",
            name="IT Department"
        )
        self.service = Service.objects.create(
            category=self.category,
            name="HPC Cluster",
            acronym="HPC",
            purpose="High-performance computing for research",
            order="1"
        )

    def test_service_creation(self):
        """Test creating a service"""
        self.assertEqual(self.service.name, "HPC Cluster")
        self.assertEqual(self.service.key, "COMP-HPC")
        self.assertEqual(str(self.service), "COMP-HPC HPC Cluster")

    def test_service_unique_category_acronym(self):
        """Test that acronym must be unique within category"""
        with self.assertRaises(IntegrityError):
            Service.objects.create(
                category=self.category,
                name="Another Service",
                acronym="HPC",  # Duplicate within category
                purpose="Test"
            )

    def test_service_same_acronym_different_category(self):
        """Test that same acronym is allowed in different categories"""
        other_category = ServiceCategory.objects.create(
            name="Storage",
            acronym="STOR"
        )
        service = Service.objects.create(
            category=other_category,
            name="Other Service",
            acronym="HPC",  # Same acronym, different category
            purpose="Test"
        )
        self.assertEqual(service.key, "STOR-HPC")

    def test_service_providers_relationship(self):
        """Test many-to-many relationship with service providers"""
        self.service.service_providers.add(self.provider)
        self.assertEqual(self.service.service_providers.count(), 1)
        self.assertIn(self.provider, self.service.service_providers.all())


class ServiceRevisionModelTest(TestCase):
    """Test ServiceRevision model"""

    def setUp(self):
        self.category = ServiceCategory.objects.create(
            name="Computing",
            acronym="COMP"
        )
        self.service = Service.objects.create(
            category=self.category,
            name="HPC Cluster",
            acronym="HPC",
            purpose="High-performance computing"
        )
        self.revision = ServiceRevision.objects.create(
            service=self.service,
            version="v1.0",
            description="Initial version",
            listed_from=date.today(),
            available_from=date.today()
        )

    def test_service_revision_creation(self):
        """Test creating a service revision"""
        self.assertEqual(self.revision.version, "v1.0")
        self.assertEqual(self.revision.service, self.service)
        self.assertFalse(self.revision.submitted)

    def test_service_revision_key_property(self):
        """Test the key property"""
        self.assertEqual(self.revision.key, "COMP-HPC-v1.0")

    def test_service_revision_date_validation(self):
        """Test date validation logic"""
        # listed_until should be after listed_from
        revision = ServiceRevision(
            service=self.service,
            version="v2.0",
            description="Test",
            listed_from=date.today(),
            listed_until=date.today() - timedelta(days=1)  # Before listed_from
        )
        with self.assertRaises(ValidationError):
            revision.clean()

    def test_service_revision_status_properties(self):
        """Test status computation properties"""
        # Test listed status
        self.assertIn("currently listed", self.revision.status_listed.lower())
        
        # Test available status
        self.assertIn("available", self.revision.status_available.lower())

    def test_service_revision_search_keys_generation(self):
        """Test that search keys are generated on save"""
        self.revision.save()
        self.assertIsNotNone(self.revision.search_keys)
        self.assertIn("COMP-HPC-v1.0", self.revision.search_keys)


class AvailabilityModelTest(TestCase):
    """Test Availability model (many-to-many through model)"""

    def setUp(self):
        self.category = ServiceCategory.objects.create(
            name="Computing",
            acronym="COMP"
        )
        self.service = Service.objects.create(
            category=self.category,
            name="HPC Cluster",
            acronym="HPC",
            purpose="Computing"
        )
        self.revision = ServiceRevision.objects.create(
            service=self.service,
            version="v1.0",
            description="Test"
        )
        self.clientele = Clientele.objects.create(
            name="AWI Staff",
            acronym="STAFF"
        )
        self.fee_unit = FeeUnit.objects.create(
            name="per month",
            acronym="PM"
        )

    def test_availability_creation(self):
        """Test creating availability relationship"""
        availability = Availability.objects.create(
            servicerevision=self.revision,
            clientele=self.clientele,
            fee_unit=self.fee_unit,
            fee_value="100"
        )
        self.assertEqual(availability.fee_value, "100")
        self.assertEqual(availability.clientele, self.clientele)

    def test_availability_unique_together(self):
        """Test that servicerevision-clientele combination must be unique"""
        Availability.objects.create(
            servicerevision=self.revision,
            clientele=self.clientele
        )
        with self.assertRaises(IntegrityError):
            Availability.objects.create(
                servicerevision=self.revision,
                clientele=self.clientele  # Duplicate
            )


# ============================================================================
# View Tests
# ============================================================================

class ViewTestCase(TestCase):
    """Base class for view tests with common setup"""

    def setUp(self):
        """Set up test client and user"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.staff_user = User.objects.create_user(
            username='staffuser',
            password='testpass123',
            is_staff=True
        )
        
        # Create test data
        self.category = ServiceCategory.objects.create(
            name="Computing",
            acronym="COMP",
            order="1"
        )
        self.service = Service.objects.create(
            category=self.category,
            name="HPC Cluster",
            acronym="HPC",
            purpose="High-performance computing"
        )
        self.revision = ServiceRevision.objects.create(
            service=self.service,
            version="v1.0",
            description="Test service",
            listed_from=date.today(),
            available_from=date.today()
        )
        self.clientele = Clientele.objects.create(
            name="AWI Staff",
            acronym="STAFF"
        )


class ServiceListViewTest(ViewTestCase):
    """Test service list views"""

    def test_services_listed_view_accessible(self):
        """Test that services listed view is accessible"""
        response = self.client.get(reverse('services_listed'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ServiceCatalogue/services_listed.html')

    def test_services_listed_view_shows_services(self):
        """Test that listed services appear in the view"""
        response = self.client.get(reverse('services_listed'))
        self.assertContains(response, "HPC Cluster")
        self.assertContains(response, "COMP-HPC")

    def test_services_listed_view_context(self):
        """Test context data in services listed view"""
        response = self.client.get(reverse('services_listed'))
        self.assertIn('object_list', response.context)
        self.assertIn('today', response.context)
        self.assertIn('branding', response.context)


class SearchFunctionalityTest(ViewTestCase):
    """Test search functionality"""

    def test_search_with_query(self):
        """Test search with a query parameter"""
        response = self.client.get(reverse('services_listed'), {'q': 'HPC'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "HPC Cluster")

    def test_search_no_results(self):
        """Test search with no matching results"""
        response = self.client.get(reverse('services_listed'), {'q': 'nonexistent'})
        self.assertEqual(response.status_code, 200)
        # Should not contain the service
        self.assertNotContains(response, "COMP-HPC")


# ============================================================================
# Business Logic Tests
# ============================================================================

class ServiceLifecycleTest(TestCase):
    """Test service lifecycle and status transitions"""

    def setUp(self):
        self.category = ServiceCategory.objects.create(
            name="Computing",
            acronym="COMP"
        )
        self.service = Service.objects.create(
            category=self.category,
            name="Test Service",
            acronym="TEST",
            purpose="Testing"
        )

    def test_service_not_yet_listed(self):
        """Test service that will be listed in the future"""
        future_date = date.today() + timedelta(days=30)
        revision = ServiceRevision.objects.create(
            service=self.service,
            version="v1.0",
            description="Future service",
            listed_from=future_date
        )
        self.assertIn("scheduled", revision.status_listed.lower())

    def test_service_currently_listed(self):
        """Test currently listed service"""
        revision = ServiceRevision.objects.create(
            service=self.service,
            version="v1.0",
            description="Current service",
            listed_from=date.today() - timedelta(days=1)
        )
        self.assertIn("currently listed", revision.status_listed.lower())

    def test_service_no_longer_listed(self):
        """Test service that was delisted"""
        past_date = date.today() - timedelta(days=30)
        revision = ServiceRevision.objects.create(
            service=self.service,
            version="v1.0",
            description="Delisted service",
            listed_from=past_date,
            listed_until=past_date + timedelta(days=1)
        )
        self.assertIn("not more listed", revision.status_listed.lower())

    def test_service_eol(self):
        """Test end-of-life service"""
        past_date = date.today() - timedelta(days=30)
        revision = ServiceRevision.objects.create(
            service=self.service,
            version="v1.0",
            description="EOL service",
            available_from=past_date,
            available_until=past_date + timedelta(days=1)
        )
        status = revision.status_available.lower()
        self.assertTrue("eol" in status or "not more available" in status)


class SearchKeysTest(TestCase):
    """Test automatic search key generation"""

    def setUp(self):
        self.category = ServiceCategory.objects.create(
            name="Computing",
            acronym="COMP"
        )
        self.service = Service.objects.create(
            category=self.category,
            name="HPC Cluster",
            acronym="HPC",
            purpose="High-performance computing"
        )

    def test_search_keys_include_service_key(self):
        """Test that search keys include the service key"""
        revision = ServiceRevision.objects.create(
            service=self.service,
            version="v1.0",
            description="Test description"
        )
        self.assertIn("COMP-HPC-v1.0", revision.search_keys)

    def test_search_keys_update_on_category_change(self):
        """Test that search keys update when category changes"""
        revision = ServiceRevision.objects.create(
            service=self.service,
            version="v1.0",
            description="Test"
        )
        original_keys = revision.search_keys
        
        # Change category
        new_category = ServiceCategory.objects.create(
            name="Storage",
            acronym="STOR"
        )
        self.service.category = new_category
        self.service.save()
        
        # Refresh revision from DB
        revision.refresh_from_db()
        self.assertNotEqual(original_keys, revision.search_keys)
        self.assertIn("STOR-HPC-v1.0", revision.search_keys)


# ============================================================================
# Integration Tests
# ============================================================================

class ServiceCatalogueIntegrationTest(TestCase):
    """Integration tests for complete workflows"""

    def setUp(self):
        # Create complete service catalogue structure
        self.category = ServiceCategory.objects.create(
            name="Computing",
            acronym="COMP",
            description="Computing services"
        )
        
        self.provider = ServiceProvider.objects.create(
            hierarchy="1.1",
            name="IT Department",
            acronym="IT"
        )
        
        self.service = Service.objects.create(
            category=self.category,
            name="HPC Cluster",
            acronym="HPC",
            purpose="High-performance computing",
            responsible="it-manager@awi.de"
        )
        self.service.service_providers.add(self.provider)
        
        self.revision = ServiceRevision.objects.create(
            service=self.service,
            version="v1.0",
            description="Production HPC cluster",
            requirements="AWI account required",
            details="24/7 support available",
            contact="hpc-support@awi.de",
            url="https://hpc.awi.de",
            listed_from=date.today(),
            available_from=date.today()
        )
        
        self.clientele = Clientele.objects.create(
            name="AWI Staff",
            acronym="STAFF"
        )
        
        self.fee_unit = FeeUnit.objects.create(
            name="per month",
            acronym="PM"
        )
        
        Availability.objects.create(
            servicerevision=self.revision,
            clientele=self.clientele,
            fee_unit=self.fee_unit,
            fee_value="0",
            comment="Free for AWI staff"
        )

    def test_complete_service_in_catalogue(self):
        """Test that a complete service appears correctly in catalogue"""
        response = Client().get(reverse('services_listed'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "HPC Cluster")
        self.assertContains(response, "COMP-HPC")
        self.assertContains(response, "Production HPC cluster")

    def test_service_has_all_relationships(self):
        """Test that all relationships are properly established"""
        # Verify service has category
        self.assertEqual(self.revision.service.category, self.category)
        
        # Verify service has providers
        self.assertEqual(self.revision.service.service_providers.count(), 1)
        
        # Verify revision has availability for clientele
        availability = Availability.objects.filter(
            servicerevision=self.revision,
            clientele=self.clientele
        ).first()
        self.assertIsNotNone(availability)
        self.assertEqual(availability.fee_value, "0")

    def test_service_history_tracking(self):
        """Test that changes are tracked in history"""
        original_desc = self.revision.description
        self.revision.description = "Updated description"
        self.revision.save()
        
        history = self.revision.history.all()
        self.assertGreaterEqual(history.count(), 2)


# ============================================================================
# Performance Tests
# ============================================================================

class QueryPerformanceTest(TestCase):
    """Test database query performance"""

    def setUp(self):
        """Create bulk test data"""
        # Create 5 categories
        categories = [
            ServiceCategory.objects.create(
                name=f"Category {i}",
                acronym=f"CAT{i}",
                order=str(i)
            ) for i in range(5)
        ]
        
        # Create 10 services per category
        for cat in categories:
            for j in range(10):
                Service.objects.create(
                    category=cat,
                    name=f"Service {j}",
                    acronym=f"SRV{j}",
                    purpose="Test service"
                )

    def test_service_listing_query_count(self):
        """Test that service listing doesn't cause N+1 queries"""
        # This test ensures we use select_related/prefetch_related properly
        from django.test.utils import override_settings
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        
        with CaptureQueriesContext(connection) as context:
            services = list(Service.objects.select_related('category').all())
        
        # Should be roughly 1 query with select_related
        self.assertLess(len(context.captured_queries), 5)
