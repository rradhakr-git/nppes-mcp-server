#!/bin/bash
# Ping the NPPES MCP server to keep it warm
# Runs every 4 hours via cron

URL="https://nppes-mcp-server.onrender.com/mcp"
LOGFILE="/home/aiagent/.claude/projects/nppes-mcp-server/logs/ping.log"

# Create logs directory if it doesn't exist
mkdir -p "$(dirname "$LOGFILE")"

# Send a real tool call to keep the server warm and awake
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$URL" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"validate_npi","arguments":{"npi":"1000000023"}}}' \
  --max-time 30 2>&1)

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

if [ "$RESPONSE" = "200" ]; then
    echo "$TIMESTAMP - OK (HTTP $RESPONSE)" >> "$LOGFILE"
else
    echo "$TIMESTAMP - FAILED (HTTP $RESPONSE)" >> "$LOGFILE"
fi