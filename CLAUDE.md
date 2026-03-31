# NPPES MCP Server — CLAUDE.md

> This file provides guidance for AI coding agents (Claude Code, Copilot, Cursor, etc.) working on this repository.

---

## Project Overview

**NPPES MCP Server** is a FastAPI-based [Model Context Protocol (MCP)](https://spec.modelcontextprotocol.io/) server that exposes tools for querying the US National Provider Identifier (NPI) Registry (NPPES). It supports natural-language provider search via a RAG pipeline over NUCC taxonomy codes.

- **MCP endpoint**: `POST /mcp` (JSON-RPC 2.0)
- **Protocol version**: `2024-11-05`
- **Server version**: `1.0.0`
- **License**: Apache 2.0

---

## Repository Structure

```
nppes-mcp-server/
├── app/
│   ├── main.py                  # FastAPI app, MCP endpoint, tool registry
│   ├── tools/                   # One file per MCP tool
│   │   ├── search_providers.py
│   │   ├── get_provider_by_npi.py
│   │   ├── validate_npi.py
│   │   ├── get_npi_for_provider.py
│   │   ├── resolve_taxonomy.py
│   │   └── semantic_search.py
│   ├── rag/
│   │   ├── index.py             # TaxonomyIndex (FAISS vector store)
│   │   └── embedder.py          # Embedder (paraphrase-MiniLM-L3-v2)
│   └── nppes_client.py          # Async NPPES API HTTP client (httpx)
├── models/
│   └── paraphrase-MiniLM-L3-v2/ # Bundled sentence-transformer model
├── tests/
│   ├── unit/                    # Fast unit tests (~63 tests)
│   ├── integration/             # Integration tests (~14 tests)
│   ├── contract/                # Schema/contract validation (schemathesis)
│   └── e2e/                     # Live server E2E tests (requires MCP_SERVER_URL)
├── scripts/                     # Utility scripts
├── .env.example                 # Environment variable template
├── Dockerfile                   # Production Docker image
├── render.yaml                  # Render.com deployment config
├── requirements.txt             # Production dependencies
├── requirements-dev.txt         # Dev/test dependencies
├── TOOLS.md                     # Detailed tool documentation
└── README.md                    # User-facing documentation
```

---

## Tech Stack

| Component | Library | Purpose |
|-----------|---------|---------|
| HTTP server | `fastapi >= 0.109.0` | Async web framework |
| ASGI server | `uvicorn >= 0.27.0` | Production server |
| HTTP client | `httpx >= 0.26.0` | Async calls to NPPES API |
| MCP SDK | `mcp >= 1.1.0` | MCP protocol types |
| Caching | `redis >= 5.0.0` (Upstash) | 1-hour result caching |
| Vector search | `faiss-cpu >= 1.7.4` | Taxonomy similarity search |
| Embeddings | `sentence-transformers >= 2.2.0` | `paraphrase-MiniLM-L3-v2` model |
| Testing | `pytest`, `pytest-asyncio`, `fakeredis`, `schemathesis` | Full test suite |

---

## Development Setup

```bash
# 1. Clone and enter
git clone https://github.com/rradhakr-git/nppes-mcp-server.git
cd nppes-mcp-server

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate       # Linux/macOS
# venv\Scripts\activate        # Windows

# 3. Install dependencies
pip install -r requirements-dev.txt

# 4. Copy and configure environment variables
cp .env.example .env
# Edit .env: set REDIS_URL if using Redis

# 5. Start the server
uvicorn app.main:app --reload --port 8000
```

### With Docker

```bash
docker build -t nppes-mcp .
docker run -p 8000:8000 -e REDIS_URL=your_redis_url nppes-mcp
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis/Upstash connection string |
| `CACHE_TTL_SECONDS` | `3600` | Cache TTL in seconds |
| `CACHE_KEY_PREFIX` | `nppes` | Redis key prefix |
| `NPPES_API_URL` | *(NPPES endpoint)* | Override NPPES API base URL |
| `REQUEST_TIMEOUT_SECONDS` | `30` | HTTP timeout for NPPES calls |
| `TAXONOMY_CSV_PATH` | *(bundled)* | Path to NUCC taxonomy CSV |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `PORT` | `8000` | Server port |

---

## MCP Tools Reference

All tools are registered in `app/main.py` → `TOOL_REGISTRY` and implemented in `app/tools/`.

### `search_providers`
Search NPPES for healthcare providers with optional filters.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `first_name` | str | No | Provider first name |
| `last_name` | str | No | Provider last name |
| `organization_name` | str | No | Hospital/clinic name |
| `city` | str | No | City filter |
| `state` | str | No | 2-letter state code (`^[A-Z]{2}$`) |
| `specialty` | str | No | Taxonomy code or specialty name |
| `zip_code` | str | No | 5-digit or ZIP+4 (`^[0-9]{5}(-[0-9]{4})?$`) |
| `limit` | int | No | Max results (default: 10) |

### `get_provider_by_npi`
Fetch a full provider record by NPI number.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `npi` | str | **Yes** | 10-digit NPI (`^[0-9]{10}$`) |

### `validate_npi`
Validate an NPI using Mod 97-10 checksum.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `npi` | str | **Yes** | 10-digit NPI |

### `get_npi_for_provider`
Lookup NPI numbers by provider name and location.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `first_name` | str | No | Provider first name |
| `last_name` | str | No | Provider last name |
| `organization_name` | str | No | Organization name |
| `city` | str | No | City filter |
| `state` | str | No | 2-letter state code |
| `zip_code` | str | No | ZIP code |
| `specialty` | str | No | Taxonomy code |

### `resolve_taxonomy`
Look up NUCC taxonomy codes by code or natural language. Uses FAISS + RAG.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `code` | str | No | Exact taxonomy code |
| `query` | str | No | Natural language query (e.g., "heart doctor") |
| `top_k` | int | No | Number of results (default: 5) |
| `min_score` | float | No | Min similarity score 0.0–1.0 (default: 0.0) |

### `semantic_search`
Combined RAG + NPPES search — natural language → taxonomy codes → provider results.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `query` | str | **Yes** | Natural language query |
| `state` | str | No | Optional state filter |
| `city` | str | No | Optional city filter |
| `top_k` | int | No | Taxonomy codes to consider (default: 5) |
| `min_score` | float | No | Min similarity score (default: 0.0) |

> **Note**: `resolve_taxonomy` and `semantic_search` receive the FastAPI `Request` object automatically (injected in `app/main.py`) to access `app.state.rag_index`. Do not pass `request` manually.

---

## MCP Protocol

The server handles JSON-RPC 2.0 at `POST /mcp`.

### Supported methods

| Method | Description |
|--------|-------------|
| `initialize` | Protocol handshake; returns `protocolVersion: "2024-11-05"` |
| `ping` | Health check; returns `{}` |
| `tools/list` | Returns all registered tools with input schemas |
| `tools/call` | Calls a tool by name with arguments |

### Example: call a tool

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "search_providers",
      "arguments": {"state": "CT", "city": "Hartford", "limit": 3}
    }
  }'
```

---

## Application Architecture

### Startup (lifespan)
`app/main.py` uses FastAPI's `lifespan` context manager to load the `TaxonomyIndex` once at startup into `app.state.rag_index`. This avoids reloading the FAISS index and sentence-transformer model on every request.

### RAG Pipeline
1. `Embedder` (`app/rag/embedder.py`) loads `paraphrase-MiniLM-L3-v2` (bundled in `models/`)
2. `TaxonomyIndex` (`app/rag/index.py`) builds a FAISS index over NUCC taxonomy descriptions
3. `semantic_search` and `resolve_taxonomy` query the index, then call NPPES with matched taxonomy codes

### Caching
- Redis (Upstash in production) caches NPPES API responses for `CACHE_TTL_SECONDS` (default: 1 hour)
- Tools accept an optional `cache` parameter (injected during testing via `fakeredis`)

### Parameter Validation Patterns
These patterns are enforced at the MCP schema level in `PARAMETER_PATTERNS` (in `app/main.py`):
- `npi`: `^[0-9]{10}$`
- `state`: `^[A-Z]{2}$`
- `zip_code`: `^[0-9]{5}(-[0-9]{4})?$`

---

## Testing

```bash
# Run all tests
pytest

# Unit tests only (fast, no network)
pytest tests/unit -q

# Integration tests
pytest tests/integration -v

# Contract/schema tests
pytest tests/contract -v

# E2E against a live server
MCP_SERVER_URL=https://your-server.com pytest tests/e2e -v

# With coverage report
pytest --cov=app --cov-report=term-missing
```

### Test Coverage Target
- **85%+** coverage required
- **119 tests** across unit, integration, and contract suites
- Tools use dependency injection for `nppes_client`, `cache`, and `taxonomy_index` to enable mocking

### Writing Tests for Tools

Tools accept injectable dependencies for testing:

```python
@pytest.mark.asyncio
async def test_search_providers_passes_specialty():
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.search_by_name_and_fields = AsyncMock(return_value=[])

    await search_providers(
        first_name="John",
        specialty="207Q00000X",
        nppes_client=mock_nppes,
    )

    call_kwargs = mock_nppes.search_by_name_and_fields.call_args.kwargs
    assert call_kwargs.get("specialty") == "207Q00000X"
```

---

## Code Conventions

### Tool Implementation Pattern

Every tool in `app/tools/` follows this pattern:

```python
from typing import Optional
from app.nppes_client import NPPESClient

async def my_tool(
    # ── Public parameters (exposed via MCP) ──────────────────
    param_a: Optional[str] = None,
    param_b: Optional[str] = None,
    # ── Internal/testing parameters (NOT exposed via MCP) ────
    nppes_client: Optional[NPPESClient] = None,
    cache=None,
) -> list[dict]:
    """
    One-line description used as the MCP tool description.

    Args:
        param_a: Description of param_a
        param_b: Description of param_b
    """
    ...
```

**Rules:**
1. Internal params (`nppes_client`, `cache`, `taxonomy_index`, `request`) are skipped in `tools/list` responses — see `app/main.py`.
2. Docstrings use Google style; the first line becomes the tool's MCP description.
3. All parameters should have type annotations.

### Adding a New Tool

1. Create `app/tools/my_new_tool.py` following the pattern above.
2. Import and register in `app/main.py`:
   ```python
   from app.tools.my_new_tool import my_new_tool
   TOOL_REGISTRY["my_new_tool"] = my_new_tool
   ```
3. Add parameter documentation to `TOOL_PARAMETER_DOCS` in `app/main.py`.
4. If the tool uses the RAG index, add its name to the injection check:
   ```python
   if tool_name in ("semantic_search", "resolve_taxonomy", "my_new_tool"):
       tool_args["request"] = request
   ```
5. Write unit tests in `tests/unit/`.
6. Update `README.md` and `TOOLS.md`.

---

## Critical Rules (Do Not Violate)

### 1. MCP Tool Parameters Must Match API Client Parameters

When a tool wraps `NPPESClient`, expose **all** parameters the client supports. Missing parameters cause silent feature loss.

```python
# ✅ Correct — all API client params are exposed
async def search_providers(
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    organization_name: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    specialty: Optional[str] = None,   # ← easy to forget
    zip_code: Optional[str] = None,
    limit: int = 10,
    nppes_client: Optional[NPPESClient] = None,
):
    ...

# ❌ Wrong — specialty silently missing from MCP tool
async def search_providers(
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    nppes_client: Optional[NPPESClient] = None,
):
    ...
```

### 2. Keep README and TOOLS.md in Sync with Tool Signatures

Before merging to `main` or deploying:
- Verify every tool in `TOOL_REGISTRY` has a section in `README.md` and `TOOLS.md`
- Confirm parameter lists match the actual function signatures
- Run `pytest` to confirm no regressions

### 3. Do Not Expose Internal Parameters via MCP

The following parameter names are filtered out of `tools/list` responses and must **never** be added as public parameters:
- `nppes_client`
- `cache`
- `taxonomy_index`
- `request`

---

## Deployment

### Render.com (primary)
The `render.yaml` configures a Docker-based web service. Steps:
1. Connect the GitHub repo to Render
2. Create a Web Service (Docker runtime)
3. Set `REDIS_URL` to your Upstash Redis URL
4. Deploy — Render auto-detects `render.yaml`

### Health Check
```
GET /health  →  {"status": "healthy"}
```

### Connecting to Claude Desktop

```json
{
  "mcpServers": {
    "nppes": {
      "url": "https://your-app.onrender.com/mcp"
    }
  }
}
```

---

## Key Files Quick Reference

| File | What it does |
|------|-------------|
| `app/main.py` | FastAPI app, MCP router, tool registry, `TOOL_PARAMETER_DOCS`, `PARAMETER_PATTERNS` |
| `app/nppes_client.py` | Async HTTP client for `npiregistry.cms.hhs.gov` |
| `app/rag/index.py` | FAISS-based `TaxonomyIndex` |
| `app/rag/embedder.py` | `Embedder` wrapping `paraphrase-MiniLM-L3-v2` |
| `app/tools/` | One module per MCP tool |
| `tests/unit/` | Fast isolated tests with mocks |
| `tests/integration/` | Tests with `fakeredis` and live NPPES |
| `tests/contract/` | Schema validation via `schemathesis` |
| `.env.example` | All supported environment variables with descriptions |
| `TOOLS.md` | Detailed tool usage examples |
```