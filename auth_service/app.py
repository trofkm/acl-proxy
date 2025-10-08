import os
import time
import base64
import hashlib
from typing import List, Optional

from fastapi import FastAPI, Request, HTTPException, Form, Depends
from fastapi.responses import PlainTextResponse, JSONResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import redis


def get_redis_client() -> redis.Redis:
    use_tls = os.getenv("REDIS_TLS", "false").lower() in {"1", "true", "yes"}
    tls_skip_verify = os.getenv("REDIS_TLS_SKIP_VERIFY", "false").lower() in {"1", "true", "yes"}
    ssl_params = {}
    if use_tls:
        ssl_params.update({
            "ssl": True,
            "ssl_cert_reqs": None if tls_skip_verify else "required",
        })

    password = os.getenv("REDIS_PASSWORD")
    username = os.getenv("REDIS_USERNAME")

    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        username=username,
        password=password,
        decode_responses=True,
        **ssl_params,
    )


redis_client = get_redis_client()

app = FastAPI(title="ACL Proxy Auth Service", version="0.1.0")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
security = HTTPBasic()


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    return value if value is not None else default


def hash_token(raw_token: str, pepper: str) -> str:
    # Derive stable hash for storage. Never store raw tokens.
    digest = hashlib.sha256((raw_token + pepper).encode("utf-8")).hexdigest()
    return digest


def admin_guard(credentials: HTTPBasicCredentials = Depends(security)) -> None:
    admin_user = get_env("ADMIN_USER", "admin")
    admin_pass = get_env("ADMIN_PASS")
    if not admin_pass:
        # If not configured, deny rather than allow
        raise HTTPException(status_code=503, detail="admin auth not configured")

    correct = credentials.username == admin_user and secrets.compare_digest(credentials.password, admin_pass)
    if not correct:
        # Trigger browser auth prompt
        raise HTTPException(status_code=401, detail="unauthorized")


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

    # Hash token with pepper
    pepper = get_env("PEPPER", "")
    if not pepper:
        raise HTTPException(status_code=503, detail="server not initialized")

    token_hash = hash_token(token, pepper)

    # Rate limiting (per token hash)
    window_sec = int(get_env("RATE_LIMIT_WINDOW_SEC", "1"))
    max_hits = int(get_env("RATE_LIMIT_MAX", "20"))
    now = int(time.time())
    window_bucket = now - (now % window_sec)
    rl_key = f"ratelimit:{token_hash}:{window_bucket}"
    current = redis_client.incr(rl_key)
    if current == 1:
        redis_client.expire(rl_key, window_sec + 1)
    if current > max_hits:
        raise HTTPException(status_code=429, detail="rate limit exceeded")

    # Load token data from redis using hash key
    token_key = f"tokens:{token_hash}"
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
async def index(request: Request, _: None = Depends(admin_guard)) -> HTMLResponse:
    tokens = []
    for key in redis_client.scan_iter("tokens:*"):
        token_value = key.split(":", 1)[1]
        data = redis_client.hgetall(key)
        ttl_seconds = redis_client.ttl(key)
        created_raw = data.get("created_at", "")
        created_iso = ""
        created_ts = 0
        if created_raw:
            try:
                created_ts = int(created_raw)
                created_iso = time.strftime("%Y-%m-%d %H:%M", time.gmtime(created_ts))
            except Exception:
                created_iso = ""
        tokens.append({
            "token": token_value,
            "hosts": data.get("hosts", ""),
            "email": data.get("email", ""),
            "comment": data.get("comment", ""),
            "created_at": created_iso,
            "_created_ts": created_ts,
            "ttl": ttl_seconds,
        })
    # Sort by creation timestamp ascending (older first)
    tokens.sort(key=lambda t: t.get("_created_ts", 0))

    default_ttl = int(get_env("TOKEN_TTL_SECONDS", "0") or 0)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "tokens": tokens, "default_ttl": default_ttl},
    )


@app.post("/create_token")
async def create_token(
    hosts: str = Form(...),
    ttl_seconds: Optional[str] = Form(None),  # accept raw string; parse if provided
    email: Optional[str] = Form(None),
    comment: Optional[str] = Form(None),
    _: None = Depends(admin_guard),
) -> JSONResponse:
    # Generate raw token returned to user once
    raw_token = secrets.token_urlsafe(32)
    pepper = get_env("PEPPER", "")
    if not pepper:
        raise HTTPException(status_code=503, detail="server not initialized")
    token_hash_value = hash_token(raw_token, pepper)

    key = f"tokens:{token_hash_value}"
    redis_client.hset(key, mapping={
        "hosts": hosts,
        "email": (email or ""),
        "comment": (comment or ""),
        "created_at": str(int(time.time())),
    })
    # Optional TTL per token
    default_ttl = int(get_env("TOKEN_TTL_SECONDS", "0") or 0)
    parsed_ttl: int = 0
    if ttl_seconds is not None and ttl_seconds != "":
        try:
            parsed_ttl = int(ttl_seconds)
        except ValueError:
            raise HTTPException(status_code=422, detail="ttl_seconds must be integer")
    ttl_effective = parsed_ttl if parsed_ttl > 0 else default_ttl
    if ttl_effective and ttl_effective > 0:
        redis_client.expire(key, ttl_effective)

    return JSONResponse({"token": raw_token, "hash": token_hash_value})


@app.post("/delete_token")
async def delete_token(token: str = Form(...), _: None = Depends(admin_guard)) -> RedirectResponse:
    redis_client.delete(f"tokens:{token}")
    return RedirectResponse(url="/", status_code=303)


