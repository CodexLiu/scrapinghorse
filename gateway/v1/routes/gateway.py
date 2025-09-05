import os
import time
import requests
from fastapi import APIRouter, Request, HTTPException
from v1.schemas.api import SearchRequest, SearchResponse
from v1.rate_limiter import limiter, RateLimits
import urllib.parse
from requests.exceptions import Timeout, ConnectionError, RequestException

router = APIRouter(
    prefix="/v1",
    tags=["scraping"],
)

@router.get("/test")
@limiter.limit(RateLimits.GENERAL)
async def test(request: Request):
    return {"message": "Hello, World!"}


@router.post("/search")
@limiter.limit(RateLimits.SEARCH)
async def search(
    search_request: SearchRequest,
    request: Request # Required for middleware
) -> SearchResponse:
    # Make an API call to the main server
    API_BASE_URL = os.getenv("BASE_URL", "")
    API_KEY = os.getenv("API_KEY", "dev")
    ENDPOINT = "/search"
    REQUEST_TIMEOUT = 45
    
    constructed_url = f"{API_BASE_URL}{ENDPOINT}?{urllib.parse.urlencode(search_request.model_dump())}"
    
    headers = {
        "X-API-Key": API_KEY
    }
    start_time = time.time()
    
    try:
        response = requests.get(
            constructed_url,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        print(f"Request time: {time.time() - start_time} seconds")
        response.raise_for_status()
        data = response.json()
        return SearchResponse(
            text_blocks=data["text_blocks"],
            references=data["references"],
            inline_images=data["inline_images"],
        )
    
    except Timeout:
        elapsed_time = time.time() - start_time
        print(f"Request timed out after {elapsed_time:.2f} seconds")
        raise HTTPException(
            status_code=504,
            detail=f"The search request timed out after {REQUEST_TIMEOUT} seconds. Please try again."
        )
    
    except ConnectionError:
        elapsed_time = time.time() - start_time
        print(f"Connection error after {elapsed_time:.2f} seconds")
        raise HTTPException(
            status_code=502,
            detail=f"Unable to connect to the search service at {constructed_url}. Please try again later."
        )
    
    except requests.exceptions.HTTPError as e:
        elapsed_time = time.time() - start_time
        print(f"HTTP error after {elapsed_time:.2f} seconds: {e}")
        
        # Extract upstream error details
        upstream_status = e.response.status_code
        try:
            upstream_error = e.response.json()
            upstream_detail = upstream_error.get("detail", str(e))
        except:
            upstream_detail = e.response.text or str(e)
        
        # Propagate upstream status and error details to Modal
        raise HTTPException(
            status_code=upstream_status,
            detail=f"Server error: {upstream_detail}"
        )
    
    except RequestException as e:
        elapsed_time = time.time() - start_time
        print(f"Request exception after {elapsed_time:.2f} seconds: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"An unexpected error occurred while contacting the search service at {constructed_url}. Please try again."
        )
