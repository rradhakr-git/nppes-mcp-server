"""
Realistic NPPES API response payloads for testing.
Based on actual api.cms.gov response structure.
"""

# Sample provider search result for valid state query
VALID_STATE_SEARCH_RESPONSE = {
    "result_count": 2,
    "results": [
        {
            "npi": "1234567890",
            "basic": {
                "first_name": "John",
                "last_name": "Smith",
                "middle_name": "A",
                "name_prefix": "Dr.",
                "credential": "MD",
                "organization_name": None,
                "sole_proprietor": "YES",
                "gender": "M",
                "status": "active"
            },
            "addresses": [
                {
                    "address_purpose": "LOCATION",
                    "address_type": "DOM",
                    "address_1": "123 Main Street",
                    "address_2": "Suite 100",
                    "city": "Hartford",
                    "state": "CT",
                    "postal_code": "06106",
                    "country_code": "US",
                    "telephone_number": "860-555-1234",
                    "fax_number": None
                }
            ],
            "taxonomies": [
                {
                    "code": "207Q00000X",
                    "desc": "Family Medicine",
                    "primary": True,
                    "state": "CT"
                }
            ],
            "other_identifiers": [],
            "created_date": "2007-01-01",
            "last_updated": "2023-06-15"
        },
        {
            "npi": "0987654321",
            "basic": {
                "first_name": "Jane",
                "last_name": "Doe",
                "middle_name": "M",
                "name_prefix": "Dr.",
                "credential": "MD",
                "organization_name": None,
                "sole_proprietor": "NO",
                "gender": "F",
                "status": "active"
            },
            "addresses": [
                {
                    "address_purpose": "LOCATION",
                    "address_type": "DOM",
                    "address_1": "456 Oak Avenue",
                    "address_2": None,
                    "city": "New Haven",
                    "state": "CT",
                    "postal_code": "06510",
                    "country_code": "US",
                    "telephone_number": "203-555-5678",
                    "fax_number": "203-555-5679"
                }
            ],
            "taxonomies": [
                {
                    "code": "208D00000X",
                    "desc": "General Practice",
                    "primary": True,
                    "state": "CT"
                }
            ],
            "other_identifiers": [],
            "created_date": "2010-03-15",
            "last_updated": "2022-09-20"
        }
    ]
}

# Empty result response (404-like - no providers found)
EMPTY_SEARCH_RESPONSE = {
    "result_count": 0,
    "results": []
}

# Server error response (503)
SERVER_ERROR_RESPONSE = {
    "Error": "Internal Server Error",
    "message": "The NPPES database is temporarily unavailable. Please try again later."
}

# Invalid request response (400)
INVALID_REQUEST_RESPONSE = {
    "Fault": {
        "faultstring": "Invalid parameter value",
        "detail": {
            "error_code": "BAD_REQUEST"
        }
    }
}