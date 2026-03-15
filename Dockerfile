# NPPES MCP Server - Dockerfile
# Deploy to Render.com or any Docker-compatible hosting
#
# Uses keyword-based taxonomy search (no ML model needed at runtime)
# All 3 MCP tools work: search_providers, resolve_taxonomy, semantic_search

FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only (no ML libraries!)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python runtime deps
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages \
    fastapi uvicorn httpx redis faiss-cpu pydantic

# Copy application code
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Run the server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
