import asyncio
import os
import threading
from typing import Dict, Any
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from app.utils.scrape_ai_mode import init_driver_session, run_job, reset_to_start, start_usage_capture, end_usage_capture_gb
from app.utils.queue import JobQueue

API_KEY = os.getenv("horse_key")
app = FastAPI()

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to return structured JSON error responses."""
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "error_type": exc.__class__.__name__
        }
    )

# Global Chrome driver and request queue
chrome_driver = None
driver_lock = threading.Lock()
request_queue = None

@app.get("/")
async def root():
    return {"message": "API is healthy"}

@app.on_event("startup")
async def on_startup():
    """Initialize the single Chrome session and job queue on server startup."""
    global chrome_driver, request_queue
    print("Starting up server - initializing Chrome session...")
    
    try:
        chrome_driver = init_driver_session()
        print("Chrome session ready - initializing job queue...")
        
        # Initialize and start the job queue
        request_queue = JobQueue()
        await request_queue.start(process_job)
        print("Server startup complete - Chrome session and job queue ready")
    except Exception as e:
        print(f"Failed to initialize server: {e}")
        raise

async def process_job(job) -> dict:
    """Process a single search job using the Chrome driver."""
    with driver_lock:
        try:
            start_usage_capture(chrome_driver)
            result = await asyncio.to_thread(run_job, chrome_driver, job.query, job.max_wait_seconds)
            usage_gb = end_usage_capture_gb(chrome_driver)
            print(f"Request data usage: {usage_gb:.4f} GB")
            await asyncio.to_thread(reset_to_start, chrome_driver)
            print("Job completed, driver reset")
            return result
        except Exception as e:
            print(f"Error processing job: {e}")
            try:
                await asyncio.to_thread(reset_to_start, chrome_driver)
                print("Driver reset after error")
            except Exception as reset_error:
                print(f"Failed to reset driver: {reset_error}")
            raise e

@app.on_event("shutdown")
async def on_shutdown():
    """Clean up job queue and Chrome session on server shutdown."""
    global chrome_driver, request_queue
    print("Shutting down server...")
    
    # Stop the job queue first
    if request_queue:
        try:
            await request_queue.stop()
            print("Job queue stopped")
        except Exception as e:
            print(f"Error stopping job queue: {e}")
    
    # Close Chrome sessions
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
    
    # Enqueue job and await result
    result = await request_queue.enqueue(decoded_query, max_wait_seconds)
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
