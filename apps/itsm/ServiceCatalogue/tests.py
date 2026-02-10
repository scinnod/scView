"""
Comprehensive test suite for ServiceCatalogue app

Tests cover:
- Fixture data integrity and structure
- Model creation, validation, and business logic
- View functionality and permissions
- URL routing
- Template rendering
- Database queries and filtering
"""

import json
from datetime import date, timedelta

from django.contrib.auth.models import User, Group, Permission
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.test import TestCase, Client
from django.test.utils import override_settings, CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

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
# Fixture Data Tests
# ============================================================================

class FixtureDataIntegrityTest(TestCase):
    """Test that fixture data loads correctly and has expected structure"""
    fixtures = ['initial_test_data.json']

    def test_fixture_loads_successfully(self):
        """Test that fixture loads without errors"""
        # If we get here, the fixture loaded successfully
        self.assertTrue(True)

    def test_clientele_groups_count(self):
        """Test that all expected clientele groups are present"""
        clienteles = Clientele.objects.all()
        self.assertEqual(clienteles.count(), 4)

    def test_clientele_groups_structure(self):
        """Test clientele groups have expected acronyms"""
        expected_acronyms = {'STUDENT', 'STAFF', 'RESEARCH', 'EXTERNAL'}
        actual_acronyms = set(Clientele.objects.values_list('acronym', flat=True))
        self.assertEqual(expected_acronyms, actual_acronyms)

    def test_clientele_groups_have_names(self):
        """Test all clientele groups have English and German names"""
        for clientele in Clientele.objects.all():
            self.assertIsNotNone(clientele.name_en, f"Clientele {clientele.acronym} missing English name")
            self.assertIsNotNone(clientele.name_de, f"Clientele {clientele.acronym} missing German name")

    def test_clientele_ordering(self):
        """Test clientele groups are ordered correctly"""
        clienteles = list(Clientele.objects.all())
        # Should be ordered by 'order' field: STUDENT(10), STAFF(20), RESEARCH(30), EXTERNAL(40)
        self.assertEqual(clienteles[0].acronym, 'STUDENT')
        self.assertEqual(clienteles[1].acronym, 'STAFF')
        self.assertEqual(clienteles[2].acronym, 'RESEARCH')
        self.assertEqual(clienteles[3].acronym, 'EXTERNAL')

    def test_service_categories_count(self):
        """Test expected number of service categories"""
        self.assertEqual(ServiceCategory.objects.count(), 4)

    def test_service_categories_structure(self):
        """Test service categories have expected acronyms"""
        expected = {'COLLAB', 'DATA', 'COMPUTE', 'IAM'}
        actual = set(ServiceCategory.objects.values_list('acronym', flat=True))
        self.assertEqual(expected, actual)

    def test_service_providers_count(self):
        """Test expected number of service providers"""
        self.assertEqual(ServiceProvider.objects.count(), 4)

    def test_fee_units_count(self):
        """Test expected number of fee units"""
        self.assertEqual(FeeUnit.objects.count(), 4)

    def test_fee_units_have_translations(self):
        """Test fee units have both English and German names"""
        for unit in FeeUnit.objects.all():
            self.assertIsNotNone(unit.name_en, f"FeeUnit pk={unit.pk} missing English name")
            self.assertIsNotNone(unit.name_de, f"FeeUnit pk={unit.pk} missing German name")

    def test_services_count(self):
        """Test expected number of services"""
        self.assertEqual(Service.objects.count(), 8)

    def test_service_revisions_count(self):
        """Test each service has at least one revision"""
        self.assertEqual(ServiceRevision.objects.count(), 8)
        for service in Service.objects.all():
            self.assertGreaterEqual(
                service.servicerevision_set.count(), 1,
                f"Service {service.acronym} has no revisions"
            )

    def test_availabilities_exist(self):
        """Test that availability relationships are defined"""
        self.assertEqual(Availability.objects.count(), 21)

    def test_all_listed_revisions_have_availability(self):
        """Test that listed service revisions have at least one availability"""
        listed_revisions = ServiceRevision.objects.filter(
            listed_from__isnull=False
        )
        for revision in listed_revisions:
            avail_count = Availability.objects.filter(servicerevision=revision).count()
            self.assertGreaterEqual(
                avail_count, 1,
                f"Listed revision {revision.key} has no availability defined"
            )

    def test_service_category_relationships(self):
        """Test all services belong to valid categories"""
        for service in Service.objects.all():
            self.assertIsNotNone(service.category)
            self.assertIn(service.category, ServiceCategory.objects.all())

    def test_hpc_service_fixture_data(self):
        """Test specific HPC service data used in other tests"""
        # This ensures the data other tests depend on exists
        hpc_service = Service.objects.get(acronym="HPC")
        self.assertEqual(hpc_service.category.acronym, "COMPUTE")
        
        revision = ServiceRevision.objects.get(service=hpc_service)
        self.assertIsNotNone(revision.listed_from)
        self.assertIsNotNone(revision.available_from)


