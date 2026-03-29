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

import inspect
import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Any, Optional, get_type_hints
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


def parse_docstring_params(func) -> dict[str, str]:
    """
    Parse parameter descriptions from Google-style docstring.

    Args:
        func: Function with docstring containing Args section

    Returns:
        Dict mapping parameter names to their descriptions
    """
    doc = func.__doc__ or ""
    params = {}

    # Find Args section
    args_match = re.search(r'Args:\s*\n(.+?)(?:\n\s*Returns:|\n\s*Raises:|\Z)', doc, re.DOTALL)
    if not args_match:
        return params

    args_section = args_match.group(1)
    lines = args_section.split('\n')

    current_param = None
    current_desc = []

    for line in lines:
        # Check for parameter definition (param_name: description or param_name: type - description)
        param_match = re.match(r'\s*(\w+)\s*:\s*(.+)', line)
        if param_match:
            # Save previous param if exists
            if current_param:
                params[current_param] = ' '.join(current_desc).strip()
            current_param = param_match.group(1)
            # Extract description, handling type annotations
            desc = param_match.group(2)
            # Remove type annotation prefix if present (e.g., "Provider name")
            desc = re.sub(r'^[\w\[\]|,.\s]+\s*-\s*', '', desc)
            current_desc = [desc]
        elif current_param and line.strip().startswith('-'):
            # Continuation line (Google style sometimes uses this)
            desc = line.strip().lstrip('-').strip()
            current_desc.append(desc)
        elif current_param and line.strip() and not line.strip().startswith('Args:') and not line.strip().startswith('Returns:'):
            # Continuation of description
            current_desc.append(line.strip())

    # Save last param
    if current_param:
        params[current_param] = ' '.join(current_desc).strip()

    return params


# Parameter metadata for enhanced documentation
TOOL_PARAMETER_DOCS = {
    "search_providers": {
        "name": "Provider first name (deprecated, use first_name instead)",
        "first_name": "Provider first name (e.g., 'Barry')",
        "last_name": "Provider last name (e.g., 'Hartman')",
        "organization_name": "Organization/facility name (for hospitals, clinics)",
        "city": "City name filter (e.g., 'New Haven')",
        "state": "Two-letter state code (e.g., 'CT', 'CA', 'NY')",
        "specialty": "Taxonomy code or specialty name (e.g., 'Cardiology', '207Q00000X')",
        "limit": "Maximum results to return (default: 10)"
    },
    "resolve_taxonomy": {
        "code": "Specific taxonomy code (e.g., '207Q00000X')",
        "query": "Natural language query (e.g., 'heart doctor', 'pediatrician')",
        "top_k": "Number of results for semantic search (default: 5)",
        "min_score": "Minimum similarity score 0.0-1.0 (default: 0.0)"
    },
    "semantic_search": {
        "query": "Natural language query (e.g., 'cardiologist in Connecticut')",
        "state": "Optional state filter (2-letter code)",
        "city": "Optional city filter",
        "top_k": "Number of taxonomy codes to search (default: 5)",
        "min_score": "Minimum similarity score 0.0-1.0 (default: 0.0)"
    },
    "get_provider_by_npi": {
        "npi": "10-digit National Provider Identifier (e.g., '1000000023')"
    },
    "validate_npi": {
        "npi": "10-digit National Provider Identifier to validate"
    },
    "get_npi_for_provider": {
        "first_name": "Provider first name",
        "last_name": "Provider last name",
        "organization_name": "Organization/facility name (for hospitals, clinics)",
        "city": "City filter",
        "state": "State filter (2-letter code)",
        "zip_code": "ZIP code filter (5 digits or ZIP+4)"
    }
}


# Parameter validation patterns
PARAMETER_PATTERNS = {
    "npi": {"pattern": "^[0-9]{10}$", "description": "Must be exactly 10 digits"},
    "state": {"pattern": "^[A-Z]{2}$", "description": "Two uppercase letters"},
    "zip_code": {"pattern": "^[0-9]{5}(-[0-9]{4})?$", "description": "5 digits or ZIP+4 format"},
}


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

    # tools/list - return available tools with parameter info
    if method == "tools/list":
        tools = []
        for name, func in TOOL_REGISTRY.items():
            # Extract docstring for description
            doc = func.__doc__ or ""
            description = doc.strip().split("\n")[0] if doc else ""

            # Extract parameters using inspect
            sig = inspect.signature(func)
            properties = {}
            required = []

            # Get parameter docs from function docstring
            docstring_params = parse_docstring_params(func)
            tool_param_docs = TOOL_PARAMETER_DOCS.get(name, {})

            for param_name, param in sig.parameters.items():
                # Skip internal/testing params
                if param_name in ("nppes_client", "cache", "taxonomy_index", "request"):
                    continue

                param_info = {}
                # Get type annotation
                if param.annotation != inspect.Parameter.empty:
                    param_type = param.annotation
                    if hasattr(param_type, "__name__"):
                        param_info["type"] = param_type.__name__
                    elif hasattr(param_type, "_name"):  # Generic types like Optional
                        param_info["type"] = str(param_type)

                # Add description from metadata or parse docstring
                description = tool_param_docs.get(param_name) or docstring_params.get(param_name)
                if description:
                    param_info["description"] = description

                # Add validation pattern if available
                if param_name in PARAMETER_PATTERNS:
                    param_info["pattern"] = PARAMETER_PATTERNS[param_name]["pattern"]
                    if "description" in param_info:
                        param_info["description"] += f" ({PARAMETER_PATTERNS[param_name]['description']})"
                    else:
                        param_info["description"] = PARAMETER_PATTERNS[param_name]["description"]

                # Check if has default (optional) or no default (required)
                if param.default != inspect.Parameter.empty:
                    param_info["optional"] = True
                    if param.default is not None and param.default != ...:  # Skip sentinel values
                        param_info["default"] = param.default
                else:
                    required.append(param_name)

                properties[param_name] = param_info

            tools.append({
                "name": name,
                "description": description,
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required if required else None
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