"""
Management command to import ServiceCatalogue data.

Supports importing from JSON (Django fixtures) or SQL (PostgreSQL dump) formats.
Auto-detects format based on file extension.
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.db import connection, transaction
from ServiceCatalogue.models import (
    Service,
    ServiceRevision,
    ServiceCategory,
    ServiceProvider,
    Clientele,
    FeeUnit,
    Availability,
)
import os
import subprocess
import json


class Command(BaseCommand):
    help = 'Import ServiceCatalogue data from JSON or SQL format'

    def add_arguments(self, parser):
        parser.add_argument(
            'file',
            type=str,
            help='Input file path (JSON or SQL)',
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'sql', 'auto'],
            default='auto',
            help='Input format: json, sql, or auto-detect (default: auto)',
        )
        parser.add_argument(
            '--test-data',
            action='store_true',
            help='Load initial test data instead of backup (uses built-in fixture)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing ServiceCatalogue data before import',
        )

    def handle(self, *args, **options):
        file_path = options['file']
        import_format = options['format']
        test_data = options['test_data']
        clear_data = options['clear']

        self.stdout.write(self.style.WARNING(
            '\n' + '=' * 70
        ))
        self.stdout.write(self.style.WARNING(
            'ServiceCatalogue - Data Import'
        ))
        self.stdout.write(self.style.WARNING(
            '=' * 70 + '\n'
        ))

        # Handle test data option
        if test_data:
            self.stdout.write(self.style.WARNING(
                'Note: --test-data option is set. Use populate_test_data command instead:'
            ))
            self.stdout.write(self.style.SUCCESS(
                '  python manage.py populate_test_data\n'
            ))
            response = input('Continue with file import anyway? [y/N]: ')
            if response.lower() != 'y':
                self.stdout.write(self.style.SUCCESS('Operation cancelled.'))
                return

        # Check file exists
        if not os.path.exists(file_path):
            raise CommandError(f'File not found: {file_path}')

        # Auto-detect format
        if import_format == 'auto':
            if file_path.endswith('.json'):
                import_format = 'json'
            elif file_path.endswith('.sql'):
                import_format = 'sql'
            else:
                # Try to detect by content
                try:
                    with open(file_path, 'r') as f:
                        first_line = f.readline().strip()
                        if first_line.startswith('[') or first_line.startswith('{'):
                            import_format = 'json'
                        elif 'INSERT INTO' in first_line or 'PostgreSQL' in first_line:
                            import_format = 'sql'
                        else:
                            raise CommandError(
                                'Cannot auto-detect format. Please specify --format json or --format sql'
                            )
                except Exception as e:
                    raise CommandError(f'Cannot read file: {str(e)}')

        self.stdout.write(f'Input file: {file_path}')
        self.stdout.write(f'Format: {import_format.upper()}\n')

        # Clear existing data if requested
        if clear_data:
            self._clear_data()

        # Import based on format
        if import_format == 'json':
            self._import_json(file_path)
        elif import_format == 'sql':
            self._import_sql(file_path)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            '=' * 70
        ))
        self.stdout.write(self.style.SUCCESS(
            'Import completed successfully!'
        ))
        self.stdout.write(self.style.SUCCESS(
            '=' * 70 + '\n'
        ))

    def _clear_data(self):
        """Clear existing ServiceCatalogue data."""
        self.stdout.write(self.style.WARNING('Clearing existing data...'))
        
        models = [
            ('Availability', Availability),
            ('ServiceRevision', ServiceRevision),
            ('Service', Service),
            ('ServiceCategory', ServiceCategory),
            ('ServiceProvider', ServiceProvider),
            ('FeeUnit', FeeUnit),
            ('Clientele', Clientele),
        ]

        try:
            with transaction.atomic():
                for model_name, model in models:
                    count = model.objects.count()
                    if count > 0:
                        model.objects.all().delete()
                        self.stdout.write(f'  • Deleted {count} {model_name} record(s)')
                    
            self.stdout.write(self.style.SUCCESS('✓ Data cleared\n'))
        except Exception as e:
            raise CommandError(f'Failed to clear data: {str(e)}')

    def _import_json(self, file_path):
        """Import data from JSON format."""
        self.stdout.write('Importing from JSON...')
        
        try:
            # Validate JSON
            with open(file_path, 'r') as f:
                data = json.load(f)
                
            if not isinstance(data, list):
                raise CommandError('Invalid JSON format: expected array of objects')
            
            self.stdout.write(f'  • Found {len(data)} record(s) in file')

            # Load using Django's loaddata
            with transaction.atomic():
                call_command('loaddata', file_path, verbosity=0)

            self.stdout.write(self.style.SUCCESS('✓ JSON import complete\n'))
            self._show_summary()

        except json.JSONDecodeError as e:
            raise CommandError(f'Invalid JSON file: {str(e)}')
        except Exception as e:
            raise CommandError(f'Failed to import JSON: {str(e)}')

    def _import_sql(self, file_path):
        """Import data from SQL format."""
        self.stdout.write('Importing from SQL...')
        
        # Get database settings
        db_settings = connection.settings_dict
        
        if db_settings['ENGINE'] != 'django.db.backends.postgresql':
            raise CommandError('SQL import only supports PostgreSQL databases')

        # Build psql command
        env = os.environ.copy()
        
        if db_settings.get('PASSWORD'):
            env['PGPASSWORD'] = db_settings['PASSWORD']

        cmd = ['psql']
        
        if db_settings.get('HOST'):
            cmd.extend(['-h', db_settings['HOST']])
        
        if db_settings.get('PORT'):
            cmd.extend(['-p', str(db_settings['PORT'])])
        
        if db_settings.get('USER'):
            cmd.extend(['-U', db_settings['USER']])

        cmd.extend(['-d', db_settings['NAME'], '-f', file_path])

        try:
            result = subprocess.run(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True
            )

            if result.stderr and 'ERROR' in result.stderr:
                self.stdout.write(self.style.WARNING(
                    f'Warnings/Errors:\n{result.stderr}'
                ))

            self.stdout.write(self.style.SUCCESS('✓ SQL import complete\n'))
            self._show_summary()

        except subprocess.CalledProcessError as e:
            raise CommandError(f'psql failed: {e.stderr}')
        except FileNotFoundError:
            raise CommandError(
                'psql command not found. Please ensure PostgreSQL client tools are installed.'
            )
        except Exception as e:
            raise CommandError(f'Failed to import SQL: {str(e)}')

    def _show_summary(self):
        """Show summary of imported data."""
        models = [
            ('ServiceCategory', ServiceCategory),
            ('ServiceProvider', ServiceProvider),
            ('Clientele', Clientele),
            ('FeeUnit', FeeUnit),
            ('Service', Service),
            ('ServiceRevision', ServiceRevision),
            ('Availability', Availability),
        ]

        self.stdout.write('Summary:')
        for model_name, model in models:
            count = model.objects.count()
            self.stdout.write(f'  • {model_name}: {count} record(s)')