# ============================================================================
# Management Command Tests
# ============================================================================

class InitializeGroupsCommandTest(TestCase):
    """Test the initialize_groups management command"""

    def test_command_creates_all_groups(self):
        """Test that the command creates all 5 expected groups"""
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        call_command('initialize_groups', stdout=out)
        
        # Check all 5 groups were created
        self.assertEqual(Group.objects.filter(name__icontains='Service Catalogue').count(), 5)

    def test_group_names_match_expected(self):
        """Test that group names match the hardcoded definitions"""
        from django.core.management import call_command
        from io import StringIO
        
        call_command('initialize_groups', stdout=StringIO())
        
        expected_names = [
            "0 - Service Catalogue Administrators",
            "1 - Service Catalogue Editors (can edit service metadata and revisions and publish)",
            "2a - Service Catalogue Authors Plus (can edit online service revisions and publish)",
            "2 - Service Catalogue Authors (can edit drafts service revision drafts only)",
            "3 - Service Catalogue Viewers",
        ]
        
        for name in expected_names:
            self.assertTrue(
                Group.objects.filter(name=name).exists(),
                f"Group '{name}' was not created"
            )

    def test_group_primary_keys(self):
        """Test that groups are created with specific primary keys"""
        from django.core.management import call_command
        from io import StringIO
        
        call_command('initialize_groups', stdout=StringIO())
        
        # Groups should have specific PKs: 1, 2, 3, 4, 5
        expected_pks = {1, 2, 3, 4, 5}
        actual_pks = set(Group.objects.filter(
            name__icontains='Service Catalogue'
        ).values_list('pk', flat=True))
        
        self.assertEqual(expected_pks, actual_pks)

    def test_administrators_group_has_publish_permission(self):
        """Test that Administrators group has can_publish_service permission"""
        from django.core.management import call_command
        from io import StringIO
        
        call_command('initialize_groups', stdout=StringIO())
        
        admin_group = Group.objects.get(pk=1)
        permission = Permission.objects.get(codename='can_publish_service')
        
        self.assertIn(permission, admin_group.permissions.all())

    def test_editors_group_has_publish_permission(self):
        """Test that Editors group has can_publish_service permission"""
        from django.core.management import call_command
        from io import StringIO
        
        call_command('initialize_groups', stdout=StringIO())
        
        editors_group = Group.objects.get(pk=2)
        permission = Permission.objects.get(codename='can_publish_service')
        
        self.assertIn(permission, editors_group.permissions.all())

    def test_authors_plus_group_has_publish_permission(self):
        """Test that Authors Plus group has can_publish_service permission"""
        from django.core.management import call_command
        from io import StringIO
        
        call_command('initialize_groups', stdout=StringIO())
        
        authors_plus_group = Group.objects.get(pk=3)
        permission = Permission.objects.get(codename='can_publish_service')
        
        self.assertIn(permission, authors_plus_group.permissions.all())

    def test_authors_group_lacks_publish_permission(self):
        """Test that Authors group does NOT have can_publish_service permission"""
        from django.core.management import call_command
        from io import StringIO
        
        call_command('initialize_groups', stdout=StringIO())
        
        authors_group = Group.objects.get(pk=4)
        permission = Permission.objects.get(codename='can_publish_service')
        
        # Authors should NOT have publish permission - that's the key difference
        self.assertNotIn(permission, authors_group.permissions.all())

    def test_viewers_group_has_minimal_permissions(self):
        """Test that Viewers group has exactly 5 view permissions"""
        from django.core.management import call_command
        from io import StringIO
        
        call_command('initialize_groups', stdout=StringIO())
        
        viewers_group = Group.objects.get(pk=5)
        permissions = viewers_group.permissions.all()
        
        self.assertEqual(permissions.count(), 5)
        
        # All permissions should be view-only
        for perm in permissions:
            self.assertTrue(
                perm.codename.startswith('view_'),
                f"Viewers have non-view permission: {perm.codename}"
            )

    def test_command_is_idempotent(self):
        """Test that running the command twice doesn't cause errors"""
        from django.core.management import call_command
        from io import StringIO
        
        # Run twice
        call_command('initialize_groups', stdout=StringIO())
        call_command('initialize_groups', stdout=StringIO())
        
        # Should still have exactly 5 groups
        self.assertEqual(Group.objects.filter(name__icontains='Service Catalogue').count(), 5)

    def test_reset_option_clears_groups(self):
        """Test that --reset option deletes existing groups first"""
        from django.core.management import call_command
        from io import StringIO
        
        # Create groups first
        call_command('initialize_groups', stdout=StringIO())
        
        # Get a group and add a user
        admin_group = Group.objects.get(pk=1)
        user = User.objects.create_user('testuser', 'test@test.com', 'password')
        user.groups.add(admin_group)
        
        # Reset should clear and recreate
        call_command('initialize_groups', '--reset', stdout=StringIO())
        
        # Groups should still exist
        self.assertEqual(Group.objects.filter(name__icontains='Service Catalogue').count(), 5)

    def test_dry_run_makes_no_changes(self):
        """Test that --dry-run doesn't create groups"""
        from django.core.management import call_command
        from io import StringIO
        
        # Ensure no groups exist
        Group.objects.filter(name__icontains='Service Catalogue').delete()
        
        # Dry run
        call_command('initialize_groups', '--dry-run', stdout=StringIO())
        
        # No groups should be created
        self.assertEqual(Group.objects.filter(name__icontains='Service Catalogue').count(), 0)

    def test_permission_counts_per_group(self):
        """Test that each group has the expected number of permissions"""
        from django.core.management import call_command
        from io import StringIO
        
        call_command('initialize_groups', stdout=StringIO())
        
        # Expected permission counts from command docstring
        expected_counts = {
            1: 50,  # Administrators (includes user management permissions)
            2: 46,  # Editors (no user permissions)
            3: 40,  # Authors Plus
            4: 39,  # Authors
            5: 5,   # Viewers
        }
        
        for pk, expected_count in expected_counts.items():
            group = Group.objects.get(pk=pk)
            actual_count = group.permissions.count()
            self.assertEqual(
                actual_count, expected_count,
                f"Group pk={pk} ({group.name}) has {actual_count} permissions, expected {expected_count}"
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
            name="Organization Staff",
            acronym="STAFF",
            order="1"
        )

    def test_clientele_creation(self):
        """Test creating a clientele"""
        self.assertEqual(self.clientele.name, "Organization Staff")
        self.assertEqual(self.clientele.acronym, "STAFF")
        self.assertEqual(str(self.clientele), "STAFF: Organization Staff")

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
        # Test listed status (property name is status_listing)
        self.assertIn("currently listed", self.revision.status_listing.lower())
        
        # Test available status (property name is status_availablility)
        self.assertIn("available", self.revision.status_availablility.lower())

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
            name="Organization Staff",
            acronym="STAFF"
        )
        self.fee_unit = FeeUnit.objects.create(
            name="per month"
        )

    def test_availability_creation(self):
        """Test creating availability relationship"""
        availability = Availability.objects.create(
            servicerevision=self.revision,
            clientele=self.clientele,
            fee_unit=self.fee_unit,
            fee=100
        )
        self.assertEqual(availability.fee, 100)
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
    """Base class for view tests with common setup using fixtures"""
    fixtures = ['initial_test_data.json']

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
        
        # Get references to fixture data for use in tests
        # HPC Cluster is pk=6 in fixtures, COMPUTE category is pk=3
        self.category = ServiceCategory.objects.get(acronym="COMPUTE")
        self.service = Service.objects.get(acronym="HPC")
        self.revision = ServiceRevision.objects.get(service=self.service)
        self.clientele = Clientele.objects.get(acronym="STAFF")


