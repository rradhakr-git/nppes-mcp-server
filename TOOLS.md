# NPPES MCP Server - Tools Reference

Complete reference for all available MCP tools, their parameters, and usage examples.

---

## Table of Contents

1. [search_providers](#search_providers) - Search NPPES registry for healthcare providers
2. [resolve_taxonomy](#resolve_taxonomy) - Resolve medical specialty codes
3. [semantic_search](#semantic_search) - Natural language provider search
4. [get_provider_by_npi](#get_provider_by_npi) - Get provider by NPI number
5. [validate_npi](#validate_npi) - Validate an NPI number
6. [get_npi_for_provider](#get_npi_for_provider) - Find NPI by provider name

---

## search_providers

Search the NPPES registry for healthcare providers with caching.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | string | Optional | - | Provider first or last name (partial matches supported) |
| `city` | string | Optional | - | City name filter (e.g., "New Haven") |
| `state` | string | Optional | - | Two-letter state code (e.g., "CT", "CA", "NY") |
| `specialty` | string | Optional | - | Taxonomy code or specialty name (e.g., "Cardiology", "207Q00000X") |
| `limit` | integer | Optional | 10 | Maximum results to return (1-200) |

### Validation Patterns

- **state**: Must be 2 uppercase letters (e.g., "CT", "NY")
- **limit**: Integer between 1 and 200

### Examples

**Search by name and state:**
```json
{
  "name": "Smith",
  "state": "CT",
  "limit": 5
}
```

**Search by specialty and city:**
```json
{
  "specialty": "Cardiology",
  "city": "New Haven",
  "state": "CT"
}
```

**Search by name only:**
```json
{
  "name": "Johnson",
  "limit": 20
}
```

### Response

Returns array of provider objects with fields:
- `number` - NPI (10-digit identifier)
- `basic` - Name, credentials, etc.
- `addresses` - Practice and mailing addresses
- `taxonomies` - Specialties and license info
- `endpoints` - Digital contact info

---

## resolve_taxonomy

Resolve a medical taxonomy code to its description, or search by natural language.

Use this tool when you need to:
- Find the official taxonomy code for a specialty (e.g., "cardiologist" → "207Q00000X")
- Get the description for a known taxonomy code
- Look up specialized provider types

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `code` | string | Optional* | - | Specific taxonomy code (e.g., "207Q00000X") |
| `query` | string | Optional* | - | Natural language query (e.g., "heart doctor", "pediatrician") |
| `top_k` | integer | Optional | 5 | Number of results to return for semantic search |
| `min_score` | number | Optional | 0.0 | Minimum similarity score (0.0-1.0) for semantic matches |

*At least one of `code` or `query` is required.

### Validation Patterns

- **code**: Taxonomy codes are 10 characters, alphanumeric (e.g., "207Q00000X")
- **top_k**: Positive integer
- **min_score**: Float between 0.0 and 1.0

### Examples

**Lookup by code:**
```json
{
  "code": "207Q00000X"
}
```

**Search by natural language:**
```json
{
  "query": "heart doctor"
}
```

**Search with options:**
```json
{
  "query": "eye surgery",
  "top_k": 3,
  "min_score": 0.5
}
```

### Response

Returns taxonomy object:
```json
{
  "code": "207Q00000X",
  "classification": "Family Medicine",
  "specialization": "",
  "display_name": "Family Medicine"
}
```

Or empty object `{}` if no match found.

### Common Taxonomy Codes

| Code | Classification |
|------|----------------|
| 207Q00000X | Family Medicine |
| 208D00000X | General Practice |
| 207RC0000X | Cardiovascular Disease |
| 207RG0100X | Gastroenterology |
| 208000000X | Pediatrics |
| 207RP1001X | Pulmonary Disease |
| 204E00000X | Oral and Maxillofacial Surgery |

---

## semantic_search

Search for providers using natural language query with RAG-based taxonomy matching.

Use this tool when you need to:
- Search using conversational descriptions ("I need a heart doctor in Connecticut")
- Find specialists when you don't know the exact taxonomy code
- Get more intelligent specialty matching than keyword search

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | **Required** | - | Natural language query (e.g., "cardiologist in Connecticut") |
| `state` | string | Optional | - | Optional state filter (2-letter code) |
| `city` | string | Optional | - | Optional city filter |
| `top_k` | integer | Optional | 5 | Number of taxonomy codes to search |
| `min_score` | number | Optional | 0.0 | Minimum similarity score for taxonomy matching |

### Validation Patterns

- **query**: Non-empty string describing the specialty needed
- **state**: 2 uppercase letters
- **top_k**: Integer between 1 and 20
- **min_score**: Float between 0.0 and 1.0

### Examples

**Basic natural language search:**
```json
{
  "query": "I need a cardiologist"
}
```

**Search with location filter:**
```json
{
  "query": "heart doctor",
  "state": "CT",
  "city": "New Haven"
}
```

**Search with similarity threshold:**
```json
{
  "query": "children's doctor",
  "state": "CA",
  "min_score": 0.7
}
```

### How It Works

1. The query is embedded and matched against taxonomy descriptions using semantic similarity
2. Top matching taxonomy codes are identified
3. NPPES API is queried with those taxonomy codes
4. Results are deduplicated and returned

### Response

Returns array of provider objects (same structure as `search_providers`).

---

## get_provider_by_npi

Get complete provider record by NPI number.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `npi` | string | **Required** | - | 10-digit National Provider Identifier |

### Validation Patterns

- **npi**: Must be exactly 10 digits (e.g., "1000000023")
  - Must pass ISO 7064 Mod 97-10 checksum validation
  - First digit is always 1 or 2 (individual vs organization)

### Examples

```json
{
  "npi": "1000000023"
}
```

### Response

```json
{
  "found": true,
  "npi": "1000000023",
  "data": {
    "number": "1000000023",
    "basic": {
      "first_name": "John",
      "last_name": "Smith",
      "credential": "MD",
      "sole_proprietor": "NO"
    },
    "addresses": [...],
    "taxonomies": [...]
  }
}
```

Or on not found:
```json
{
  "found": false,
  "npi": "1000000023"
}
```

Or on invalid NPI:
```json
{
  "error": "NPI must be exactly 10 digits",
  "npi": "invalid"
}
```

---

## validate_npi

Validate an NPI number - checks format, checksum, and registry existence.

Use this tool when you need to:
- Verify an NPI is valid before using it
- Check if an NPI is active in the registry
- Validate NPI format for data entry

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `npi` | string | **Required** | - | 10-digit National Provider Identifier |

### Validation Patterns

- **npi**: Must be exactly 10 digits
  - Must pass ISO 7064 Mod 97-10 checksum: `(NPI * 100 + 24) % 97 == 1`
  - Verified against active NPPES registry

### Examples

```json
{
  "npi": "1000000023"
}
```

### Response

**Valid and active:**
```json
{
  "valid": true,
  "npi": "1000000023",
  "active": true
}
```

**Invalid format:**
```json
{
  "valid": false,
  "npi": "12345",
  "error": "NPI must be exactly 10 digits"
}
```

**Valid format but not in registry:**
```json
{
  "valid": true,
  "npi": "9999999999",
  "active": false,
  "error": "NPI not found in registry"
}
```

**Failed checksum:**
```json
{
  "valid": false,
  "npi": "1234567890",
  "error": "Invalid NPI checksum"
}
```

---

## get_npi_for_provider

Search for a provider's NPI by name and optional location filters.

Use this tool when you need to:
- Find an NPI when you know the provider's name
- Locate a provider by name and city/state

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `first_name` | string | Optional* | - | Provider first name |
| `last_name` | string | Optional* | - | Provider last name |
| `organization_name` | string | Optional* | - | Organization/facility name (for hospitals, clinics) |
| `city` | string | Optional | - | City filter |
| `state` | string | Optional | - | State filter (2-letter code) |
| `zip_code` | string | Optional | - | ZIP code filter (5 digits or ZIP+4) |

*At least one of `first_name`, `last_name`, or `organization_name` is required.

### Validation Patterns

- **state**: 2 uppercase letters
- **zip_code**: 5 digits or ZIP+4 format (e.g., "06510", "06510-1234")

### Examples

**Search by individual name:**
```json
{
  "first_name": "John",
  "last_name": "Smith"
}
```

**Search by organization:**
```json
{
  "organization_name": "Yale New Haven Hospital",
  "state": "CT"
}
```

**Search with full location:**
```json
{
  "first_name": "Jane",
  "last_name": "Doe",
  "city": "New Haven",
  "state": "CT",
  "zip_code": "06510"
}
```

### Response

**Found:**
```json
{
  "found": true,
  "npi": "1000000023",
  "data": {
    "number": "1000000023",
    "basic": { ... },
    "addresses": [ ... ]
  }
}
```

**Not found:**
```json
{
  "found": false,
  "error": "No provider found matching the given criteria"
}
```

**Missing required parameter:**
```json
{
  "error": "At least one of first_name, last_name, or organization_name is required",
  "found": false
}
```

---

## Common Response Patterns

### Error Responses

All tools return errors in a consistent format:

```json
{
  "error": "Human-readable error message",
  "details": "Additional context (optional)"
}
```

### Rate Limiting

The NPPES API has rate limits. This server implements:
- **Caching**: 1-hour TTL for provider searches (`3600` seconds)
- **Validation caching**: 24-hour TTL for NPI validations (`86400` seconds)
- **Redis backend**: Configurable via `REDIS_URL` environment variable

### State Code Reference

Common two-letter state codes used across tools:

| Code | State | Code | State |
|------|-------|------|-------|
| AL | Alabama | MT | Montana |
| AK | Alaska | NE | Nebraska |
| AZ | Arizona | NV | Nevada |
| AR | Arkansas | NH | New Hampshire |
| CA | California | NJ | New Jersey |
| CO | Colorado | NM | New Mexico |
| CT | Connecticut | NY | New York |
| DC | District of Columbia | NC | North Carolina |
| DE | Delaware | ND | North Dakota |
| FL | Florida | OH | Ohio |
| GA | Georgia | OK | Oklahoma |
| HI | Hawaii | OR | Oregon |
| ID | Idaho | PA | Pennsylvania |
| IL | Illinois | RI | Rhode Island |
| IN | Indiana | SC | South Carolina |
| IA | Iowa | SD | South Dakota |
| KS | Kansas | TN | Tennessee |
| KY | Kentucky | TX | Texas |
| LA | Louisiana | UT | Utah |
| ME | Maine | VT | Vermont |
| MD | Maryland | VA | Virginia |
| MA | Massachusetts | WA | Washington |
| MI | Michigan | WV | West Virginia |
| MN | Minnesota | WI | Wisconsin |
| MS | Mississippi | WY | Wyoming |
| MO | Missouri | PR | Puerto Rico |

---

## Tool Selection Guide

| Task | Use This Tool |
|------|---------------|
| "Find doctors named Smith in CT" | `search_providers` |
| "What does taxonomy code 207Q00000X mean?" | `resolve_taxonomy` |
| "Find a heart doctor near me" | `semantic_search` |
| "Get details for NPI 1000000023" | `get_provider_by_npi` |
| "Is 1000000023 a valid NPI?" | `validate_npi` |
| "What's Dr. John Smith's NPI?" | `get_npi_for_provider` |
| "What taxonomy code is 'cardiologist'?" | `resolve_taxonomy` |

---

## Environment Configuration

Key environment variables affecting tool behavior:

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Cache backend URL |
| `CACHE_TTL_SECONDS` | `3600` | Default cache TTL |
| `NPPES_API_URL` | `https://npiregistry.cms.hhs.gov/api` | NPPES API endpoint |
| `REQUEST_TIMEOUT_SECONDS` | `30` | API request timeout |
