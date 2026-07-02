import os

from fastapi import Header, HTTPException


async def verify_internal_key(x_internal_key: str = Header(default="")) -> None:
    expected = os.getenv("CHAT_API_INTERNAL_KEY", "")
    if not expected:
        return
    if x_internal_key != expected:
        raise HTTPException(status_code=401, detail="invalid internal key")
