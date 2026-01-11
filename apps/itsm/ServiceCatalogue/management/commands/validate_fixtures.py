"""
Management command to validate Service Catalogue fixture files.

This command thoroughly validates fixture JSON files for:
- JSON syntax and structure
- Model existence and field definitions
- Required fields presence
- Data type correctness
- Foreign key references
- Unique constraints
- Date logic
- Field length limits
- Translation completeness
- Email and URL formats

Usage:
    python manage.py validate_fixtures <fixture_file_or_directory> [--verbose]
"""

import json
import os
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from ServiceCatalogue.models import (
    ServiceCategory, Service, ServiceRevision,
    ServiceProvider, Clientele, FeeUnit, Availability
)


class Command(BaseCommand):
    help = 'Validates Service Catalogue fixture files for correctness'

    def __init__(self):
        super().__init__()
        self.errors = []
        self.warnings = []
        self.info = []
        self.verbose = False
        
        # Track pks and unique values for cross-record validation
        self.pks = {}
        self.unique_values = {
            'ServiceCatalogue.servicecategory': {'acronym': set()},
            'ServiceCatalogue.clientele': {'acronym': set()},
            'ServiceCatalogue.service': {'category_acronym': set()},
            'ServiceCatalogue.servicerevision': {'service_version': set()},
            'ServiceCatalogue.availability': {'servicerevision_clientele': set()},
        }

    def add_arguments(self, parser):
        parser.add_argument(
            'path',
            type=str,
            help='Path to fixture file or directory containing fixtures'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed validation information',
        )

    def handle(self, *args, **options):
        self.verbose = options['verbose']
        path = options['path']
        
        self.stdout.write(self.style.WARNING(
            '\n' + '=' * 70
        ))
        self.stdout.write(self.style.WARNING(
            'Service Catalogue Fixture Validator'
        ))
        self.stdout.write(self.style.WARNING(
            '=' * 70 + '\n'
        ))

        # Determine if path is file or directory
        path_obj = Path(path)
        
        if not path_obj.exists():
            raise CommandError(f'Path does not exist: {path}')
        
        fixture_files = []
        if path_obj.is_file():
            if path_obj.suffix == '.json':
                fixture_files = [path_obj]
            else:
                raise CommandError('File must have .json extension')
        elif path_obj.is_dir():
            fixture_files = sorted(path_obj.glob('*.json'))
            if not fixture_files:
                raise CommandError(f'No .json files found in directory: {path}')
        
        self.stdout.write(f'Found {len(fixture_files)} fixture file(s) to validate\n')
        
        # Validate each file
        total_records = 0
        for fixture_file in fixture_files:
            self.stdout.write(f'Validating: {fixture_file.name}')
            records = self.validate_fixture_file(fixture_file)
            total_records += records
            self.stdout.write('')
        
        # Summary
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write(self.style.WARNING('Validation Summary'))
        self.stdout.write(self.style.WARNING('=' * 70 + '\n'))
        
        self.stdout.write(f'Total records validated: {total_records}')
        self.stdout.write(f'Errors: {len(self.errors)}')
        self.stdout.write(f'Warnings: {len(self.warnings)}')
        if self.verbose:
            self.stdout.write(f'Info messages: {len(self.info)}\n')
        
        if self.errors:
            self.stdout.write(self.style.ERROR('\n❌ ERRORS FOUND:'))
            for error in self.errors:
                self.stdout.write(self.style.ERROR(f'  • {error}'))
        
        if self.warnings:
            self.stdout.write(self.style.WARNING('\n⚠ WARNINGS:'))
            for warning in self.warnings:
                self.stdout.write(self.style.WARNING(f'  • {warning}'))
        
        if self.verbose and self.info:
            self.stdout.write(self.style.SUCCESS('\nℹ INFO:'))
            for info in self.info:
                self.stdout.write(f'  • {info}')
        
        self.stdout.write('')
        if self.errors:
            self.stdout.write(self.style.ERROR('❌ Validation FAILED - please fix errors above'))
            raise CommandError('Fixture validation failed')
        elif self.warnings:
            self.stdout.write(self.style.WARNING('⚠ Validation PASSED with warnings'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ Validation PASSED - fixtures are valid!'))

    def validate_fixture_file(self, filepath):
        """Validate a single fixture file."""
        # Read and parse JSON
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.errors.append(f'{filepath.name}: Invalid JSON syntax: {e}')
            return 0
        except Exception as e:
            self.errors.append(f'{filepath.name}: Error reading file: {e}')
            return 0
        
        # Check top-level structure
        if not isinstance(data, list):
            self.errors.append(f'{filepath.name}: Fixture must be a JSON array')
            return 0
        
        if len(data) == 0:
            self.warnings.append(f'{filepath.name}: Empty fixture file')
            return 0
        
        self.info.append(f'{filepath.name}: {len(data)} records')
        
        # Validate each record
        for idx, record in enumerate(data, 1):
            self.validate_record(record, idx, filepath.name)
        
        return len(data)

    def validate_record(self, record, idx, filename):
        """Validate a single fixture record."""
        prefix = f'{filename}[{idx}]'
        
        # Check record structure
        if not isinstance(record, dict):
            self.errors.append(f'{prefix}: Record must be a JSON object')
            return
        
        if 'model' not in record:
            self.errors.append(f'{prefix}: Missing "model" field')
            return
        
        if 'pk' not in record:
            self.errors.append(f'{prefix}: Missing "pk" field')
            return
        
        if 'fields' not in record:
            self.errors.append(f'{prefix}: Missing "fields" field')
            return
        
        model_name = record['model']
        pk = record['pk']
        fields = record['fields']
        
        # Validate model name
        if not model_name.startswith('ServiceCatalogue.'):
            self.errors.append(f'{prefix}: Model must start with "ServiceCatalogue."')
            return
        
        # Track pk
        if model_name not in self.pks:
            self.pks[model_name] = set()
        
        if pk in self.pks[model_name]:
            self.errors.append(f'{prefix}: Duplicate pk {pk} for model {model_name}')
        else:
            self.pks[model_name].add(pk)
        
        # Validate based on model type
        model_validators = {
            'ServiceCatalogue.servicecategory': self.validate_servicecategory,
            'ServiceCatalogue.clientele': self.validate_clientele,
            'ServiceCatalogue.feeunit': self.validate_feeunit,
            'ServiceCatalogue.serviceprovider': self.validate_serviceprovider,
            'ServiceCatalogue.service': self.validate_service,
            'ServiceCatalogue.servicerevision': self.validate_servicerevision,
            'ServiceCatalogue.availability': self.validate_availability,
        }
        
        validator = model_validators.get(model_name)
        if validator:
            validator(fields, pk, prefix)
        else:
            self.warnings.append(f'{prefix}: Unknown model {model_name}')

    def check_required_field(self, fields, field_name, prefix):
        """Check if a required field is present and not null."""
        if field_name not in fields:
            self.errors.append(f'{prefix}: Missing required field "{field_name}"')
            return False
        if fields[field_name] is None:
            self.errors.append(f'{prefix}: Required field "{field_name}" cannot be null')
            return False
        return True

    def check_string_field(self, fields, field_name, prefix, required=False, max_length=None):
        """Validate a string field."""
        if field_name not in fields or fields[field_name] is None:
            if required:
                self.errors.append(f'{prefix}: Missing required field "{field_name}"')
            return
        
        value = fields[field_name]
        if not isinstance(value, str):
            self.errors.append(f'{prefix}: Field "{field_name}" must be a string')
            return
        
        if max_length and len(value) > max_length:
            self.errors.append(
                f'{prefix}: Field "{field_name}" exceeds max length {max_length} '
                f'(current: {len(value)})'
            )

    def check_translation_fields(self, fields, base_name, prefix, required=False):
        """Check that both _de and _en translation fields are present."""
        de_field = f'{base_name}_de'
        en_field = f'{base_name}_en'
        
        if required:
            self.check_required_field(fields, de_field, prefix)
            self.check_required_field(fields, en_field, prefix)
        
        if de_field in fields and fields[de_field] is not None:
            if not isinstance(fields[de_field], str):
                self.errors.append(f'{prefix}: Field "{de_field}" must be a string')
        
        if en_field in fields and fields[en_field] is not None:
            if not isinstance(fields[en_field], str):
                self.errors.append(f'{prefix}: Field "{en_field}" must be a string')

    def check_date_field(self, fields, field_name, prefix, required=False):
        """Validate a date field."""
        if field_name not in fields or fields[field_name] is None:
            if required:
                self.errors.append(f'{prefix}: Missing required date field "{field_name}"')
            return None
        
        value = fields[field_name]
        if not isinstance(value, str):
            self.errors.append(f'{prefix}: Date field "{field_name}" must be a string')
            return None
        
        # Validate date format YYYY-MM-DD
        try:
            parsed_date = datetime.strptime(value, '%Y-%m-%d').date()
            return parsed_date
        except ValueError:
            self.errors.append(
                f'{prefix}: Date field "{field_name}" must be in YYYY-MM-DD format '
                f'(got: {value})'
            )
            return None

    def check_foreign_key(self, fields, field_name, target_model, prefix, required=False):
        """Validate a foreign key field."""
        if field_name not in fields or fields[field_name] is None:
            if required:
                self.errors.append(f'{prefix}: Missing required foreign key "{field_name}"')
            return
        
        value = fields[field_name]
        if not isinstance(value, int):
            self.errors.append(
                f'{prefix}: Foreign key "{field_name}" must be an integer (got: {type(value).__name__})'
            )
            return
        
        # Warn if referenced pk not found (might be in another file)
        if target_model not in self.pks or value not in self.pks[target_model]:
            self.warnings.append(
                f'{prefix}: Foreign key "{field_name}" references {target_model} pk={value} '
                f'which was not found in this fixture file'
            )

    def check_email_field(self, fields, field_name, prefix, required=False):
        """Validate an email field."""
        if field_name not in fields or fields[field_name] is None:
            if required:
                self.errors.append(f'{prefix}: Missing required email field "{field_name}"')
            return
        
        value = fields[field_name]
        if not isinstance(value, str):
            self.errors.append(f'{prefix}: Email field "{field_name}" must be a string')
            return
        
        # Simple email validation
        if '@' not in value or '.' not in value.split('@')[-1]:
            self.errors.append(f'{prefix}: Invalid email format in "{field_name}": {value}')

    def check_url_field(self, fields, field_name, prefix, required=False):
        """Validate a URL field."""
        if field_name not in fields or fields[field_name] is None:
            if required:
                self.errors.append(f'{prefix}: Missing required URL field "{field_name}"')
            return
        
        value = fields[field_name]
        if not isinstance(value, str):
            self.errors.append(f'{prefix}: URL field "{field_name}" must be a string')
            return
        
        # Check URL starts with http:// or https://
        if not value.startswith(('http://', 'https://')):
            self.errors.append(
                f'{prefix}: URL field "{field_name}" should start with http:// or https://'
            )

    def check_decimal_field(self, fields, field_name, prefix, required=False):
        """Validate a decimal field."""
        if field_name not in fields or fields[field_name] is None:
            if required:
                self.errors.append(f'{prefix}: Missing required decimal field "{field_name}"')
            return
        
        value = fields[field_name]
        if not isinstance(value, str):
            self.errors.append(
                f'{prefix}: Decimal field "{field_name}" must be a quoted string '
                f'(got: {type(value).__name__})'
            )
            return
        
        # Validate decimal format
        try:
            decimal_value = Decimal(value)
            # Check decimal places (should be 2 for fees)
            if '.' in value and len(value.split('.')[1]) != 2:
                self.warnings.append(
                    f'{prefix}: Decimal field "{field_name}" should have exactly 2 decimal places '
                    f'(got: {value})'
                )
        except InvalidOperation:
            self.errors.append(f'{prefix}: Invalid decimal value in "{field_name}": {value}')

    def validate_servicecategory(self, fields, pk, prefix):
        """Validate ServiceCategory fields."""
        self.check_string_field(fields, 'order', prefix, max_length=10)
        self.check_translation_fields(fields, 'name', prefix, required=True)
        self.check_string_field(fields, 'acronym', prefix, required=True, max_length=10)
        self.check_translation_fields(fields, 'description', prefix)
        self.check_string_field(fields, 'responsible', prefix, max_length=80)
        
        # Check unique acronym
        if 'acronym' in fields and fields['acronym']:
            acronym = fields['acronym']
            if acronym in self.unique_values['ServiceCatalogue.servicecategory']['acronym']:
                self.errors.append(f'{prefix}: Duplicate acronym "{acronym}"')
            else:
                self.unique_values['ServiceCatalogue.servicecategory']['acronym'].add(acronym)

    def validate_clientele(self, fields, pk, prefix):
        """Validate Clientele fields."""
        self.check_string_field(fields, 'order', prefix, max_length=10)
        self.check_translation_fields(fields, 'name', prefix, required=True)
        self.check_string_field(fields, 'acronym', prefix, required=True, max_length=10)
        
        # Check unique acronym
        if 'acronym' in fields and fields['acronym']:
            acronym = fields['acronym']
            if acronym in self.unique_values['ServiceCatalogue.clientele']['acronym']:
                self.errors.append(f'{prefix}: Duplicate acronym "{acronym}"')
            else:
                self.unique_values['ServiceCatalogue.clientele']['acronym'].add(acronym)

    def validate_feeunit(self, fields, pk, prefix):
        """Validate FeeUnit fields."""
        self.check_translation_fields(fields, 'name', prefix, required=True)

    def validate_serviceprovider(self, fields, pk, prefix):
        """Validate ServiceProvider fields."""
        self.check_string_field(fields, 'hierarchy', prefix, required=True, max_length=10)
        self.check_string_field(fields, 'name', prefix, required=True, max_length=80)
        self.check_string_field(fields, 'acronym', prefix, max_length=10)

    def validate_service(self, fields, pk, prefix):
        """Validate Service fields."""
        self.check_string_field(fields, 'order', prefix, max_length=10)
        self.check_foreign_key(fields, 'category', 'ServiceCatalogue.servicecategory', prefix, required=True)
        self.check_translation_fields(fields, 'name', prefix, required=True)
        self.check_string_field(fields, 'acronym', prefix, required=True, max_length=10)
        self.check_translation_fields(fields, 'purpose', prefix, required=True)
        self.check_string_field(fields, 'responsible', prefix, max_length=80)
        
        # service_providers is optional many-to-many
        if 'service_providers' in fields and fields['service_providers'] is not None:
            if not isinstance(fields['service_providers'], list):
                self.errors.append(f'{prefix}: Field "service_providers" must be an array')
        
        # Check unique (category, acronym) combination
        if 'category' in fields and 'acronym' in fields:
            category_id = fields['category']
            acronym = fields['acronym']
            unique_key = f'{category_id}:{acronym}'
            if unique_key in self.unique_values['ServiceCatalogue.service']['category_acronym']:
                self.errors.append(
                    f'{prefix}: Duplicate (category, acronym) combination: '
                    f'category={category_id}, acronym="{acronym}"'
                )
            else:
                self.unique_values['ServiceCatalogue.service']['category_acronym'].add(unique_key)

    def validate_servicerevision(self, fields, pk, prefix):
        """Validate ServiceRevision fields."""
        self.check_foreign_key(fields, 'service', 'ServiceCatalogue.service', prefix, required=True)
        self.check_string_field(fields, 'version', prefix, required=True, max_length=10)
        self.check_translation_fields(fields, 'keywords', prefix)
        
        # Boolean field
        if 'submitted' in fields and fields['submitted'] is not None:
            if not isinstance(fields['submitted'], bool):
                self.errors.append(f'{prefix}: Field "submitted" must be a boolean')
        
        # Date fields
        listed_from = self.check_date_field(fields, 'listed_from', prefix)
        available_from = self.check_date_field(fields, 'available_from', prefix)
        listed_until = self.check_date_field(fields, 'listed_until', prefix)
        available_until = self.check_date_field(fields, 'available_until', prefix)
        
        # Date logic validation
        if listed_until and not listed_from:
            self.errors.append(
                f'{prefix}: If "listed_until" is set, "listed_from" must also be set'
            )
        
        if listed_from and listed_until and listed_until < listed_from:
            self.errors.append(
                f'{prefix}: "listed_until" cannot be earlier than "listed_from"'
            )
        
        if listed_until and not available_until:
            self.errors.append(
                f'{prefix}: If "listed_until" is set, "available_until" must also be set'
            )
        
        if available_until and not available_from:
            self.errors.append(
                f'{prefix}: If "available_until" is set, "available_from" must also be set'
            )
        
        if available_from and available_until and available_until < available_from:
            self.errors.append(
                f'{prefix}: "available_until" cannot be earlier than "available_from"'
            )
        
        if available_until and 'eol' in fields and not fields['eol']:
            self.errors.append(
                f'{prefix}: If "available_until" is set, "eol" must not be empty'
            )
        
        # Text fields
        self.check_string_field(fields, 'description_internal', prefix)
        self.check_translation_fields(fields, 'description', prefix, required=True)
        self.check_translation_fields(fields, 'usage_information', prefix)
        self.check_translation_fields(fields, 'requirements', prefix)
        self.check_translation_fields(fields, 'details', prefix)
        self.check_translation_fields(fields, 'options', prefix)
        
        # Email and URL
        self.check_email_field(fields, 'contact', prefix)
        self.check_url_field(fields, 'url', prefix)
        
        # EOL text
        self.check_string_field(fields, 'eol', prefix)
        
        # Check unique (service, version) combination
        if 'service' in fields and 'version' in fields:
            service_id = fields['service']
            version = fields['version']
            unique_key = f'{service_id}:{version}'
            if unique_key in self.unique_values['ServiceCatalogue.servicerevision']['service_version']:
                self.errors.append(
                    f'{prefix}: Duplicate (service, version) combination: '
                    f'service={service_id}, version="{version}"'
                )
            else:
                self.unique_values['ServiceCatalogue.servicerevision']['service_version'].add(unique_key)

    def validate_availability(self, fields, pk, prefix):
        """Validate Availability fields."""
        self.check_foreign_key(fields, 'servicerevision', 'ServiceCatalogue.servicerevision', prefix, required=True)
        self.check_foreign_key(fields, 'clientele', 'ServiceCatalogue.clientele', prefix, required=True)
        self.check_string_field(fields, 'comment', prefix)
        
        # Boolean field
        if 'charged' in fields and fields['charged'] is not None:
            if not isinstance(fields['charged'], bool):
                self.errors.append(f'{prefix}: Field "charged" must be a boolean')
        
        # Decimal fee
        self.check_decimal_field(fields, 'fee', prefix)
        
        # Fee unit (optional foreign key)
        self.check_foreign_key(fields, 'fee_unit', 'ServiceCatalogue.feeunit', prefix)
        
        # Business logic: if fee > 0, fee_unit should be set
        if 'fee' in fields and fields['fee']:
            try:
                fee_value = Decimal(fields['fee'])
                if fee_value > 0 and ('fee_unit' not in fields or fields['fee_unit'] is None):
                    self.warnings.append(
                        f'{prefix}: Fee is set to {fields["fee"]} but "fee_unit" is null. '
                        f'Consider setting a fee unit.'
                    )
            except (InvalidOperation, TypeError):
                pass  # Already caught by check_decimal_field
        
        # Check unique (servicerevision, clientele) combination
        if 'servicerevision' in fields and 'clientele' in fields:
            sr_id = fields['servicerevision']
            cl_id = fields['clientele']
            unique_key = f'{sr_id}:{cl_id}'
            if unique_key in self.unique_values['ServiceCatalogue.availability']['servicerevision_clientele']:
                self.errors.append(
                    f'{prefix}: Duplicate (servicerevision, clientele) combination: '
                    f'servicerevision={sr_id}, clientele={cl_id}'
                )
            else:
                self.unique_values['ServiceCatalogue.availability']['servicerevision_clientele'].add(unique_key)