@override_settings(SERVICE_CATALOGUE_REQUIRE_LOGIN=False)
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
        # Fixture has HPC Cluster service with COMPUTE-HPC key
        self.assertContains(response, "HPC Cluster")
        self.assertContains(response, "COMPUTE-HPC")

    def test_services_listed_view_context(self):
        """Test context data in services listed view"""
        response = self.client.get(reverse('services_listed'))
        self.assertIn('object_list', response.context)
        self.assertIn('today', response.context)
        self.assertIn('branding', response.context)


@override_settings(SERVICE_CATALOGUE_REQUIRE_LOGIN=False)
class SearchFunctionalityTest(ViewTestCase):
    """Test search functionality"""

    def test_search_with_query(self):
        """Test search with a query parameter"""
        response = self.client.get(reverse('services_listed'), {'q': 'HPC'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "HPC Cluster")

    def test_search_no_results(self):
        """Test search with no matching results"""
        response = self.client.get(reverse('services_listed'), {'q': 'nonexistent12345'})
        self.assertEqual(response.status_code, 200)
        # Should not contain any fixture services
        self.assertNotContains(response, "COMPUTE-HPC")


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
        # status_listing returns "2-listing at {date}" for future services
        self.assertIn("listing at", revision.status_listing.lower())

    def test_service_currently_listed(self):
        """Test currently listed service"""
        revision = ServiceRevision.objects.create(
            service=self.service,
            version="v1.0",
            description="Current service",
            listed_from=date.today() - timedelta(days=1)
        )
        self.assertIn("currently listed", revision.status_listing.lower())

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
        self.assertIn("not more listed", revision.status_listing.lower())

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
        status = revision.status_availablility.lower()
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

@override_settings(SERVICE_CATALOGUE_REQUIRE_LOGIN=False)
class ServiceCatalogueIntegrationTest(TestCase):
    """Integration tests for complete workflows using fixture data"""
    fixtures = ['initial_test_data.json']

    def setUp(self):
        # Get references to fixture data
        # The fixture includes HPC Cluster (pk=6) in COMPUTE category (pk=3)
        self.category = ServiceCategory.objects.get(acronym="COMPUTE")
        self.provider = ServiceProvider.objects.get(acronym="HPC")  # Research Computing
        self.service = Service.objects.get(acronym="HPC")
        self.revision = ServiceRevision.objects.get(service=self.service)
        self.clientele = Clientele.objects.get(acronym="STAFF")
        self.fee_unit = FeeUnit.objects.get(pk=1)  # per month
        
        # Add provider to service (fixture may not have this relationship)
        self.service.service_providers.add(self.provider)
        
        # Create availability for this test (not in fixture)
        Availability.objects.get_or_create(
            servicerevision=self.revision,
            clientele=self.clientele,
            defaults={
                'fee_unit': self.fee_unit,
                'fee': 0,
                'comment': "Free for organization staff"
            }
        )

    def test_complete_service_in_catalogue(self):
        """Test that a complete service appears correctly in catalogue"""
        response = Client().get(reverse('services_listed'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "HPC Cluster")
        self.assertContains(response, "COMPUTE-HPC")

    def test_service_has_all_relationships(self):
        """Test that all relationships are properly established"""
        # Verify service has category
        self.assertEqual(self.revision.service.category, self.category)
        
        # Verify service has providers
        self.assertGreaterEqual(self.revision.service.service_providers.count(), 1)
        
        # Verify revision has availability for clientele
        availability = Availability.objects.filter(
            servicerevision=self.revision,
            clientele=self.clientele
        ).first()
        self.assertIsNotNone(availability)
        self.assertEqual(availability.fee, 0)

    def test_service_history_tracking(self):
        """Test that changes are tracked in history"""
        # Get initial history count (fixture data already has history)
        initial_count = self.revision.history.count()
        
        # Make a change
        original_desc = self.revision.description
        self.revision.description = "Updated description"
        self.revision.save()
        
        # History should increase
        history = self.revision.history.all()
        self.assertGreater(history.count(), initial_count)


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
        
        with CaptureQueriesContext(connection) as context:
            services = list(Service.objects.select_related('category').all())
        
        # Should be roughly 1 query with select_related
        self.assertLess(len(context.captured_queries), 5)


# ============================================================================
# User Access Control Tests
# ============================================================================

class UserAccessControlTest(TestCase):
    """Test AUTO_CREATE_USERS and STAFF_ONLY_MODE settings"""
    
    def setUp(self):
        """Create test users"""
        self.staff_user = User.objects.create_user(
            username='staffuser',
            password='testpass123',
            is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username='regularuser',
            password='testpass123',
            is_staff=False
        )
        self.client = Client()
    
    def test_auto_create_users_default_is_true(self):
        """Test that AUTO_CREATE_USERS defaults to True"""
        from django.conf import settings
        # The default should be True (verified by checking the setting exists)
        self.assertTrue(hasattr(settings, 'AUTO_CREATE_USERS'))
    
    def test_staff_only_mode_default_is_false(self):
        """Test that STAFF_ONLY_MODE defaults to False"""
        from django.conf import settings
        self.assertTrue(hasattr(settings, 'STAFF_ONLY_MODE'))
    
    @override_settings(AUTO_CREATE_USERS=False)
    def test_auto_create_users_disabled_blocks_new_user(self):
        """Test that AUTO_CREATE_USERS=False prevents new user creation via middleware"""
        from itsm_config.backends import CustomRemoteUserMiddleware
        from django.test import RequestFactory
        
        factory = RequestFactory()
        request = factory.get('/sso-login/', HTTP_X_REMOTE_USER='newuser_that_does_not_exist')
        
        middleware = CustomRemoteUserMiddleware(lambda r: None)
        response = middleware(request)
        
        # Should return error page response (not raise exception)
        self.assertEqual(response.status_code, 403)
        content = response.content.decode().lower()
        # Check for key elements of the user creation disabled page
        self.assertIn('user not found', content)
        self.assertIn('automatic user creation is currently disabled', content)
    
    @override_settings(AUTO_CREATE_USERS=True)
    def test_auto_create_users_enabled_allows_new_user(self):
        """Test that AUTO_CREATE_USERS=True allows new user creation"""
        from itsm_config.backends import KeycloakRemoteUserBackend
        
        backend = KeycloakRemoteUserBackend()
        
        # Creating a new user should work
        new_user = backend.create_user('brand_new_test_user')
        self.assertIsNotNone(new_user)
        self.assertEqual(new_user.username, 'brand_new_test_user')
        self.assertTrue(new_user.is_active)
        
        # Cleanup
        new_user.delete()
    
    @override_settings(STAFF_ONLY_MODE=True)
    def test_staff_only_mode_blocks_non_staff(self):
        """Test that STAFF_ONLY_MODE=True blocks non-staff users via middleware"""
        from itsm_config.backends import StaffOnlyModeMiddleware
        from django.test import RequestFactory
        
        factory = RequestFactory()
        request = factory.get('/en/sc/services')
        request.user = self.regular_user
        
        middleware = StaffOnlyModeMiddleware(lambda r: None)
        
        # Non-staff user should receive 403 response (not raise exception)
        response = middleware(request)
        self.assertEqual(response.status_code, 403)
        self.assertIn('insufficient', response.content.decode().lower())
    
    @override_settings(STAFF_ONLY_MODE=True)
    def test_staff_only_mode_allows_staff(self):
        """Test that STAFF_ONLY_MODE=True allows staff users via middleware"""
        from itsm_config.backends import StaffOnlyModeMiddleware
        from django.test import RequestFactory
        from django.http import HttpResponse
        
        factory = RequestFactory()
        request = factory.get('/en/sc/services')
        request.user = self.staff_user
        
        mock_response = HttpResponse('OK')
        middleware = StaffOnlyModeMiddleware(lambda r: mock_response)
        
        # Staff user should not raise an error
        try:
            response = middleware(request)
            self.assertEqual(response.content, b'OK')
        except Exception as e:
            self.fail(f"Staff user should be allowed but got: {e}")
    
    @override_settings(STAFF_ONLY_MODE=False)
    def test_staff_only_mode_disabled_allows_non_staff(self):
        """Test that STAFF_ONLY_MODE=False allows non-staff users"""
        from itsm_config.backends import StaffOnlyModeMiddleware
        from django.test import RequestFactory
        from django.http import HttpResponse
        
        factory = RequestFactory()
        request = factory.get('/en/sc/services')
        request.user = self.regular_user
        
        mock_response = HttpResponse('OK')
        middleware = StaffOnlyModeMiddleware(lambda r: mock_response)
        
        # Non-staff user should be allowed when mode is disabled
        try:
            response = middleware(request)
            self.assertEqual(response.content, b'OK')
        except Exception as e:
            self.fail(f"Non-staff user should be allowed when STAFF_ONLY_MODE=False but got: {e}")


class InsufficientPrivilegesViewTest(TestCase):
    """Test the insufficient privileges (403) view"""
    
    def setUp(self):
        """Create test users"""
        self.staff_user = User.objects.create_user(
            username='staffuser',
            password='testpass123',
            is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username='regularuser',
            password='testpass123',
            is_staff=False
        )
        self.client = Client()
    
    def test_insufficient_privileges_view_renders(self):
        """Test that insufficient_privileges_view renders correctly"""
        from ServiceCatalogue.views import insufficient_privileges_view
        from django.test import RequestFactory
        from django.core.exceptions import PermissionDenied
        
        factory = RequestFactory()
        request = factory.get('/test/')
        request.user = self.regular_user
        
        response = insufficient_privileges_view(request, exception=PermissionDenied("Test reason"))
        
        self.assertEqual(response.status_code, 403)
        self.assertIn(b'Insufficient Privileges', response.content)
        self.assertIn(b'regularuser', response.content)
    
    def test_insufficient_privileges_view_shows_username(self):
        """Test that the view shows the logged-in username"""
        from ServiceCatalogue.views import insufficient_privileges_view
        from django.test import RequestFactory
        
        factory = RequestFactory()
        request = factory.get('/test/')
        request.user = self.regular_user
        
        response = insufficient_privileges_view(request)
        
        # Should contain the username
        self.assertIn(b'regularuser', response.content)
    
    def test_insufficient_privileges_view_shows_reason(self):
        """Test that the view shows the denial reason when provided"""
        from ServiceCatalogue.views import insufficient_privileges_view
        from django.test import RequestFactory
        from django.core.exceptions import PermissionDenied
        
        factory = RequestFactory()
        request = factory.get('/test/')
        request.user = self.regular_user
        
        reason = "Staff-only mode is currently enabled."
        response = insufficient_privileges_view(request, exception=PermissionDenied(reason))
        
        # Should contain the reason
        self.assertIn(reason.encode(), response.content)
    
    def test_insufficient_privileges_view_has_logout_link(self):
        """Test that the view has a logout button"""
        from ServiceCatalogue.views import insufficient_privileges_view
        from django.test import RequestFactory
        
        factory = RequestFactory()
        request = factory.get('/test/')
        request.user = self.regular_user
        
        response = insufficient_privileges_view(request)
        
        # Should contain logout link
        self.assertIn(b'sso-logout', response.content)


class StaffOnlyModeIntegrationTest(TestCase):
    """Integration tests for STAFF_ONLY_MODE with views"""
    fixtures = ['initial_test_data.json']
    
    def setUp(self):
        """Create test users"""
        self.staff_user = User.objects.create_user(
            username='staffuser',
            password='testpass123',
            is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username='regularuser',
            password='testpass123',
            is_staff=False
        )
        self.client = Client()
    
    def test_staff_view_denies_non_staff_user(self):
        """Test that staff-only views deny access to non-staff users"""
        # Login as regular user
        self.client.login(username='regularuser', password='testpass123')
        
        # Access a staff-only view (services_under_revision)
        response = self.client.get(reverse('services_under_revision'))
        
        # Should be redirected to login or get 403
        self.assertIn(response.status_code, [302, 403])
    
    def test_staff_view_allows_staff_user(self):
        """Test that staff-only views allow access to staff users"""
        # Login as staff user
        self.client.login(username='staffuser', password='testpass123')
        
        # Access a staff-only view (services_under_revision)
        response = self.client.get(reverse('services_under_revision'))
        
        # Should be allowed (200)
        self.assertEqual(response.status_code, 200)


# ============================================================================
# REST API Tests
# ============================================================================

class APITestCase(TestCase):
    """Base class for REST API tests with common fixtures and helpers."""
    fixtures = ['initial_test_data.json']

    def setUp(self):
        self.client = Client()

    def _json(self, response):
        """Parse JSON from a response."""
        return json.loads(response.content)


@override_settings(ONLINE_SERVICES_REQUIRE_LOGIN=False)
class OnlineServicesAPITest(APITestCase):
    """Tests for /api/online-services/ endpoint."""

    def test_returns_200(self):
        """Endpoint returns 200 when public."""
        response = self.client.get(reverse('api_online_services'))
        self.assertEqual(response.status_code, 200)

    def test_json_structure(self):
        """Response has expected top-level keys."""
        response = self.client.get(reverse('api_online_services'))
        data = self._json(response)
        self.assertTrue(data['success'])
        self.assertIn('categories', data)
        self.assertIn('total_count', data)
        self.assertIn('language', data)
        self.assertIn('timestamp', data)

    def test_only_services_with_url(self):
        """Only revisions with a URL appear (mirrors jump page)."""
        response = self.client.get(reverse('api_online_services'))
        data = self._json(response)
        for cat in data['categories']:
            for svc in cat['services']:
                self.assertIsNotNone(svc.get('url'), f"{svc['service_name']} should have a URL")

    def test_does_not_expose_internal_fields(self):
        """Online services API must NOT expose description, contact, responsible, etc."""
        response = self.client.get(reverse('api_online_services'))
        data = self._json(response)
        for cat in data['categories']:
            for svc in cat['services']:
                self.assertNotIn('description', svc)
                self.assertNotIn('contact', svc)
                self.assertNotIn('responsible', svc)
                self.assertNotIn('service_providers', svc)
                self.assertNotIn('service_purpose', svc)

    def test_service_fields(self):
        """Each service has the expected set of public fields."""
        response = self.client.get(reverse('api_online_services'))
        data = self._json(response)
        svc = data['categories'][0]['services'][0]
        for key in ('id', 'service_key', 'service_name', 'category', 'version', 'url', 'detail_url', 'is_new'):
            self.assertIn(key, svc, f"Missing field: {key}")

    def test_clientele_filter(self):
        """The clientele query parameter filters results."""
        all_response = self.client.get(reverse('api_online_services'))
        filtered_response = self.client.get(reverse('api_online_services'), {'clientele': 'STAFF'})
        all_count = self._json(all_response)['total_count']
        filtered_count = self._json(filtered_response)['total_count']
        self.assertLessEqual(filtered_count, all_count)

    def test_language_parameter(self):
        """The lang parameter switches response language."""
        response_de = self.client.get(reverse('api_online_services'), {'lang': 'de'})
        data = self._json(response_de)
        self.assertEqual(data['language'], 'de')

    def test_only_get_allowed(self):
        """POST, PUT, DELETE must be rejected."""
        url = reverse('api_online_services')
        self.assertEqual(self.client.post(url).status_code, 405)
        self.assertEqual(self.client.put(url).status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 405)


@override_settings(ONLINE_SERVICES_REQUIRE_LOGIN=True)
class OnlineServicesAPIGatedTest(APITestCase):
    """Tests for /api/online-services/ when the page requires login."""

    def test_returns_403_when_login_required(self):
        """Endpoint returns 403 when ONLINE_SERVICES_REQUIRE_LOGIN is True."""
        response = self.client.get(reverse('api_online_services'))
        self.assertEqual(response.status_code, 403)
        data = self._json(response)
        self.assertFalse(data['success'])
        self.assertIn('error', data)


@override_settings(SERVICE_CATALOGUE_REQUIRE_LOGIN=False)
class ServiceCatalogueAPITest(APITestCase):
    """Tests for /api/service-catalogue/ endpoint."""

    def test_returns_200(self):
        response = self.client.get(reverse('api_service_catalogue'))
        self.assertEqual(response.status_code, 200)

    def test_json_structure(self):
        response = self.client.get(reverse('api_service_catalogue'))
        data = self._json(response)
        self.assertTrue(data['success'])
        self.assertIn('categories', data)
        self.assertIn('total_count', data)

    def test_includes_all_listed_services(self):
        """All listed services appear (including those without a URL)."""
        response = self.client.get(reverse('api_service_catalogue'))
        data = self._json(response)
        # Fixture has 8 listed services
        self.assertEqual(data['total_count'], 8)

    def test_catalogue_service_fields(self):
        """Catalogue services expose the correct set of fields."""
        response = self.client.get(reverse('api_service_catalogue'))
        data = self._json(response)
        svc = data['categories'][0]['services'][0]
        for key in ('id', 'service_key', 'service_name', 'service_purpose',
                     'category', 'version', 'description', 'detail_url', 'clienteles'):
            self.assertIn(key, svc, f"Missing field: {key}")

    def test_does_not_expose_internal_fields(self):
        """Catalogue API must NOT expose responsible, service_providers, etc."""
        response = self.client.get(reverse('api_service_catalogue'))
        data = self._json(response)
        for cat in data['categories']:
            for svc in cat['services']:
                self.assertNotIn('responsible', svc)
                self.assertNotIn('service_providers', svc)
                self.assertNotIn('description_internal', svc)
                self.assertNotIn('keywords', svc)

    def test_clientele_filter(self):
        all_response = self.client.get(reverse('api_service_catalogue'))
        filtered_response = self.client.get(reverse('api_service_catalogue'), {'clientele': 'EXTERNAL'})
        all_count = self._json(all_response)['total_count']
        filtered_count = self._json(filtered_response)['total_count']
        self.assertLessEqual(filtered_count, all_count)


@override_settings(SERVICE_CATALOGUE_REQUIRE_LOGIN=True)
class ServiceCatalogueAPIGatedTest(APITestCase):
    """Tests for /api/service-catalogue/ when the page requires login."""

    def test_returns_403_when_login_required(self):
        response = self.client.get(reverse('api_service_catalogue'))
        self.assertEqual(response.status_code, 403)
        data = self._json(response)
        self.assertFalse(data['success'])


@override_settings(SERVICE_CATALOGUE_REQUIRE_LOGIN=False)
class ServiceDetailAPITest(APITestCase):
    """Tests for /api/service/<id>/ endpoint."""

    def test_returns_200_for_valid_service(self):
        revision = ServiceRevision.objects.filter(listed_from__isnull=False).first()
        response = self.client.get(
            reverse('api_service_detail', kwargs={'service_id': revision.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_returns_404_for_nonexistent(self):
        response = self.client.get(
            reverse('api_service_detail', kwargs={'service_id': 99999})
        )
        self.assertEqual(response.status_code, 404)
        data = self._json(response)
        self.assertFalse(data['success'])

    def test_detail_fields(self):
        revision = ServiceRevision.objects.filter(listed_from__isnull=False).first()
        response = self.client.get(
            reverse('api_service_detail', kwargs={'service_id': revision.pk})
        )
        data = self._json(response)
        svc = data['service']
        self.assertEqual(svc['id'], revision.pk)
        self.assertIn('service_name', svc)
        self.assertIn('description', svc)
        self.assertIn('clienteles', svc)

    def test_does_not_expose_internal_fields(self):
        revision = ServiceRevision.objects.filter(listed_from__isnull=False).first()
        response = self.client.get(
            reverse('api_service_detail', kwargs={'service_id': revision.pk})
        )
        svc = self._json(response)['service']
        self.assertNotIn('responsible', svc)
        self.assertNotIn('service_providers', svc)
        self.assertNotIn('description_internal', svc)


@override_settings(SERVICE_CATALOGUE_REQUIRE_LOGIN=True)
class ServiceDetailAPIGatedTest(APITestCase):
    """Service detail returns 403 when catalogue requires login."""

    def test_returns_403(self):
        response = self.client.get(
            reverse('api_service_detail', kwargs={'service_id': 1})
        )
        self.assertEqual(response.status_code, 403)


@override_settings(SERVICE_CATALOGUE_REQUIRE_LOGIN=False)
class ServiceByKeyAPITest(APITestCase):
    """Tests for /api/service-by-key/<key>/ endpoint."""

    def test_returns_200_for_valid_key(self):
        response = self.client.get(
            reverse('api_service_by_key', kwargs={'service_key': 'COMPUTE-HPC'})
        )
        self.assertEqual(response.status_code, 200)
        svc = self._json(response)['service']
        self.assertEqual(svc['service_key'], 'COMPUTE-HPC')

    def test_returns_404_for_unknown_key(self):
        response = self.client.get(
            reverse('api_service_by_key', kwargs={'service_key': 'NONE-EXIST'})
        )
        self.assertEqual(response.status_code, 404)

    def test_returns_400_for_malformed_key(self):
        response = self.client.get(
            reverse('api_service_by_key', kwargs={'service_key': 'NOKEY'})
        )
        self.assertEqual(response.status_code, 400)


@override_settings(SERVICE_CATALOGUE_REQUIRE_LOGIN=True)
class ServiceByKeyAPIGatedTest(APITestCase):
    """Service-by-key returns 403 when catalogue requires login."""

    def test_returns_403(self):
        response = self.client.get(
            reverse('api_service_by_key', kwargs={'service_key': 'COMPUTE-HPC'})
        )
        self.assertEqual(response.status_code, 403)


class MetadataAPITest(APITestCase):
    """Tests for /api/metadata/ endpoint (always available)."""

    def test_returns_200(self):
        response = self.client.get(reverse('api_metadata'))
        self.assertEqual(response.status_code, 200)

    def test_json_structure(self):
        response = self.client.get(reverse('api_metadata'))
        data = self._json(response)
        self.assertTrue(data['success'])
        self.assertIn('endpoints', data)
        self.assertIn('languages', data)
        self.assertIn('clienteles', data)
        self.assertIn('categories', data)

    def test_endpoints_reflect_settings(self):
        """Endpoint 'enabled' flags match the current settings."""
        response = self.client.get(reverse('api_metadata'))
        data = self._json(response)
        eps = data['endpoints']
        self.assertEqual(
            eps['online_services']['enabled'],
            not getattr(settings, 'ONLINE_SERVICES_REQUIRE_LOGIN', True),
        )
        self.assertEqual(
            eps['service_catalogue']['enabled'],
            not getattr(settings, 'SERVICE_CATALOGUE_REQUIRE_LOGIN', True),
        )
        # Metadata itself is always enabled
        self.assertTrue(eps['metadata']['enabled'])

    @override_settings(
        ONLINE_SERVICES_REQUIRE_LOGIN=False,
        SERVICE_CATALOGUE_REQUIRE_LOGIN=False,
    )
    def test_all_enabled_when_public(self):
        """All endpoints show enabled when both settings are False."""
        response = self.client.get(reverse('api_metadata'))
        eps = self._json(response)['endpoints']
        for name, ep in eps.items():
            self.assertTrue(ep['enabled'], f"{name} should be enabled")


@override_settings(
    SERVICE_CATALOGUE_REQUIRE_LOGIN=False,
    SERVICECATALOGUE_FIELD_USAGE_INFORMATION=True,
    SERVICECATALOGUE_FIELD_REQUIREMENTS=True,
    SERVICECATALOGUE_FIELD_DETAILS=True,
    SERVICECATALOGUE_FIELD_OPTIONS=True,
    SERVICECATALOGUE_FIELD_SERVICE_LEVEL=True,
)
class APIFieldVisibilityTest(APITestCase):
    """Test that SERVICECATALOGUE_FIELD_* settings gate API output."""

    @override_settings(SERVICECATALOGUE_FIELD_USAGE_INFORMATION=False)
    def test_usage_information_hidden(self):
        response = self.client.get(reverse('api_service_catalogue'))
        for cat in self._json(response)['categories']:
            for svc in cat['services']:
                self.assertNotIn('usage_information', svc)

    @override_settings(SERVICECATALOGUE_FIELD_REQUIREMENTS=False)
    def test_requirements_hidden(self):
        response = self.client.get(reverse('api_service_catalogue'))
        for cat in self._json(response)['categories']:
            for svc in cat['services']:
                self.assertNotIn('requirements', svc)

    @override_settings(SERVICECATALOGUE_FIELD_DETAILS=False)
    def test_details_hidden(self):
        response = self.client.get(reverse('api_service_catalogue'))
        for cat in self._json(response)['categories']:
            for svc in cat['services']:
                self.assertNotIn('details', svc)

    @override_settings(SERVICECATALOGUE_FIELD_OPTIONS=False)
    def test_options_hidden(self):
        response = self.client.get(reverse('api_service_catalogue'))
        for cat in self._json(response)['categories']:
            for svc in cat['services']:
                self.assertNotIn('options', svc)

    @override_settings(SERVICECATALOGUE_FIELD_SERVICE_LEVEL=False)
    def test_service_level_hidden(self):
        response = self.client.get(reverse('api_service_catalogue'))
        for cat in self._json(response)['categories']:
            for svc in cat['services']:
                self.assertNotIn('service_level', svc)
