from fastapi import APIRouter, Request
from v1.rate_limiter import limiter, RateLimits

router = APIRouter(
    tags=["public"],
)

@router.get("/")
@limiter.limit(RateLimits.PUBLIC)
async def root(request: Request):
    return {"message": "Hello, World!"}