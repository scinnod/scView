# Service Catalogue Fixtures

This directory contains JSON fixture files for populating the Service Catalogue database with initial or test data.

## Table of Contents

- [Overview](#overview)
- [Data Model and Relationships](#data-model-and-relationships)
- [Fixture Format Specification](#fixture-format-specification)
- [Field Specifications by Model](#field-specifications-by-model)
- [Translation Fields](#translation-fields)
- [Validation Rules](#validation-rules)
- [Creating New Fixtures](#creating-new-fixtures)
- [Loading Fixtures](#loading-fixtures)
- [Validating Fixtures](#validating-fixtures)
- [AI/LLM Guidance](#aillm-guidance-for-generating-fixtures)

## Overview

Fixtures are JSON files that contain serialized database records. They are used to:
- Populate a new database with initial data
- Provide test data for development
- Share sample data between installations
- Backup and restore specific datasets

**LLM/AI Tip:** This README is designed to serve as comprehensive instructions for LLMs generating fixture files. Point an AI assistant to this file when generating service catalogue data from institutional documentation. Always validate generated fixtures before loading:

```bash
docker-compose exec itsm python manage.py validate_fixtures <path_to_fixture.json>
```

## Data Model and Relationships

The Service Catalogue uses a hierarchical relational model:

```
ServiceCategory (top level)
    └── Service (belongs to one category)
        └── ServiceRevision (versioned details of a service)
            └── Availability (many-to-many through table)
                ├── links to: Clientele (target user groups)
                └── links to: FeeUnit (optional, for pricing)

ServiceProvider (independent, many-to-many with Service)
Clientele (independent, defines user groups)
FeeUnit (independent, defines charging units)
```

### Key Relationships

1. **ServiceCategory → Service**: One-to-many (a category has many services)
2. **Service → ServiceRevision**: One-to-many (a service has many versions/revisions)
3. **ServiceRevision → Availability → Clientele**: Many-to-many (a revision can be available to multiple user groups with different pricing)
4. **Service → ServiceProvider**: Many-to-many (a service can be provided by multiple teams)
5. **Availability → FeeUnit**: Many-to-one (optional, for defining fee units)

### Loading Order

**CRITICAL**: Due to foreign key constraints, fixtures must be loaded in dependency order:

1. **ServiceCategory** (no dependencies)
2. **Clientele** (no dependencies)
3. **FeeUnit** (no dependencies)
4. **ServiceProvider** (no dependencies)
5. **Service** (depends on ServiceCategory)
6. **ServiceRevision** (depends on Service)
7. **Availability** (depends on ServiceRevision, Clientele, and optionally FeeUnit)

## Fixture Format Specification

Fixtures follow Django's JSON fixture format:

```json
[
    {
        "model": "ServiceCatalogue.modelname",
        "pk": 1,
        "fields": {
            "field1": "value1",
            "field2": "value2"
        }
    }
]
```

### Format Rules

- **Top level**: Array of objects
- **model**: String in format `"ServiceCatalogue.modelname"` (lowercase model name)
- **pk**: Integer, unique primary key for this model type
- **fields**: Object containing all field values

### Data Types

- **String**: `"text value"`
- **Integer**: `123` (no quotes)
- **Decimal**: `"123.45"` (quoted string for precise decimal handling)
- **Boolean**: `true` or `false` (lowercase, no quotes)
- **Date**: `"YYYY-MM-DD"` format (e.g., `"2024-01-15"`)
- **Email**: `"user@example.com"` (string)
- **URL**: `"https://example.com"` (string)
- **Foreign Key**: Integer ID referencing the pk of related object
- **null**: `null` (lowercase, no quotes) for optional fields

## Field Specifications by Model

### ServiceCategory

Defines categories for organizing services (e.g., "Communication", "Computing", "Storage").

```json
{
    "model": "ServiceCatalogue.servicecategory",
    "pk": 1,
    "fields": {
        "order": "10",
        "name_de": "Kommunikation",
        "name_en": "Communication",
        "acronym": "COMM",
        "description_de": "Dienste für Kommunikation und Zusammenarbeit",
        "description_en": "Services for communication and collaboration",
        "responsible": "John Doe"
    }
}
```

**Fields:**
- `order` (string, optional): Sort order (e.g., "10", "20", "30")
- `name_de` (string, **required**): German category name
- `name_en` (string, **required**): English category name
- `acronym` (string, **required**, unique, max 10 chars): Short identifier (e.g., "COMM")
- `description_de` (string, optional): German description
- `description_en` (string, optional): English description
- `responsible` (string, optional, max 80 chars): Category owner/manager name

### Clientele

Defines target user groups (e.g., "Students", "Staff", "Researchers").

```json
{
    "model": "ServiceCatalogue.clientele",
    "pk": 1,
    "fields": {
        "order": "10",
        "name_de": "Studierende",
        "name_en": "Students",
        "acronym": "STUDENT"
    }
}
```

**Fields:**
- `order` (string, optional): Sort order
- `name_de` (string, **required**): German name
- `name_en` (string, **required**): English name
- `acronym` (string, **required**, unique, max 10 chars): Identifier

### FeeUnit

Defines units for charging fees (e.g., "per month", "per GB").

```json
{
    "model": "ServiceCatalogue.feeunit",
    "pk": 1,
    "fields": {
        "name_de": "pro Monat",
        "name_en": "per month"
    }
}
```

**Fields:**
- `name_de` (string, **required**): German unit name
- `name_en` (string, **required**): English unit name

### ServiceProvider

Defines organizational units providing services (e.g., "IT Services", "Infrastructure Team").

```json
{
    "model": "ServiceCatalogue.serviceprovider",
    "pk": 1,
    "fields": {
        "hierarchy": "1.0",
        "name": "IT Services",
        "acronym": "IT"
    }
}
```

**Fields:**
- `hierarchy` (string, **required**, max 10 chars): Hierarchical position (e.g., "1.0", "1.1", "2.0")
  - Use dots to indicate hierarchy: "1.0" > "1.1" > "1.1.1"
- `name` (string, **required**, max 80 chars): Provider name
- `acronym` (string, optional, max 10 chars): Short identifier

### Service

Defines a service offering (e.g., "Email Service", "Cloud Storage").

```json
{
    "model": "ServiceCatalogue.service",
    "pk": 1,
    "fields": {
        "order": "10",
        "category": 1,
        "name_de": "E-Mail-Service",
        "name_en": "Email Service",
        "acronym": "EMAIL",
        "purpose_de": "Sichere und zuverlässige E-Mail-Kommunikation",
        "purpose_en": "Secure and reliable email communication",
        "responsible": "Jane Smith",
        "service_providers": [1, 2]
    }
}
```

**Fields:**
- `order` (string, optional): Sort order within category
- `category` (integer, **required**): Foreign key to ServiceCategory pk
- `name_de` (string, **required**, max 80 chars): German service name
- `name_en` (string, **required**, max 80 chars): English service name
- `acronym` (string, **required**, max 10 chars): Short identifier
  - Must be unique within category
- `purpose_de` (string, **required**): German description of main purpose/value
- `purpose_en` (string, **required**): English description of main purpose/value
- `responsible` (string, optional, max 80 chars): Service owner name
- `service_providers` (array of integers, optional): Foreign keys to ServiceProvider pks

**Unique Constraint:** Combination of `category` + `acronym` must be unique.

**Computed Key:** Automatically generated as `{category.acronym}-{acronym}` (e.g., "COMM-EMAIL")

### ServiceRevision

Defines versioned details of a service. Each service can have multiple revisions.

```json
{
    "model": "ServiceCatalogue.servicerevision",
    "pk": 1,
    "fields": {
        "service": 1,
        "version": "2.0",
        "keywords_de": "E-Mail Outlook Exchange Microsoft 365",
        "keywords_en": "email outlook exchange microsoft 365",
        "submitted": false,
        "listed_from": "2024-01-01",
        "available_from": "2024-01-01",
        "description_internal": "Exchange Online, 50GB mailboxes, 90-day retention",
        "description_de": "Professioneller E-Mail-Service...",
        "description_en": "Professional email service...",
        "usage_information_de": "Bitte beachten Sie...",
        "usage_information_en": "Please note...",
        "requirements_de": "Institutionelles Benutzerkonto erforderlich",
        "requirements_en": "Institutional account required",
        "details_de": "24/7 Verfügbarkeit...",
        "details_en": "24/7 availability...",
        "options_de": "Zusätzlicher Speicher verfügbar",
        "options_en": "Additional storage available",
        "contact": "email-support@example.com",
        "url": "https://webmail.example.com",
        "listed_until": null,
        "available_until": null,
        "eol": null
    }
}
```

**Fields:**
- `service` (integer, **required**): Foreign key to Service pk
- `version` (string, **required**, max 10 chars): Version identifier (e.g., "1.0", "2.0", "2.1")
  - Must be unique per service
- `keywords_de` (string, optional): German search keywords (space-separated)
- `keywords_en` (string, optional): English search keywords (space-separated)
- `submitted` (boolean, default: `false`): Whether submitted for staff review
- `listed_from` (date, optional): Date when service appears in public catalogue (YYYY-MM-DD)
- `available_from` (date, optional): Date when service becomes available to users
- `description_internal` (string, optional): Internal notes (configuration, technical details)
- `description_de` (string, **required**): German service description (main text)
- `description_en` (string, **required**): English service description (main text)
- `usage_information_de` (string, optional): German important usage notes (compliance, regulations)
- `usage_information_en` (string, optional): English important usage notes
- `requirements_de` (string, optional): German prerequisites for using service
- `requirements_en` (string, optional): English prerequisites
- `details_de` (string, optional): German detailed information (SLA, support hours, etc.)
- `details_en` (string, optional): English detailed information
- `options_de` (string, optional): German available options/customizations
- `options_en` (string, optional): English available options
- `contact` (email, optional, max 80 chars): Contact email for service requests
- `url` (URL, optional, max 250 chars): Direct link to service
- `listed_until` (date, optional): Date when service is removed from catalogue
- `available_until` (date, optional): End-of-life date (service discontinued)
- `eol` (string, optional): End-of-life instructions/migration path

**Unique Constraint:** Combination of `service` + `version` must be unique.

**Computed Key:** Automatically generated as `{service.key}-{version}` (e.g., "COMM-EMAIL-2.0")

### Text Formatting in ServiceRevision Fields

Certain text fields in ServiceRevision support lightweight formatting syntax that is rendered in both the HTML catalogue and PDF/LaTeX exports. The syntax is kept deliberately simple so that the raw text remains human-readable.

**Supported formatting:**

| Syntax | Example | Result |
|--------|---------|--------|
| Bold | `**important**` | **important** |
| Italic | `*note*` | *note* |
| Unordered list | `- item` (one per line) | Bullet list |
| Ordered list | `1. step` (one per line) | Numbered list |
| Internal link | `[[COMM-EMAIL]]` | Link to service |
| URL | `https://example.com` | Clickable link |

**Fields supporting full formatting** (bold, italic, lists, URLs, internal links):
`description_internal`, `usage_information`, `requirements`, `details`, `options`, `service_level`, `eol`

**Fields with restricted formatting** (line breaks and internal links only): 
`description` (both `_de` and `_en`)

The `purpose` field on **Service** does not support any formatting — it is rendered as plain text only.

**Example with formatting in a fixture:**
```json
{
    "description_en": "This service provides **secure** file storage.\n\nKey features:\n- 100 GB default quota\n- *Automatic* daily backups\n- Integration with [[COMM-EMAIL]]\n\nMore info: https://storage.example.com",
    "requirements_en": "1. Valid institutional account\n2. Completed IT security training"
}
```

**Note:** Use `\n` for newlines in JSON strings. Each list item must start on a new line. All items in a block must use the same marker type (all bullets or all numbers).

### Availability

Links a ServiceRevision to target user groups (Clientele) with pricing information.

```json
{
    "model": "ServiceCatalogue.availability",
    "pk": 1,
    "fields": {
        "servicerevision": 1,
        "clientele": 1,
        "comment": "Free access for students as part of institutional subscription",
        "charged": false,
        "fee": "0.00",
        "fee_unit": null
    }
}
```

**Fields:**
- `servicerevision` (integer, **required**): Foreign key to ServiceRevision pk
- `clientele` (integer, **required**): Foreign key to Clientele pk
- `comment` (string, optional): Additional information about availability/pricing
- `charged` (boolean, default: `false`): Whether this availability incurs charges
- `fee` (decimal, default: `"0.00"`): Fee amount (quoted string, 2 decimal places)
- `fee_unit` (integer, optional): Foreign key to FeeUnit pk (required if fee > 0)

**Unique Constraint:** Combination of `servicerevision` + `clientele` must be unique.

**Examples:**
```json
// Free for students
{"servicerevision": 1, "clientele": 1, "fee": "0.00", "fee_unit": null}

// 10 EUR per month for researchers
{"servicerevision": 1, "clientele": 3, "fee": "10.00", "fee_unit": 1}

// 0.50 EUR per GB over quota
{"servicerevision": 2, "clientele": 3, "comment": "Fee applies per GB over quota", "fee": "0.50", "fee_unit": 2}
```

## Translation Fields

The following models use **django-modeltranslation** for multilingual support:

- **ServiceCategory**: `name`, `description`
- **Service**: `name`, `purpose`
- **ServiceRevision**: `keywords`, `description`, `requirements`, `usage_information`, `details`, `options`
- **Clientele**: `name`
- **FeeUnit**: `name`

### Translation Field Naming

For each translated field, two database fields exist:
- `fieldname_de`: German version
- `fieldname_en`: English version

**Example:**
```json
{
    "name_de": "E-Mail-Service",
    "name_en": "Email Service"
}
```

### Translation Requirements

- **Best practice: Provide both `_de` and `_en` versions** for all translated fields
- Use `null` for optional translated fields if not available in one language
- Do NOT use the base field name (e.g., `name`) in fixtures - always use `name_de` and `name_en`

### Translation Fallback Behavior

The Service Catalogue uses **django-modeltranslation** which provides automatic language fallback:

- **If only one language is defined** (e.g., only `name_en` is provided and `name_de` is `null`), the system will automatically use the available language for both German and English users
- **Fallback order**: If a field is `null` in the requested language, the system falls back to the other defined language
- **This means**: You can provide content in just one language initially, and it will work for all users

**Example with fallback:**
```json
{
    "name_de": null,
    "name_en": "Email Service"
}
```
→ Both German and English users will see "Email Service" until a German translation is added.

**Recommended approach for AI/LLM generation:**
- If source documentation is only available in one language, populate both `_de` and `_en` fields with the same content
- Alternatively, populate only the available language field and set the other to `null` (fallback will handle it)
- If capable of translation, generate appropriate translations for both languages

## Validation Rules

### Date Validation

For **ServiceRevision**:
1. If `listed_until` is set, `listed_from` must also be set
2. `listed_until` must be >= `listed_from`
3. If `listed_until` is set, `available_until` must also be set
4. If `available_until` is set, `available_from` must also be set
5. `available_until` must be >= `available_from`
6. If `available_until` is set, `eol` must not be empty

### Unique Constraints

1. **ServiceCategory.acronym**: Must be globally unique
2. **Clientele.acronym**: Must be globally unique
3. **Service**: `(category, acronym)` combination must be unique
4. **ServiceRevision**: `(service, version)` combination must be unique
5. **Availability**: `(servicerevision, clientele)` combination must be unique

### Foreign Key Integrity

- All foreign key references must point to existing primary keys
- Load parent models before child models (see Loading Order)

### Field Length Limits

- `acronym`: 10 characters maximum
- `name`, `responsible`, `contact`: 80 characters maximum
- `hierarchy`, `order`, `version`: 10 characters maximum
- `url`: 250 characters maximum
- Text fields (`description`, `details`, etc.): No practical limit but keep reasonable

### Required Fields

Each model has specific required fields (marked **required** above). Use `null` for optional fields.

## Creating New Fixtures

### Step-by-Step Process

1. **Plan your data structure**
   - Identify categories (typically 5-15)
   - Define user groups (typically 3-6)
   - List services per category
   - Define pricing units if needed

2. **Create independent entities first**
   ```json
   [
       // ServiceCategories
       {"model": "ServiceCatalogue.servicecategory", "pk": 1, "fields": {...}},
       {"model": "ServiceCatalogue.servicecategory", "pk": 2, "fields": {...}},
       
       // Clientele
       {"model": "ServiceCatalogue.clientele", "pk": 1, "fields": {...}},
       {"model": "ServiceCatalogue.clientele", "pk": 2, "fields": {...}},
       
       // FeeUnits (if needed)
       {"model": "ServiceCatalogue.feeunit", "pk": 1, "fields": {...}},
       
       // ServiceProviders (if needed)
       {"model": "ServiceCatalogue.serviceprovider", "pk": 1, "fields": {...}}
   ]
   ```

3. **Add services**
   ```json
   [
       {
           "model": "ServiceCatalogue.service",
           "pk": 1,
           "fields": {
               "category": 1,  // Reference to ServiceCategory pk
               "acronym": "EMAIL",
               "name_de": "...",
               "name_en": "...",
               "purpose_de": "...",
               "purpose_en": "..."
           }
       }
   ]
   ```

4. **Add service revisions**
   ```json
   [
       {
           "model": "ServiceCatalogue.servicerevision",
           "pk": 1,
           "fields": {
               "service": 1,  // Reference to Service pk
               "version": "1.0",
               "description_de": "...",
               "description_en": "...",
               "listed_from": "2024-01-01",
               "available_from": "2024-01-01"
           }
       }
   ]
   ```

5. **Add availability records**
   ```json
   [
       {
           "model": "ServiceCatalogue.availability",
           "pk": 1,
           "fields": {
               "servicerevision": 1,  // Reference to ServiceRevision pk
               "clientele": 1,  // Reference to Clientele pk
               "fee": "0.00",
               "fee_unit": null
           }
       }
   ]
   ```

### Primary Key Management

- **Use sequential integers** starting from 1 for each model type
- **Maintain unique pks** within each model type
- **Track your pk assignments** to avoid conflicts
- For relationships, reference the pk values you assigned

### Best Practices

1. **Use meaningful order values**: "10", "20", "30" allows inserting items later
2. **Keep acronyms short and descriptive**: "EMAIL", "CLOUD", "HPC"
3. **Provide comprehensive descriptions**: Users rely on these for understanding services
4. **Include keywords for searchability**: Think about what terms users might search
5. **Set realistic dates**: Use actual or planned deployment dates
6. **Add comments to availabilities**: Explain pricing, restrictions, or special conditions
7. **Use consistent formatting**: Makes maintenance easier
8. **Validate before loading**: Use the validation command (see below)

## Loading Fixtures

### Using Django's loaddata Command

```bash
# Load all fixtures in order (recommended)
python manage.py loaddata apps/itsm/ServiceCatalogue/fixtures/initial_test_data.json

# Load multiple specific files
python manage.py loaddata clientele servicecategory services
```

### Using populate_test_data Command

The Service Catalogue includes a custom management command:

```bash
# Populate new database with test data
python manage.py populate_test_data

# Force reload (WARNING: deletes existing data)
python manage.py populate_test_data --force
```

This command:
- Checks if database is already populated
- Validates user existence (requires superuser)
- Loads permission groups
- Loads service catalogue fixtures
- Provides detailed feedback on success/failure

### Troubleshooting Loading Issues

**Error: "DoesNotExist: ... matching query does not exist"**
- **Cause**: Foreign key reference to non-existent pk
- **Solution**: Check that referenced model exists and pk is correct

**Error: "UNIQUE constraint failed"**
- **Cause**: Duplicate pk or unique field value
- **Solution**: Ensure pks are unique and acronyms don't repeat

**Error: "IntegrityError"**
- **Cause**: Missing required field or invalid foreign key
- **Solution**: Check that all required fields are present and valid

**Error: "ValidationError"**
- **Cause**: Date validation or business logic violation
- **Solution**: Check date constraints (listed_until > listed_from, etc.)

## Validating Fixtures

### Using the validate_fixtures Command

A management command is available for thorough fixture validation:

```bash
# Validate specific fixture file
python manage.py validate_fixtures apps/itsm/ServiceCatalogue/fixtures/initial_test_data.json

# Validate all fixtures in directory
python manage.py validate_fixtures apps/itsm/ServiceCatalogue/fixtures/

# Validate with detailed output
python manage.py validate_fixtures initial_test_data.json --verbose
```

The validator checks:
- ✓ JSON syntax and structure
- ✓ Model existence in ServiceCatalogue app
- ✓ Required fields presence
- ✓ Field data types and formats
- ✓ Foreign key references (warns if referenced pk not found in same file)
- ✓ Unique constraints (within fixture file)
- ✓ Date logic constraints
- ✓ Field length limits
- ✓ Translation field completeness
- ✓ Email and URL format validation
- ✓ Decimal precision for fees

### Manual Validation

You can also validate manually:

```bash
# Check JSON syntax
python -m json.tool your_fixture.json > /dev/null

# Try loading to test database
python manage.py loaddata your_fixture.json --database test
```

### Pre-commit Validation

Consider adding fixture validation to your development workflow:

```bash
# Add to git pre-commit hook
python manage.py validate_fixtures apps/itsm/ServiceCatalogue/fixtures/*.json
```

## AI/LLM Guidance for Generating Fixtures

This section provides specific guidance for AI systems and Large Language Models to generate valid Service Catalogue fixtures from institutional documentation.

### Input Sources for AI Generation

AI systems can generate fixtures from:
1. **Institutional IT service documentation** (websites, PDFs, wikis)
2. **Service desk knowledge bases** (existing service descriptions)
3. **IT service catalogs** (from other systems or formats)
4. **Department websites** (descriptions of offered services)
5. **User guides and help documentation**
6. **Service Level Agreements** (SLAs)

### AI Generation Workflow

1. **Extract Service Information**
   - Identify distinct services offered by the institution
   - Group services into logical categories (5-15 categories typically)
   - Note target audiences (students, staff, researchers, external partners)
   - Extract pricing information if available

2. **Map to Data Model**
   - ServiceCategory ← Service groupings (e.g., "Communication", "Computing", "Storage")
   - Clientele ← Target user groups (e.g., "Students", "Staff", "Researchers")
   - Service ← Individual service offerings (e.g., "Email", "File Storage", "VPN")
   - ServiceRevision ← Service details and versions
   - Availability ← Service-to-user-group mappings with pricing

3. **Generate Primary Keys**
   - Use sequential integers starting from 1
   - Track pk assignments across related models
   - Ensure foreign keys reference valid pks

4. **Handle Translations**
   - If source is single-language, duplicate to both _de and _en fields
   - If bilingual source available, use appropriate translations
   - Generate translation if capable (use same meaning in both languages)

5. **Set Dates**
   - Use current date or "2024-01-01" for `listed_from` and `available_from`
   - Leave `listed_until`, `available_until`, and `eol` as `null` for active services

6. **Validate Output**
   - Check all foreign keys have valid references
   - Verify unique constraints (acronyms, combinations)
   - Ensure required fields are present
   - Validate date logic if dates are set

### AI-Specific Requirements

**CRITICAL for AI systems:**

1. **Always generate complete, loadable JSON**
   - Single JSON array containing all records
   - Proper JSON escaping for quotes in text
   - No trailing commas
   - Correct data types (integers unquoted, strings quoted)

2. **Follow dependency order**
   - Place ServiceCategory, Clientele, FeeUnit, ServiceProvider first
   - Then Service records
   - Then ServiceRevision records
   - Finally Availability records

3. **Use consistent pk numbering**
   - Start each model type at pk=1
   - Increment sequentially
   - Track and reference correctly in foreign keys

4. **Generate realistic acronyms**
   - Use 2-10 uppercase letters
   - Make them descriptive (EMAIL not SRV1)
   - Ensure uniqueness within constraints

5. **Create availability for all user groups**
   - Each ServiceRevision should have 1-4 Availability records
   - Cover different user groups (students, staff, researchers)
   - Use fee="0.00" when service is free

6. **Handle missing information gracefully**
   - Use `null` for optional fields when information unavailable
   - Generate reasonable defaults (e.g., contact email from institution domain)
   - Mark with comments where information is assumed

### AI Output Template

When generating fixtures, AI should produce:

```json
[
    {
        "model": "ServiceCatalogue.servicecategory",
        "pk": 1,
        "fields": {
            "order": "10",
            "name_de": "[German name or English name if German unavailable]",
            "name_en": "[English name]",
            "acronym": "[SHORT_ACRONYM]",
            "description_de": "[Comprehensive German description]",
            "description_en": "[Comprehensive English description]",
            "responsible": "[Name or null]"
        }
    },
    {
        "model": "ServiceCatalogue.clientele",
        "pk": 1,
        "fields": {
            "order": "10",
            "name_de": "[User group in German]",
            "name_en": "[User group in English]",
            "acronym": "[GROUP_ACRONYM]"
        }
    },
    {
        "model": "ServiceCatalogue.service",
        "pk": 1,
        "fields": {
            "order": "10",
            "category": 1,
            "name_de": "[Service name German]",
            "name_en": "[Service name English]",
            "acronym": "[SVC_ACRONYM]",
            "purpose_de": "[Why this service exists - German]",
            "purpose_en": "[Why this service exists - English]",
            "responsible": "[Service owner name or null]",
            "service_providers": []
        }
    },
    {
        "model": "ServiceCatalogue.servicerevision",
        "pk": 1,
        "fields": {
            "service": 1,
            "version": "1.0",
            "keywords_de": "[search keywords German space-separated]",
            "keywords_en": "[search keywords English space-separated]",
            "submitted": false,
            "listed_from": "2024-01-01",
            "available_from": "2024-01-01",
            "description_internal": "[Internal notes or null]",
            "description_de": "[Main service description German]",
            "description_en": "[Main service description English]",
            "usage_information_de": "[Compliance notes German or null]",
            "usage_information_en": "[Compliance notes English or null]",
            "requirements_de": "[Prerequisites German or null]",
            "requirements_en": "[Prerequisites English or null]",
            "details_de": "[SLA, support details German or null]",
            "details_en": "[SLA, support details English or null]",
            "options_de": "[Available options German or null]",
            "options_en": "[Available options English or null]",
            "contact": "[support@institution.domain]",
            "url": "[https://service.url or null]",
            "listed_until": null,
            "available_until": null,
            "eol": null
        }
    },
    {
        "model": "ServiceCatalogue.availability",
        "pk": 1,
        "fields": {
            "servicerevision": 1,
            "clientele": 1,
            "comment": "[Pricing notes or special conditions or null]",
            "charged": false,
            "fee": "0.00",
            "fee_unit": null
        }
    }
]
```

### AI Validation Checklist

Before outputting generated fixtures, AI should verify:

- [ ] Valid JSON syntax (use JSON validator)
- [ ] All models use correct format: `"ServiceCatalogue.modelname"`
- [ ] All pks are unique integers within each model type
- [ ] All foreign keys reference existing pks in the fixture
- [ ] All required fields are present (name_de, name_en, etc.)
- [ ] All acronyms are unique where required
- [ ] Dates use YYYY-MM-DD format
- [ ] Decimal values are quoted strings with 2 decimal places
- [ ] Boolean values are lowercase `true`/`false`
- [ ] URLs start with http:// or https://
- [ ] Email addresses contain @ symbol
- [ ] No trailing commas in JSON
- [ ] Translation fields use _de and _en suffixes
- [ ] ServiceRevision has at least one Availability record

### Common AI Mistakes to Avoid

1. **Using base field names instead of translated fields**
   - ❌ `"name": "Email"`
   - ✅ `"name_de": "E-Mail", "name_en": "Email"`

2. **Incorrect foreign key references**
   - ❌ `"category": "COMM"` (string)
   - ✅ `"category": 1` (integer pk)

3. **Missing required translations**
   - ❌ Only providing `name_en`
   - ✅ Providing both `name_de` and `name_en`

4. **Invalid decimal format**
   - ❌ `"fee": 10.50` (number)
   - ✅ `"fee": "10.50"` (quoted string)

5. **Duplicate acronyms**
   - ❌ Two ServiceCategory records with same acronym
   - ✅ Unique acronyms for each category

6. **Orphaned availabilities**
   - ❌ Availability with no matching ServiceRevision
   - ✅ Only create Availability for existing ServiceRevisions

## Examples

See `initial_test_data.json` in this directory for a complete, working example with:
- 4 ServiceCategories
- 4 Clientele groups  
- 4 FeeUnits
- 3 ServiceProviders
- 8 Services
- 8 ServiceRevisions
- 21 Availability records

This example demonstrates:
- Proper relationship hierarchies
- Translation field usage
- Free and paid service configurations
- Different pricing models (per month, per GB, per core-hour, per project)
- Multiple user groups per service
- Use of comments for pricing explanations

## Additional Resources

- Django fixtures documentation: https://docs.djangoproject.com/en/4.1/howto/initial-data/
- JSON validation tools: https://jsonlint.com/
- Service Catalogue models: `apps/itsm/ServiceCatalogue/models.py`
- Management commands: `apps/itsm/ServiceCatalogue/management/commands/`

## Support

For issues with fixtures or the Service Catalogue:
1. Check this README thoroughly
2. Validate your fixture with `validate_fixtures` command
3. Review the example fixture `initial_test_data.json`
4. Check model definitions in `models.py`
5. Consult Django fixtures documentation
