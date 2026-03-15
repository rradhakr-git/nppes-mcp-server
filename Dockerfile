# NPPES MCP Server - Dockerfile
# Deploy to Render.com or any Docker-compatible hosting

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for FAISS and sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Ensure taxonomy CSV is bundled (should be in app/rag/taxonomy.csv)
# If missing, the app will download it at startup

# Expose port
EXPOSE 8000

# Run the server
# Render.com sets PORT env var automatically
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
