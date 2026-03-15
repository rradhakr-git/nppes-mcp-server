# NPPES MCP Server

> An MCP (Model Context Protocol) server for searching healthcare providers in the US National Provider Identifier (NPI) Registry — works with Claude, Cursor, and any MCP-compatible AI assistant.

Built with FastAPI, Redis caching, and FAISS-based semantic search over NUCC taxonomy codes.

## Claude Integration

This server implements the MCP (Model Context Protocol) specification, making it compatible with:

- **Claude Desktop** (Anthropic)
- **Cursor** IDE
- **Windsurf** IDE
- **Any MCP-compatible client**

Once deployed, you can connect Claude to search NPI providers using natural language:

```
You: Find me 5 pediatricians in Hartford, Connecticut
Claude: [uses search_providers tool via MCP server]
→ Returns list of providers with NPI numbers, addresses, specialties
```

The MCP endpoint is at `/mcp` and accepts JSON-RPC 2.0 `tools/call` requests.

## What This Does

Query the NPPES registry (npiregistry.cms.hhs.gov) using natural language or structured filters:

- **Find providers by location**: `state=CT, city=Hartford`
- **Find by specialty**: Search using taxonomy codes or semantic descriptions like "pediatric cardiologist"
- **Caching**: Redis (Upstash) caches results for 1 hour to stay friendly to the NPPES API

## Quick Start

### Local Development

```bash
# Clone and enter
git clone https://github.com/yourusername/nppes-mcp-server.git
cd nppes-mcp-server

# Set up virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload

# Test it
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

### With Docker

```bash
docker build -t nppes-mcp .
docker run -p 8000:8000 -e REDIS_URL=your_redis_url nppes-mcp
```

## MCP Tools

### `search_providers`

Search for healthcare providers with filters:

```json
{
  "name": "search_providers",
  "arguments": {
    "state": "CT",
    "city": "Hartford",
    "specialty": "207Q00000X",
    "limit": 10
  }
}
```

### `resolve_taxonomy`

Look up taxonomy codes by code or natural language:

```json
{
  "name": "resolve_taxonomy",
  "arguments": {
    "query": "heart doctor"
  }
}
```

### `semantic_search`

Combined RAG + NPPES search - finds providers matching a natural language query:

```json
{
  "name": "semantic_search",
  "arguments": {
    "query": "find me a pediatric cardiologist in Connecticut"
  }
}
```

## Connecting to Claude

Once deployed, add this to your Claude Desktop config:

### macOS
`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "nppes": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-http", "--port", "8000"],
      "env": {
        "URL": "https://your-app.onrender.com/mcp"
      }
    }
  }
}
```

### Or using SSE transport

```json
{
  "mcpServers": {
    "nppes": {
      "url": "https://your-app.onrender.com/mcp"
    }
  }
}
```

Then ask Claude:

> "Find me 3 cardiologists in Boston, MA"

Claude will use the MCP tool to search and return provider results.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection (Upstash for production) |
| `CACHE_TTL_SECONDS` | `3600` | Cache lifetime in seconds |
| `NPPES_API_URL` | (NPPES endpoint) | Override NPPES API URL |
| `REQUEST_TIMEOUT_SECONDS` | `30` | HTTP request timeout |
| `LOG_LEVEL` | `INFO` | Logging level |

See `.env.example` for more.

## Deployment

This repo deploys easily to Render.com:

1. Connect your GitHub repo to Render
2. Create a Web Service with Docker
3. Set `REDIS_URL` to your Upstash URL
4. Deploy

The `render.yaml` file handles most configuration automatically.

## Testing

```bash
# All tests
pytest

# Just unit tests (fast)
pytest tests/unit -q

# E2E against live server (requires MCP_SERVER_URL env var)
MCP_SERVER_URL=https://your-server.com pytest tests/e2e -v
```

## Tech Stack

- **FastAPI** - HTTP server
- **httpx** - Async HTTP client for NPPES API
- **Redis** (Upstash) - Caching layer
- **FAISS** - Vector similarity search
- **sentence-transformers** - Embeddings for taxonomy semantic search
- **pytest** - Testing

## Why This Exists

I needed a way to query the NPI registry programmatically for a health-tech project. The NPPES web interface is... not great for programmatic access. This MCP server makes it easy for AI assistants (or any HTTP client) to search providers using natural language or structured filters.

The RAG pipeline over NUCC taxonomy codes lets you search by things like "find a doctor who treats heart conditions" instead of memorizing taxonomy codes.

## License

Apache License 2.0 - see LICENSE file.

---

Built with Claude Code and a lot of coffee.
