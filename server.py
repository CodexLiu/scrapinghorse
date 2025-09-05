import asyncio
import threading
from typing import Dict, Any
from fastapi import FastAPI, Header, HTTPException, Query
from scrape_ai_mode import init_driver_session, run_job, reset_to_start, start_usage_capture, end_usage_capture_gb

API_KEY = "is_hotdog_or_not"
app = FastAPI()

# Global Chrome driver and lock for thread safety
chrome_driver = None
driver_lock = threading.Lock()

@app.get("/")
async def root():
    return {"message": "API is healthy"}

@app.on_event("startup")
async def on_startup():
    """Initialize the single Chrome session on server startup."""
    global chrome_driver
    print("Starting up server - initializing Chrome session...")
    
    try:
        chrome_driver = init_driver_session()
        print("Server startup complete - Chrome session ready with low-data mode")
    except Exception as e:
        print(f"Failed to initialize Chrome session: {e}")
        raise

@app.on_event("shutdown")
async def on_shutdown():
    """Clean up Chrome session on server shutdown."""
    global chrome_driver
    print("Shutting down server - closing Chrome session...")
    
    if chrome_driver:
        try:
            chrome_driver.quit()
            print("Chrome session closed")
        except Exception as e:
            print(f"Error closing Chrome session: {e}")
    
    print("Server shutdown complete")

@app.get("/search")
async def search(
    query: str = Query(..., description="Search query string"),
    api_key: str = Header(..., alias="X-API-Key"),
    max_wait_seconds: int = Query(10, description="Maximum seconds to wait for results")
) -> dict:
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Decode query (replace + with space)
    decoded_query = query.replace('+', ' ')
    
    # Use the single Chrome driver with thread safety
    def run_search():
        with driver_lock:
            try:
                print(f"Processing query: {decoded_query}")
                start_usage_capture(chrome_driver)
                result = run_job(chrome_driver, decoded_query, max_wait_seconds)
                usage_gb = end_usage_capture_gb(chrome_driver)
                print(f"Request data usage: {usage_gb:.4f} GB")
                reset_to_start(chrome_driver)
                print("Job completed, driver reset")
                return result
            except Exception as e:
                print(f"Error processing query: {e}")
                try:
                    reset_to_start(chrome_driver)
                    print("Driver reset after error")
                except Exception as reset_error:
                    print(f"Failed to reset driver: {reset_error}")
                raise e
    
    # Run in thread to avoid blocking the async event loop
    result = await asyncio.to_thread(run_search)
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
