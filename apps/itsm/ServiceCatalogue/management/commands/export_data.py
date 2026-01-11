"""
Management command to export ServiceCatalogue data.

Supports exporting to JSON (Django fixtures) or SQL (PostgreSQL dump) formats.
"""

from django.core.management.base import BaseCommand, CommandError
from django.core import serializers
from django.db import connection
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
from datetime import datetime


class Command(BaseCommand):
    help = 'Export ServiceCatalogue data to JSON or SQL format'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'sql', 'both'],
            default='json',
            help='Export format: json, sql, or both (default: json)',
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path (auto-generated if not specified)',
        )
        parser.add_argument(
            '--indent',
            type=int,
            default=2,
            help='JSON indentation level (default: 2)',
        )

    def handle(self, *args, **options):
        export_format = options['format']
        output_path = options['output']
        indent = options['indent']

        self.stdout.write(self.style.WARNING(
            '\n' + '=' * 70
        ))
        self.stdout.write(self.style.WARNING(
            'ServiceCatalogue - Data Export'
        ))
        self.stdout.write(self.style.WARNING(
            '=' * 70 + '\n'
        ))

        # Generate timestamp for default filenames
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Determine output paths
        if export_format in ['json', 'both']:
            json_path = output_path if output_path and export_format == 'json' else f'servicecatalogue_backup_{timestamp}.json'
            self._export_json(json_path, indent)

        if export_format in ['sql', 'both']:
            sql_path = output_path if output_path and export_format == 'sql' else f'servicecatalogue_backup_{timestamp}.sql'
            self._export_sql(sql_path)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            '=' * 70
        ))
        self.stdout.write(self.style.SUCCESS(
            'Export completed successfully!'
        ))
        self.stdout.write(self.style.SUCCESS(
            '=' * 70 + '\n'
        ))

    def _export_json(self, output_path, indent):
        """Export data to JSON format using Django serialization."""
        self.stdout.write(f'Exporting to JSON: {output_path}')
        
        # Define models in order (respecting foreign key dependencies)
        models_to_export = [
            Clientele,
            FeeUnit,
            ServiceProvider,
            ServiceCategory,
            Service,
            ServiceRevision,
            Availability,
        ]

        try:
            # Collect all objects
            all_objects = []
            for model in models_to_export:
                objects = list(model.objects.all())
                all_objects.extend(objects)
                self.stdout.write(f'  • {model.__name__}: {len(objects)} record(s)')

            # Serialize to JSON
            json_data = serializers.serialize(
                'json',
                all_objects,
                indent=indent,
                use_natural_foreign_keys=False,
                use_natural_primary_keys=False,
            )

            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_data)

            file_size = os.path.getsize(output_path)
            self.stdout.write(self.style.SUCCESS(
                f'✓ JSON export complete: {output_path} ({file_size:,} bytes)'
            ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'✗ JSON export failed: {str(e)}'
            ))
            raise CommandError(f'Failed to export JSON: {str(e)}')

    def _export_sql(self, output_path):
        """Export data to SQL format using pg_dump."""
        self.stdout.write(f'\nExporting to SQL: {output_path}')
        
        # Get database settings from Django
        db_settings = connection.settings_dict
        
        if db_settings['ENGINE'] != 'django.db.backends.postgresql':
            raise CommandError('SQL export only supports PostgreSQL databases')

        # Build pg_dump command
        env = os.environ.copy()
        
        if db_settings.get('PASSWORD'):
            env['PGPASSWORD'] = db_settings['PASSWORD']

        cmd = ['pg_dump']
        
        if db_settings.get('HOST'):
            cmd.extend(['-h', db_settings['HOST']])
        
        if db_settings.get('PORT'):
            cmd.extend(['-p', str(db_settings['PORT'])])
        
        if db_settings.get('USER'):
            cmd.extend(['-U', db_settings['USER']])

        # Export only ServiceCatalogue tables
        tables = [
            'ServiceCatalogue_clientele',
            'ServiceCatalogue_feeunit',
            'ServiceCatalogue_serviceprovider',
            'ServiceCatalogue_servicecategory',
            'ServiceCatalogue_service',
            'ServiceCatalogue_service_service_providers',
            'ServiceCatalogue_servicerevision',
            'ServiceCatalogue_availability',
        ]

        for table in tables:
            cmd.extend(['-t', table])

        # Add database name
        cmd.extend(['--data-only', '--column-inserts', db_settings['NAME']])

        try:
            # Run pg_dump
            with open(output_path, 'w') as f:
                result = subprocess.run(
                    cmd,
                    env=env,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    check=True,
                    text=True
                )

            file_size = os.path.getsize(output_path)
            self.stdout.write(self.style.SUCCESS(
                f'✓ SQL export complete: {output_path} ({file_size:,} bytes)'
            ))

        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR(
                f'✗ SQL export failed: {e.stderr}'
            ))
            raise CommandError(f'pg_dump failed: {e.stderr}')
        except FileNotFoundError:
            raise CommandError(
                'pg_dump command not found. Please ensure PostgreSQL client tools are installed.'
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'✗ SQL export failed: {str(e)}'
            ))
            raise CommandError(f'Failed to export SQL: {str(e)}')
