#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting scraping server..."
echo "Directory: $SCRIPT_DIR"

# Activate virtual environment
source .venv/bin/activate

# Load environment variables from .env file
set -a && source .env && set +a

# Setup logging
mkdir -p logs
LOG_FILE="logs/server-$(date +'%Y%m%d_%H%M%S').log"
ln -sf "$(basename "$LOG_FILE")" logs/latest.log
echo "Server logs will be written to: $LOG_FILE"
echo ""

# Detect active network interface and get IP addresses
echo "Server will be accessible at:"

# Try en0 first, fallback to en1
IFACE="en0"
LOCAL_IPV4=$(ipconfig getifaddr "$IFACE" 2>/dev/null || true)

if [ -z "$LOCAL_IPV4" ]; then
    IFACE="en1"
    LOCAL_IPV4=$(ipconfig getifaddr "$IFACE" 2>/dev/null || true)
fi

# Display IPv4 if found
if [ -n "$LOCAL_IPV4" ]; then
    echo "  IPv4 ($IFACE): http://$LOCAL_IPV4:8000"
fi

# Get IPv6 for the selected interface
LOCAL_IPV6=$(ifconfig "$IFACE" 2>/dev/null | awk '/inet6/{print $2}' | grep -v '^fe80' | head -n1)
if [ -n "$LOCAL_IPV6" ]; then
    echo "  IPv6 ($IFACE): http://[$LOCAL_IPV6]:8000"
fi

echo ""
echo "API Key required: X-API-Key: $horse_key"

# Show curl example only if we have an IPv4
if [ -n "$LOCAL_IPV4" ]; then
    echo "Example: curl -H \"X-API-Key: $horse_key\" \"http://$LOCAL_IPV4:8000/search?query=test\""
else
    echo "Note: No IPv4 detected on en0 or en1; server started on port 8000. Check your network interface."
fi

echo ""
echo "Press Ctrl+C to stop the server"
echo "----------------------------------------"

# Start the server
uvicorn app.server:app --host 0.0.0.0 --port 8000 2>&1 | tee -a "$LOG_FILE"
