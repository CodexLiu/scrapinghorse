# Scraping Horse API

Simple web scraping API server that extracts structured data from Google AI search results.

## Quick Start

### Start Server
```bash
./start_server.sh
```

### Use API
```bash
curl -H "X-API-Key: is_hotdog_or_not" "http://192.168.2.186:8000/search?query=your_search_here"
```

Replace `192.168.2.186` with your actual IP address (shown when server starts).

## API

- **Endpoint**: `GET /search`
- **Required Header**: `X-API-Key: is_hotdog_or_not`
- **Parameters**: 
  - `query` (required): Search query string
  - `max_wait_seconds` (optional): Max wait time, default 10

## Response
Returns JSON with `text_blocks`, `references`, and `inline_images`.
