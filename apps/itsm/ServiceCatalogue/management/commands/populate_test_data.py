"""
Management command to populate the ServiceCatalogue with initial test data.

This command is intended for initial database population only. It will check
if the database already contains data and refuse to run if it does.
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import transaction
from ServiceCatalogue.models import (
    Service,
    ServiceRevision,
    ServiceCategory,
    ServiceProvider,
    Clientele,
    FeeUnit,
    Availability,
)


class Command(BaseCommand):
    help = 'Populates the ServiceCatalogue with initial test data (for new installations only)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='REPLACE existing data with test data (deletes all ServiceCatalogue and Group data)',
        )

    def handle(self, *args, **options):
        User = get_user_model()
        
        self.stdout.write(self.style.WARNING(
            '\n' + '=' * 70
        ))
        self.stdout.write(self.style.WARNING(
            'ServiceCatalogue - Initial Test Data Population'
        ))
        self.stdout.write(self.style.WARNING(
            '=' * 70 + '\n'
        ))

        # Check for superuser
        if not User.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.ERROR(
                '✗ No superuser found in the database.'
            ))
            self.stdout.write(self.style.WARNING(
                '\nPlease create a superuser first using:'
            ))
            self.stdout.write(self.style.SUCCESS(
                '  python manage.py createsuperuser'
            ))
            self.stdout.write('')
            raise CommandError('Superuser required before populating test data')

        # Check if database is already populated
        models_to_check = [
            ('ServiceCategory', ServiceCategory),
            ('ServiceProvider', ServiceProvider),
            ('Service', Service),
            ('ServiceRevision', ServiceRevision),
            ('Clientele', Clientele),
            ('FeeUnit', FeeUnit),
            ('Availability', Availability),
        ]
        
        # Check for ServiceCatalogue groups separately
        sc_groups = Group.objects.filter(name__icontains='Service Catalogue')
        group_count = sc_groups.count()

        self.stdout.write('Checking database state...\n')
        
        has_data = False
        for model_name, model in models_to_check:
            count = model.objects.count()
            if count > 0:
                has_data = True
                self.stdout.write(self.style.WARNING(
                    f'  • {model_name}: {count} record(s) found'
                ))
            else:
                self.stdout.write(
                    f'  • {model_name}: empty'
                )
        
        # Report on groups separately
        if group_count > 0:
            has_data = True
            self.stdout.write(self.style.WARNING(
                f'  • Service Catalogue Groups: {group_count} found'
            ))
        else:
            self.stdout.write(
                f'  • Service Catalogue Groups: empty'
            )

        if has_data and not options['force']:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR(
                '✗ Database already contains ServiceCatalogue data!'
            ))
            self.stdout.write(self.style.WARNING(
                '\nThis command is intended for initial population only.'
            ))
            self.stdout.write(self.style.WARNING(
                'To backup and restore data, use:'
            ))
            self.stdout.write(self.style.SUCCESS(
                '  python manage.py export_data --format json'
            ))
            self.stdout.write(self.style.SUCCESS(
                '  python manage.py import_data <backup_file>'
            ))
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                'To REPLACE existing data with test data (deletes all current data):'
            ))
            self.stdout.write(self.style.SUCCESS(
                '  python manage.py populate_test_data --force'
            ))
            self.stdout.write(self.style.ERROR(
                '  (WARNING: This will DELETE all existing data!)'
            ))
            self.stdout.write('')
            raise CommandError('Database already populated')

        if options['force'] and has_data:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR(
                '⚠️  DANGER: This will REPLACE all existing data!'
            ))
            self.stdout.write(self.style.WARNING(
                '\nThe following data will be PERMANENTLY DELETED and replaced with test data:'
            ))
            if group_count > 0:
                self.stdout.write(self.style.WARNING(
                    f'  • {group_count} Service Catalogue permission groups'
                ))
            self.stdout.write(self.style.WARNING(
                '  • All service catalogue data (services, categories, providers, etc.)'
            ))
            self.stdout.write('')
            self.stdout.write(self.style.ERROR(
                'This action CANNOT be undone!'
            ))
            self.stdout.write(self.style.WARNING(
                '\nBefore continuing, you should backup your data:'
            ))
            self.stdout.write(self.style.SUCCESS(
                '  python manage.py export_data --format both'
            ))
            self.stdout.write('')
            response = input('Type YES (in capital letters) to confirm deletion and reload: ')
            if response != 'YES':
                self.stdout.write(self.style.SUCCESS('\nOperation cancelled.'))
                return
            
            # Clear existing data
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('🗑️  Deleting existing data...'))
            
            with transaction.atomic():
                # Delete in reverse order to respect foreign keys
                deleted_counts = {}
                
                # Delete historical records first
                self.stdout.write('  • Deleting historical records...')
                history_count = 0
                
                # Import historical models
                from ServiceCatalogue.models import (
                    Availability as AvailabilityModel,
                    FeeUnit as FeeUnitModel,
                    Clientele as ClienteleModel,
                    ServiceCategory as ServiceCategoryModel,
                )
                
                # Delete histories (simple_history creates these automatically)
                if hasattr(AvailabilityModel, 'history'):
                    history_count += AvailabilityModel.history.all().delete()[0]
                if hasattr(ServiceRevision, 'history'):
                    history_count += ServiceRevision.history.all().delete()[0]
                if hasattr(Service, 'history'):
                    history_count += Service.history.all().delete()[0]
                if hasattr(ServiceCategoryModel, 'history'):
                    history_count += ServiceCategoryModel.history.all().delete()[0]
                if hasattr(ServiceProvider, 'history'):
                    history_count += ServiceProvider.history.all().delete()[0]
                if hasattr(ClienteleModel, 'history'):
                    history_count += ClienteleModel.history.all().delete()[0]
                if hasattr(FeeUnitModel, 'history'):
                    history_count += FeeUnitModel.history.all().delete()[0]
                
                deleted_counts['Historical records'] = history_count
                
                # Delete main data in reverse order
                self.stdout.write('  • Deleting availability records...')
                count = Availability.objects.all().delete()[0]
                deleted_counts['Availability'] = count
                
                self.stdout.write('  • Deleting service revisions...')
                count = ServiceRevision.objects.all().delete()[0]
                deleted_counts['ServiceRevision'] = count
                
                self.stdout.write('  • Deleting services...')
                count = Service.objects.all().delete()[0]
                deleted_counts['Service'] = count
                
                self.stdout.write('  • Deleting service categories...')
                count = ServiceCategory.objects.all().delete()[0]
                deleted_counts['ServiceCategory'] = count
                
                self.stdout.write('  • Deleting service providers...')
                count = ServiceProvider.objects.all().delete()[0]
                deleted_counts['ServiceProvider'] = count
                
                self.stdout.write('  • Deleting clientele groups...')
                count = Clientele.objects.all().delete()[0]
                deleted_counts['Clientele'] = count
                
                self.stdout.write('  • Deleting fee units...')
                count = FeeUnit.objects.all().delete()[0]
                deleted_counts['FeeUnit'] = count
                
                self.stdout.write('  • Deleting permission groups...')
                # Delete ServiceCatalogue-related groups only
                sc_groups = Group.objects.filter(name__icontains='Service Catalogue')
                count = sc_groups.count()
                sc_groups.delete()
                deleted_counts['Service Catalogue Groups'] = count
                
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('✓ Existing data deleted'))
            self.stdout.write('\nDeletion summary:')
            for model_name, count in deleted_counts.items():
                if count > 0:
                    self.stdout.write(self.style.WARNING(
                        f'  • {model_name}: {count} record(s) deleted'
                    ))

        self.stdout.write('')
        self.stdout.write('Setting up groups and loading test data...')
        
        try:
            with transaction.atomic():
                # Initialize permission groups using the management command
                self.stdout.write('  • Initializing permission groups...')
                call_command('initialize_groups', verbosity=0)
                self.stdout.write(self.style.SUCCESS('    ✓ Permission groups initialized'))
                
                # Load test data
                self.stdout.write('  • Loading service catalogue data...')
                call_command('loaddata', 'initial_test_data', verbosity=0)
                self.stdout.write(self.style.SUCCESS('    ✓ Service catalogue data loaded'))
                
                # Verify data was loaded
                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS('✓ Data successfully loaded!\n'))
                self.stdout.write('Summary:')
                
                for model_name, model in models_to_check:
                    count = model.objects.count()
                    self.stdout.write(self.style.SUCCESS(
                        f'  • {model_name}: {count} record(s)'
                    ))

                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS(
                    '=' * 70
                ))
                self.stdout.write(self.style.SUCCESS(
                    'Initial test data successfully populated!'
                ))
                self.stdout.write(self.style.SUCCESS(
                    '=' * 70
                ))
                self.stdout.write('')
                self.stdout.write('You can now:')
                self.stdout.write('  • Access the admin interface')
                self.stdout.write('  • Browse the service catalogue')
                self.stdout.write('  • Customize the data for your institution')
                self.stdout.write('')

        except Exception as e:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR(
                f'✗ Error loading test data: {str(e)}'
            ))
            raise CommandError(f'Failed to load test data: {str(e)}')
