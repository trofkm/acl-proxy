from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse

from auth.service import ForbiddenHostError, InvalidTokenError, validate_token
from config import Config
from deps import check_throttle, get_auth_throttle, get_client_ip, get_config, get_store
from log import logger

router = APIRouter()


async def _record_failure(request: Request) -> None:
    throttle = get_auth_throttle(request)
    client_ip = get_client_ip(request)
    await throttle.record_failure(client_ip)


@router.api_route(
    "/auth",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    response_class=PlainTextResponse,
)
async def auth(
    request: Request,
    store=Depends(get_store),
    cfg: Config = Depends(get_config),
    _: None = Depends(check_throttle),
) -> str:
    auth_header = request.headers.get("authorization")
    if not auth_header:
        await _record_failure(request)
        raise HTTPException(status_code=401, detail="missing bearer token")

    host = request.headers.get("X-Forwarded-Host")

    parts = auth_header.split(maxsplit=1)
    if len(parts) < 2 or parts[0].lower() != "bearer":
        logger.warning("auth: bad auth header format, host=%s", host)
        await _record_failure(request)
        raise HTTPException(status_code=401, detail="invalid authorization header")

    token = parts[1]
    if not token:
        logger.warning("auth: empty token, host=%s", host)
        await _record_failure(request)
        raise HTTPException(status_code=401, detail="empty token")

    if not host:
        raise HTTPException(
            status_code=400,
            detail="missing X-Forwarded-Host header (must be set by reverse proxy)",
        )

    try:
        await validate_token(store, token, host, cfg.pepper.get_secret_value())
    except (InvalidTokenError, ForbiddenHostError):
        await _record_failure(request)
        raise HTTPException(status_code=401, detail="invalid token")

    return "OK"
