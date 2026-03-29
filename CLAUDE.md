# NPPES MCP Server - Project Rules

## MCP Tool Development Rule

**When adding new tools or modifying existing ones, ensure MCP tool parameters match the underlying API client parameters.**

### Why This Matters
- Tools that wrap API clients must expose ALL parameters the client supports
- Missing parameters = silent feature loss (users don't know what's missing)
- This issue was discovered after `search_providers` had `first_name`, `last_name`, `organization_name` but MCP tool only had `name`

### How to Apply

When creating or modifying a tool that wraps an API client:

1. **Compare signatures** - List all parameters in the API client method vs the MCP tool
2. **Check each parameter** - Ensure every API parameter is exposed in the MCP tool
3. **Test parameter passthrough** - Write a test that verifies the parameter is passed to the API client

### Example Pattern

```python
# API client has: first_name, last_name, organization_name, city, state, specialty, zip_code
# MCP tool must have ALL of these

async def my_tool(
    # Copy ALL params from API client
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    organization_name: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    specialty: Optional[str] = None,  # <-- Don't forget this!
    zip_code: Optional[str] = None,
    # Plus internal/testing params
    nppes_client: Optional[NPPESClient] = None,
):
    await nppes_client.search_by_name_and_fields(
        first_name=first_name,
        last_name=last_name,
        # ... pass ALL params through
        specialty=specialty,  # <-- Pass through!
    )
```

### Test Template

```python
@pytest.mark.asyncio
async def test_tool_passes_specialty_to_api():
    """Test that tool passes specialty parameter to NPPES API."""
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.search_by_name_and_fields = AsyncMock(return_value=[...])

    result = await my_tool(
        first_name="John",
        specialty="207Q00000X",  # Test the parameter
        nppes_client=mock_nppes,
        ...
    )

    # Verify it was passed
    call_kwargs = mock_nppes.search_by_name_and_fields.call_args.kwargs
    assert call_kwargs.get("specialty") == "207Q00000X"
```