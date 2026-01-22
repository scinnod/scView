"""
Management command to initialize ServiceCatalogue groups and permissions.

This command creates the group hierarchy for the ServiceCatalogue application
and assigns the appropriate permissions based on the recovered permission
structure from the previous implementation.

Group Hierarchy:
  0 - Administrators (50 perms)   - Full access to everything + user management
  1 - Editors (46 perms)          - Can edit service metadata + revisions + publish
  2a - Authors Plus (40 perms)    - Can edit revisions + publish (no service metadata)
  2 - Authors (39 perms)          - Can edit draft revisions only (no publish)
  3 - Viewers (5 perms)           - Read-only access

Key Permission Differences:
  - Editors: Can manage Services and ServiceCategories
  - Authors Plus: Can edit revisions AND publish them
  - Authors: Can only create draft revisions (no publish permission)
  - Viewers: Minimal read-only access
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission


class Command(BaseCommand):
    help = """
    Initialize ServiceCatalogue groups and permissions.
    
    Creates/updates the complete group permission structure for the ServiceCatalogue app.
    Use --reset to delete existing groups first, or --dry-run to preview changes.
    
    Groups created:
      Group 1: Administrators (50 permissions) - Full access + user management
      Group 2: Editors (47 permissions) - Can edit services + publish
      Group 3: Authors Plus (40 permissions) - Can edit revisions + publish
      Group 4: Authors (39 permissions) - Can edit draft revisions only
      Group 5: Viewers (5 permissions) - Read-only access
    """
    
    # Group definitions with their permissions
    GROUP_DEFINITIONS = {
        1: {
            "name": "0 - Service Catalogue Administrators",
            "description": "Full administrative access to all ServiceCatalogue models",
            "permissions": [
                "ServiceCatalogue.add_availability", "ServiceCatalogue.add_historicalavailability",
                "ServiceCatalogue.add_historicalclientele", "ServiceCatalogue.add_historicalfeeunit",
                "ServiceCatalogue.add_historicalservice", "ServiceCatalogue.add_historicalservicecategory",
                "ServiceCatalogue.add_historicalserviceprovider", "ServiceCatalogue.add_historicalservicerevision",
                "ServiceCatalogue.add_service", "ServiceCatalogue.add_servicerevision",
                "ServiceCatalogue.can_publish_service",
                "ServiceCatalogue.change_availability", "ServiceCatalogue.change_historicalavailability",
                "ServiceCatalogue.change_historicalclientele", "ServiceCatalogue.change_historicalfeeunit",
                "ServiceCatalogue.change_historicalservice", "ServiceCatalogue.change_historicalservicecategory",
                "ServiceCatalogue.change_historicalserviceprovider", "ServiceCatalogue.change_historicalservicerevision",
                "ServiceCatalogue.change_service", "ServiceCatalogue.change_servicecategory",
                "ServiceCatalogue.change_servicerevision",
                "ServiceCatalogue.delete_availability", "ServiceCatalogue.delete_historicalavailability",
                "ServiceCatalogue.delete_historicalclientele", "ServiceCatalogue.delete_historicalfeeunit",
                "ServiceCatalogue.delete_historicalservice", "ServiceCatalogue.delete_historicalservicecategory",
                "ServiceCatalogue.delete_historicalserviceprovider", "ServiceCatalogue.delete_historicalservicerevision",
                "ServiceCatalogue.delete_service", "ServiceCatalogue.delete_servicerevision",
                "ServiceCatalogue.view_availability", "ServiceCatalogue.view_clientele",
                "ServiceCatalogue.view_feeunit", "ServiceCatalogue.view_historicalavailability",
                "ServiceCatalogue.view_historicalclientele", "ServiceCatalogue.view_historicalfeeunit",
                "ServiceCatalogue.view_historicalservice", "ServiceCatalogue.view_historicalservicecategory",
                "ServiceCatalogue.view_historicalserviceprovider", "ServiceCatalogue.view_historicalservicerevision",
                "ServiceCatalogue.view_service", "ServiceCatalogue.view_servicecategory",
                "ServiceCatalogue.view_serviceprovider", "ServiceCatalogue.view_servicerevision",
                "auth.add_user", "auth.change_user", "auth.delete_user", "auth.view_user"
            ]
        },
        2: {
            "name": "1 - Service Catalogue Editors (can edit service metadata and revisions and publish)",
            "description": "Can edit Service metadata, ServiceRevisions, and publish services",
            "permissions": [
                "ServiceCatalogue.add_availability", "ServiceCatalogue.add_historicalavailability",
                "ServiceCatalogue.add_historicalclientele", "ServiceCatalogue.add_historicalfeeunit",
                "ServiceCatalogue.add_historicalservice", "ServiceCatalogue.add_historicalservicecategory",
                "ServiceCatalogue.add_historicalserviceprovider", "ServiceCatalogue.add_historicalservicerevision",
                "ServiceCatalogue.add_service", "ServiceCatalogue.add_servicerevision",
                "ServiceCatalogue.can_publish_service",
                "ServiceCatalogue.change_availability", "ServiceCatalogue.change_historicalavailability",
                "ServiceCatalogue.change_historicalclientele", "ServiceCatalogue.change_historicalfeeunit",
                "ServiceCatalogue.change_historicalservice", "ServiceCatalogue.change_historicalservicecategory",
                "ServiceCatalogue.change_historicalserviceprovider", "ServiceCatalogue.change_historicalservicerevision",
                "ServiceCatalogue.change_service", "ServiceCatalogue.change_servicecategory",
                "ServiceCatalogue.change_servicerevision",
                "ServiceCatalogue.delete_availability", "ServiceCatalogue.delete_historicalavailability",
                "ServiceCatalogue.delete_historicalclientele", "ServiceCatalogue.delete_historicalfeeunit",
                "ServiceCatalogue.delete_historicalservice", "ServiceCatalogue.delete_historicalservicecategory",
                "ServiceCatalogue.delete_historicalserviceprovider", "ServiceCatalogue.delete_historicalservicerevision",
                "ServiceCatalogue.delete_service", "ServiceCatalogue.delete_servicerevision",
                "ServiceCatalogue.view_availability", "ServiceCatalogue.view_clientele",
                "ServiceCatalogue.view_feeunit", "ServiceCatalogue.view_historicalavailability",
                "ServiceCatalogue.view_historicalclientele", "ServiceCatalogue.view_historicalfeeunit",
                "ServiceCatalogue.view_historicalservice", "ServiceCatalogue.view_historicalservicecategory",
                "ServiceCatalogue.view_historicalserviceprovider", "ServiceCatalogue.view_historicalservicerevision",
                "ServiceCatalogue.view_service", "ServiceCatalogue.view_servicecategory",
                "ServiceCatalogue.view_serviceprovider", "ServiceCatalogue.view_servicerevision"
            ]
        },
        3: {
            "name": "2a - Service Catalogue Authors Plus (can edit online service revisions and publish)",
            "description": "Can edit ServiceRevisions and publish them (no Service metadata access)",
            "permissions": [
                "ServiceCatalogue.add_availability", "ServiceCatalogue.add_historicalavailability",
                "ServiceCatalogue.add_historicalclientele", "ServiceCatalogue.add_historicalfeeunit",
                "ServiceCatalogue.add_historicalservice", "ServiceCatalogue.add_historicalservicecategory",
                "ServiceCatalogue.add_historicalserviceprovider", "ServiceCatalogue.add_historicalservicerevision",
                "ServiceCatalogue.add_servicerevision", "ServiceCatalogue.can_publish_service",
                "ServiceCatalogue.change_availability", "ServiceCatalogue.change_historicalavailability",
                "ServiceCatalogue.change_historicalclientele", "ServiceCatalogue.change_historicalfeeunit",
                "ServiceCatalogue.change_historicalservice", "ServiceCatalogue.change_historicalservicecategory",
                "ServiceCatalogue.change_historicalserviceprovider", "ServiceCatalogue.change_historicalservicerevision",
                "ServiceCatalogue.change_servicerevision",
                "ServiceCatalogue.delete_availability", "ServiceCatalogue.delete_historicalavailability",
                "ServiceCatalogue.delete_historicalclientele", "ServiceCatalogue.delete_historicalfeeunit",
                "ServiceCatalogue.delete_historicalservice", "ServiceCatalogue.delete_historicalservicecategory",
                "ServiceCatalogue.delete_historicalserviceprovider", "ServiceCatalogue.delete_historicalservicerevision",
                "ServiceCatalogue.delete_servicerevision",
                "ServiceCatalogue.view_availability", "ServiceCatalogue.view_clientele",
                "ServiceCatalogue.view_historicalavailability", "ServiceCatalogue.view_historicalclientele",
                "ServiceCatalogue.view_historicalfeeunit", "ServiceCatalogue.view_historicalservice",
                "ServiceCatalogue.view_historicalservicecategory", "ServiceCatalogue.view_historicalserviceprovider",
                "ServiceCatalogue.view_historicalservicerevision", "ServiceCatalogue.view_service",
                "ServiceCatalogue.view_servicecategory", "ServiceCatalogue.view_servicerevision"
            ]
        },
        4: {
            "name": "2 - Service Catalogue Authors (can edit drafts service revision drafts only)",
            "description": "Can edit draft ServiceRevisions only (no publish permission)",
            "permissions": [
                "ServiceCatalogue.add_availability", "ServiceCatalogue.add_historicalavailability",
                "ServiceCatalogue.add_historicalclientele", "ServiceCatalogue.add_historicalfeeunit",
                "ServiceCatalogue.add_historicalservice", "ServiceCatalogue.add_historicalservicecategory",
                "ServiceCatalogue.add_historicalserviceprovider", "ServiceCatalogue.add_historicalservicerevision",
                "ServiceCatalogue.add_servicerevision",
                "ServiceCatalogue.change_availability", "ServiceCatalogue.change_historicalavailability",
                "ServiceCatalogue.change_historicalclientele", "ServiceCatalogue.change_historicalfeeunit",
                "ServiceCatalogue.change_historicalservice", "ServiceCatalogue.change_historicalservicecategory",
                "ServiceCatalogue.change_historicalserviceprovider", "ServiceCatalogue.change_historicalservicerevision",
                "ServiceCatalogue.change_servicerevision",
                "ServiceCatalogue.delete_availability", "ServiceCatalogue.delete_historicalavailability",
                "ServiceCatalogue.delete_historicalclientele", "ServiceCatalogue.delete_historicalfeeunit",
                "ServiceCatalogue.delete_historicalservice", "ServiceCatalogue.delete_historicalservicecategory",
                "ServiceCatalogue.delete_historicalserviceprovider", "ServiceCatalogue.delete_historicalservicerevision",
                "ServiceCatalogue.delete_servicerevision",
                "ServiceCatalogue.view_availability", "ServiceCatalogue.view_clientele",
                "ServiceCatalogue.view_historicalavailability", "ServiceCatalogue.view_historicalclientele",
                "ServiceCatalogue.view_historicalfeeunit", "ServiceCatalogue.view_historicalservice",
                "ServiceCatalogue.view_historicalservicecategory", "ServiceCatalogue.view_historicalserviceprovider",
                "ServiceCatalogue.view_historicalservicerevision", "ServiceCatalogue.view_service",
                "ServiceCatalogue.view_servicecategory", "ServiceCatalogue.view_servicerevision"
            ]
        },
        5: {
            "name": "3 - Service Catalogue Viewers",
            "description": "Read-only access to core models",
            "permissions": [
                "ServiceCatalogue.view_availability", "ServiceCatalogue.view_clientele",
                "ServiceCatalogue.view_service", "ServiceCatalogue.view_servicecategory",
                "ServiceCatalogue.view_servicerevision"
            ]
        }
    }
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete all ServiceCatalogue groups and recreate them from scratch',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        reset = options['reset']
        dry_run = options['dry_run']
        
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.HTTP_INFO("ServiceCatalogue - Initialize Groups and Permissions"))
        self.stdout.write("=" * 80)
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\n⚠ DRY RUN MODE - No changes will be made\n"))
        
        if reset:
            self._reset_groups(dry_run)
        
        self._initialize_groups(dry_run)
        
        self.stdout.write("=" * 80)
    
    def _reset_groups(self, dry_run):
        """Delete all ServiceCatalogue groups"""
        self.stdout.write("\n" + self.style.WARNING("RESET MODE: Deleting existing groups..."))
        
        groups_to_delete = Group.objects.filter(name__icontains='Service Catalogue')
        
        if groups_to_delete.exists():
            self.stdout.write(f"  Found {groups_to_delete.count()} existing group(s):")
            for group in groups_to_delete:
                user_count = group.user_set.count()
                self.stdout.write(f"    - {group.name} (pk={group.pk}, {user_count} users)")
            
            if not dry_run:
                count = groups_to_delete.count()
                groups_to_delete.delete()
                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {count} group(s)\n"))
            else:
                self.stdout.write(self.style.WARNING(f"  [DRY RUN] Would delete {groups_to_delete.count()} group(s)\n"))
        else:
            self.stdout.write("  No existing groups found\n")
    
    def _initialize_groups(self, dry_run):
        """Create or update groups with permissions"""
        self.stdout.write("\nInitializing groups and permissions...\n")
        
        total_created = 0
        total_updated = 0
        total_permissions = 0
        missing_perms_summary = []
        
        for pk, group_def in self.GROUP_DEFINITIONS.items():
            group_name = group_def["name"]
            perm_codes = group_def["permissions"]
            
            self.stdout.write(f"\nGroup {pk}: {group_name}")
            self.stdout.write(f"  Description: {group_def['description']}")
            
            # Create or get group
            if dry_run:
                try:
                    group = Group.objects.get(pk=pk)
                except Group.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"  [DRY RUN] Would create new group"))
                    group = Group(pk=pk, name=group_name)  # Temporary for checks
            else:
                group, created = Group.objects.get_or_create(pk=pk, defaults={'name': group_name})
                
                if created:
                    total_created += 1
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Created new group"))
                else:
                    total_updated += 1
                    if group.name != group_name:
                        group.name = group_name
                        group.save()
                        self.stdout.write(self.style.SUCCESS(f"  ✓ Updated group name"))
                    else:
                        self.stdout.write(f"  ✓ Group exists")
            
            # Assign permissions
            assigned_count = 0
            missing_perms = []
            
            if not dry_run:
                group.permissions.clear()
            
            for perm_code in perm_codes:
                app_label, codename = perm_code.split('.')
                
                try:
                    permission = Permission.objects.get(
                        content_type__app_label=app_label,
                        codename=codename
                    )
                    
                    if not dry_run:
                        group.permissions.add(permission)
                    assigned_count += 1
                    
                except Permission.DoesNotExist:
                    missing_perms.append(perm_code)
            
            total_permissions += assigned_count
            
            if dry_run:
                self.stdout.write(self.style.WARNING(
                    f"  [DRY RUN] Would assign {assigned_count}/{len(perm_codes)} permissions"
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ Assigned {assigned_count}/{len(perm_codes)} permissions"
                ))
            
            if missing_perms:
                missing_perms_summary.extend(missing_perms)
                self.stdout.write(self.style.WARNING(
                    f"  ⚠ Missing {len(missing_perms)} permission(s)"
                ))
        
        # Summary
        self.stdout.write("\n" + "-" * 80)
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN SUMMARY:"))
        else:
            self.stdout.write(self.style.SUCCESS("SUMMARY:"))
        
        self.stdout.write(f"  Groups created: {total_created}")
        self.stdout.write(f"  Groups updated: {total_updated}")
        self.stdout.write(f"  Total permissions assigned: {total_permissions}")
        
        if missing_perms_summary:
            unique_missing = list(set(missing_perms_summary))
            self.stdout.write(self.style.WARNING(f"  Warnings: {len(unique_missing)} unique missing permission(s)"))
            self.stdout.write("\n  Run migrations to create missing permissions:")
            self.stdout.write("    python manage.py migrate")
        else:
            self.stdout.write(self.style.SUCCESS("  ✓ No errors - all permissions found"))
        
        if not dry_run:
            self.stdout.write("\n" + self.style.SUCCESS("✓ Group initialization complete!"))
        else:
            self.stdout.write("\n" + self.style.WARNING("✓ Dry run complete - no changes made"))
