import asyncio
import os
import threading
from typing import Dict, Any
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from app.utils.scrape_ai_mode import init_driver_session, run_job, reset_to_start, start_usage_capture, end_usage_capture_gb
from app.utils.queue import JobRouter, Worker

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

# Global worker pool and job router
workers = []
job_router = None

@app.get("/")
async def root():
    return {"message": "API is healthy"}

@app.on_event("startup")
async def on_startup():
    """Initialize the Chrome worker pool and job router on server startup."""
    global workers, job_router
    print("Starting up server - initializing Chrome worker pool...")
    
    # Log proxy configuration
    proxies_enabled = os.getenv('ENABLE_PROXIES', '0').lower() in ('1', 'true', 'yes')
    if proxies_enabled:
        proxy_host = os.getenv('OXYLABS_PROXY_HOST', 'pr.oxylabs.io')
        proxy_port = os.getenv('OXYLABS_PROXY_PORT', '7777')
        username = os.getenv('OXYLABS_USERNAME')
        if username:
            print(f"🔄 Proxies ENABLED - using {proxy_host}:{proxy_port} with user: customer-{username}-cc-US")
        else:
            print("⚠️ Proxies ENABLED but no OXYLABS_USERNAME found - will use direct connection")
    else:
        print("ℹ️ Proxies DISABLED - using direct connection")
    
    try:
        # Create worker pool
        chrome_workers = int(os.getenv("CHROME_WORKERS", "1"))
        print(f"Creating {chrome_workers} Chrome worker(s)...")
        
        workers = []
        for i in range(chrome_workers):
            print(f"Initializing worker {i}...")
            driver = init_driver_session()
            worker = Worker(
                id=i,
                driver=driver,
                queue=asyncio.Queue(),
                state="initializing",
                lock=threading.Lock()
            )
            workers.append(worker)
            print(f"Worker {i} initialized")
        
        # Initialize job router
        job_router = JobRouter(workers)
        await job_router.start(process_job_on_worker)
        print(f"Server startup complete - {len(workers)} Chrome workers ready")
    except Exception as e:
        print(f"Failed to initialize server: {e}")
        raise

async def process_job_on_worker(worker: Worker, job) -> dict:
    """Process a single search job using a specific worker's Chrome driver."""
    with worker.lock:
        try:
            start_usage_capture(worker.driver)
            result = await asyncio.to_thread(run_job, worker.driver, job.query, job.max_wait_seconds)
            usage_gb = end_usage_capture_gb(worker.driver)
            print(f"Worker {worker.id} request data usage: {usage_gb:.4f} GB")
            worker.driver = await asyncio.to_thread(reset_to_start, worker.driver)
            print(f"Worker {worker.id} job completed, driver reset")
            return result
        except Exception as e:
            print(f"Worker {worker.id} error processing job: {e}")
            try:
                worker.driver = await asyncio.to_thread(reset_to_start, worker.driver)
                print(f"Worker {worker.id} driver reset after error")
            except Exception as reset_error:
                print(f"Worker {worker.id} failed to reset driver: {reset_error}")
            raise e

@app.on_event("shutdown")
async def on_shutdown():
    """Clean up job router and Chrome workers on server shutdown."""
    global workers, job_router
    print("Shutting down server...")
    
    # Stop the job router first
    if job_router:
        try:
            await job_router.stop()
            print("Job router stopped")
        except Exception as e:
            print(f"Error stopping job router: {e}")
    
    # Close all Chrome sessions
    for worker in workers:
        if worker.driver:
            try:
                worker.driver.quit()
                print(f"Worker {worker.id} Chrome session closed")
            except Exception as e:
                print(f"Error closing worker {worker.id} Chrome session: {e}")
    
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
    result = await job_router.enqueue(decoded_query, max_wait_seconds)
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
