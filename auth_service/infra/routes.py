from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from deps import get_store
from metrics import store_health
from storage import TokenStore

router = APIRouter()


@router.get("/healthz", response_class=PlainTextResponse)
async def healthz() -> str:
    return "ok"


@router.get("/readyz", response_class=PlainTextResponse)
async def readyz(store: TokenStore = Depends(get_store)) -> str:
    try:
        healthy = await store.health()
    except Exception:
        healthy = False

    store_health.set(1 if healthy else 0)

    if healthy:
        return "ok"
    raise HTTPException(status_code=503, detail="store unavailable")
