import os
from fastapi import HTTPException, Header

# Default to dev if no API key is set. E.g, local-testing
API_KEY = os.getenv("API_KEY", "dev")

async def get_api_key(api_key: str = Header(...)):
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key