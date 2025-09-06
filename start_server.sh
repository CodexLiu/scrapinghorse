#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Parse workers argument (default to 1)
CHROME_WORKERS=1
if [ "$1" ]; then
    if [[ "$1" =~ ^[0-9]+$ ]]; then
        CHROME_WORKERS=$1
        echo "Starting scraping server with $CHROME_WORKERS Chrome worker(s)..."
    else
        echo "Usage: $0 [number_of_chrome_workers]"
        echo "Example: $0 2  # Start with 2 Chrome worker processes"
        exit 1
    fi
else
    echo "Starting scraping server with 1 Chrome worker..."throug
fi

# Export CHROME_WORKERS for child processes
export CHROME_WORKERS

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

# Setup window positioning
rm -rf .window_slots && mkdir -p .window_slots
export WINDOW_MARGIN="${WINDOW_MARGIN:-20}"

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

# Start localtunnel in background
echo "Starting localtunnel..."
lt --port 8000 --subdomain scrapinghorse > logs/tunnel.log 2>&1 &
TUNNEL_PID=$!

# Wait a moment for tunnel to establish
sleep 3

# Check if tunnel started successfully
if kill -0 $TUNNEL_PID 2>/dev/null; then
    echo "✅ Localtunnel started: https://scrapinghorse.loca.lt"
    echo "   Tunnel PID: $TUNNEL_PID"
else
    echo "❌ Failed to start localtunnel"
fi

echo ""
echo "Press Ctrl+C to stop the server and tunnel"
echo "----------------------------------------"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    if kill -0 $TUNNEL_PID 2>/dev/null; then
        echo "Stopping localtunnel (PID: $TUNNEL_PID)..."
        kill $TUNNEL_PID
    fi
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup SIGINT SIGTERM

# Start the server with single uvicorn process (workers managed internally)
uvicorn app.server:app --host 0.0.0.0 --port 8000 --workers 1 2>&1 | tee -a "$LOG_FILE"
