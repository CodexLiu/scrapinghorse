import os
import time
import requests
from fastapi import APIRouter, Request
from v1.schemas.api import SearchRequest, SearchResponse
from v1.rate_limiter import limiter, RateLimits

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
    REQUEST_TIMEOUT = 30
    
    headers = {
        "X-API-Key": API_KEY
    }
    start_time = time.time()
    response = requests.get(
        f"{API_BASE_URL}{ENDPOINT}",
        params=search_request.model_dump(),
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
