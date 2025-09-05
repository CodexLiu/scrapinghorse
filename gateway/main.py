import modal
from v1.modal_config import app
from v1.routes.gateway import router
from v1.routes.public import router as public_router
from v1.auth import get_api_key
from v1.rate_limiter import setup_rate_limiting, rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded


@app.function()
@modal.concurrent(max_inputs=10)
@modal.asgi_app()
def f():
    from fastapi import FastAPI, Depends
    from fastapi.middleware.cors import CORSMiddleware
    
    def lifespan(wapp: FastAPI):
        print(f"Starting Scraping Horse Gateway with rate limiting")
        yield
        print(f"Stopping")
    
    web_app = FastAPI(
        title="Scraping Horse Gateway",
        version="0.1.0",
        lifespan=lifespan,
    )
    
    # Setup rate limiting (must be done before adding routes)
    limiter = setup_rate_limiting(web_app)
    
    # Add custom rate limit exceeded handler
    web_app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    
    web_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Public endpoints not required to have an API key
    web_app.include_router(public_router)
    
    # Private endpoints required to have an API key
    web_app.include_router(router, dependencies=[Depends(get_api_key)])

    return web_app
