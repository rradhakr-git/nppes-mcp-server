"""
FastAPI application with MCP endpoint.

Provides MCP (Model Context Protocol) tools for NPPES provider search.

Environment variables:
    REDIS_URL: Redis connection URL
    CACHE_TTL_SECONDS: Cache TTL (default: 3600)
    CACHE_KEY_PREFIX: Cache key prefix (default: nppes)
    NPPES_API_URL: Override NPPES API URL
    REQUEST_TIMEOUT_SECONDS: HTTP request timeout (default: 30)
    TAXONOMY_CSV_PATH: Path to bundled taxonomy CSV
    LOG_LEVEL: Logging level (default: INFO)
    PORT: Server port (default: 8000)
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Optional
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field

from app.rag.index import TaxonomyIndex
from app.rag.embedder import Embedder
from app.tools.search_providers import search_providers
from app.tools.resolve_taxonomy import resolve_taxonomy
from app.tools.semantic_search import semantic_search
from app.tools.get_provider_by_npi import get_provider_by_npi
from app.tools.validate_npi import validate_npi
from app.tools.get_npi_for_provider import get_npi_for_provider


# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load RAG resources at startup, clean up on shutdown."""
    # Startup: load TaxonomyIndex once
    logger.info("Loading RAG taxonomy index at startup...")
    embedder = Embedder()
    app.state.rag_index = TaxonomyIndex(embedder=embedder, skip_build=False)
    logger.info(f"RAG taxonomy index loaded with {len(app.state.rag_index._taxonomies)} taxonomies")

    yield

    # Shutdown: clean up
    logger.info("Shutting down RAG resources...")
    app.state.rag_index = None


app = FastAPI(
    title="NPPES MCP Server",
    description="MCP server for NPPES provider registry search",
    version="1.0.0",
    lifespan=lifespan
)


# =============================================================================
# MCP Request/Response Models
# =============================================================================

class MCPParams(BaseModel):
    """MCP tools/call parameters."""
    name: str = Field(..., description="Tool name to call")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class MCPRequest(BaseModel):
    """JSON-RPC 2.0 request."""
    jsonrpc: str = Field(..., pattern=r"^2\.0$")
    id: int | str | None
    method: str
    params: Optional[MCPParams] = None


class MCPContentItem(BaseModel):
    """MCP content item."""
    type: str = "text"
    text: str


class MCPResult(BaseModel):
    """MCP result wrapper."""
    content: list[dict[str, Any]]


class MCPError(BaseModel):
    """JSON-RPC error."""
    code: int
    message: str
    data: Optional[str] = None


# =============================================================================
# Tool Registry
# =============================================================================

TOOL_REGISTRY = {
    "search_providers": search_providers,
    "resolve_taxonomy": resolve_taxonomy,
    "semantic_search": semantic_search,
    "get_provider_by_npi": get_provider_by_npi,
    "validate_npi": validate_npi,
    "get_npi_for_provider": get_npi_for_provider,
}


# =============================================================================
# MCP Endpoint
# =============================================================================

@app.post("/mcp")
async def handle_mcp_request(request: Request):
    """Handle MCP JSON-RPC 2.0 requests."""
    # Parse JSON body
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Extract required fields
    jsonrpc = body.get("jsonrpc")
    request_id = body.get("id")
    method = body.get("method")
    params = body.get("params")

    # Validate jsonrpc field
    if jsonrpc != "2.0":
        raise HTTPException(status_code=400, detail="Invalid jsonrpc version")

    # Validate method field
    if not method:
        raise HTTPException(status_code=400, detail="Missing method field")

    # Validate params for tools/call
    if method == "tools/call":
        if params is None:
            raise HTTPException(status_code=400, detail="Missing params")

        if not isinstance(params, dict):
            raise HTTPException(status_code=400, detail="Params must be an object")

        tool_name = params.get("name")
        has_arguments = "arguments" in params
        tool_args = params.get("arguments", {}) if has_arguments else {}

        if not tool_name:
            raise HTTPException(status_code=400, detail="Missing tool name")

        # Validate required arguments if tool needs them
        if not has_arguments:
            raise HTTPException(
                status_code=400,
                detail="Missing required parameter: arguments"
            )

        # Check if tool exists
        if tool_name not in TOOL_REGISTRY:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"UNKNOWN_TOOL: Tool '{tool_name}' not found"
                }
            }

        # Get and call the tool
        tool_func = TOOL_REGISTRY[tool_name]

        # Pass request to tools that need access to app.state (for RAG index)
        # Only pass to tools that accept 'request' parameter
        if tool_name in ("semantic_search", "resolve_taxonomy"):
            tool_args["request"] = request

        try:
            result = await tool_func(**tool_args)
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }

        # Wrap result in MCP envelope
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": result if isinstance(result, list) else [result]
            }
        }

    # =============================================================================
    # Standard MCP Methods
    # =============================================================================

    # ping - health check
    if method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {}
        }

    # initialize - protocol handshake
    if method == "initialize":
        client_info = params.get("clientInfo", {}) if params else {}
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "NPPES MCP Server",
                    "version": "1.0.0"
                }
            }
        }

    # tools/list - return available tools
    if method == "tools/list":
        tools = []
        for name, func in TOOL_REGISTRY.items():
            # Extract docstring for description
            doc = func.__doc__ or ""
            description = doc.strip().split("\n")[0] if doc else ""
            tools.append({
                "name": name,
                "description": description,
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            })
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": tools
            }
        }

    # Unknown method
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": -32601,
            "message": f"Unknown method: {method}"
        }
    }


# =============================================================================
# Health Check Endpoint
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# =============================================================================
# OpenAPI docs endpoint (for portfolio showcase)
# =============================================================================

@app.get("/")
async def root():
    """Root endpoint with server info."""
    return {
        "name": "NPPES MCP Server",
        "version": "1.0.0",
        "docs": "/docs",
        "mcp_endpoint": "/mcp"
    }