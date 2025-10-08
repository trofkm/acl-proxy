import os
from typing import List

from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import PlainTextResponse, JSONResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import secrets
import redis


def get_redis_client() -> redis.Redis:
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        decode_responses=True,
    )


redis_client = get_redis_client()

app = FastAPI(title="ACL Proxy Auth Service", version="0.1.0")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


@app.get("/healthz", response_class=PlainTextResponse)
async def healthz() -> str:
    try:
        # simple ping to ensure connectivity
        redis_client.ping()
        return "ok"
    except Exception:
        raise HTTPException(status_code=503, detail="redis unavailable")


def parse_allowed_hosts(raw_hosts: str) -> List[str]:
    if not raw_hosts:
        return []
    return [h.strip().lower() for h in raw_hosts.split(",") if h.strip()]


@app.get("/auth", response_class=PlainTextResponse)
async def auth(request: Request) -> str:
    # Extract Bearer token
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="empty token")

    # Load token data from redis
    token_key = f"tokens:{token}"
    token_data = redis_client.hgetall(token_key)
    if not token_data:
        raise HTTPException(status_code=401, detail="invalid token")

    allowed_hosts = parse_allowed_hosts(token_data.get("hosts", ""))

    # Determine requested host (Traefik will pass X-Forwarded-Host when trustForwardHeader=true)
    requested_host = (
        request.headers.get("X-Forwarded-Host")
        or request.headers.get("x-forwarded-host")
        or (request.url.hostname or "").lower()
    )

    if not requested_host:
        raise HTTPException(status_code=400, detail="cannot determine requested host")

    requested_host = requested_host.lower()

    if allowed_hosts and requested_host not in allowed_hosts:
        # token exists but not permitted for this host
        raise HTTPException(status_code=403, detail="forbidden for host")

    # When allowed_hosts is empty, we can interpret as no access. Be explicit.
    if not allowed_hosts:
        raise HTTPException(status_code=403, detail="no hosts assigned for token")

    # Success tells Traefik to continue the request to the backend service
    return "OK"


@app.get("/debug/token/{token}")
async def debug_token(token: str) -> JSONResponse:
    token_key = f"tokens:{token}"
    token_data = redis_client.hgetall(token_key)
    return JSONResponse({"exists": bool(token_data), "data": token_data})


# --- Admin UI ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    tokens = []
    for key in redis_client.scan_iter("tokens:*"):
        token_value = key.split(":", 1)[1]
        data = redis_client.hgetall(key)
        tokens.append({"token": token_value, "hosts": data.get("hosts", "")})
    return templates.TemplateResponse("index.html", {"request": request, "tokens": tokens})


@app.post("/create_token")
async def create_token(hosts: str = Form(...)) -> JSONResponse:
    token = secrets.token_urlsafe(32)
    redis_client.hset(f"tokens:{token}", mapping={"hosts": hosts})
    return JSONResponse({"token": token})


@app.post("/delete_token")
async def delete_token(token: str = Form(...)) -> RedirectResponse:
    redis_client.delete(f"tokens:{token}")
    return RedirectResponse(url="/", status_code=303)


