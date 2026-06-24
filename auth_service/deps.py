import secrets

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

from config import Config
from log import logger
from storage import TokenStore
from throttle import FailureStore

templates = Jinja2Templates(directory="templates")
security = HTTPBasic()


def get_store(request: Request) -> TokenStore:
    return request.app.state.store


def get_config(request: Request) -> Config:
    return request.app.state.config


def get_auth_throttle(request: Request) -> FailureStore:
    return request.app.state.auth_throttle


def get_admin_throttle(request: Request) -> FailureStore:
    return request.app.state.admin_throttle


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


async def check_throttle(request: Request, cfg: Config = Depends(get_config)) -> None:
    throttle = get_auth_throttle(request)
    client_ip = get_client_ip(request)
    if await throttle.is_blocked(client_ip):
        logger.warning("auth_throttled", ip=client_ip)
        raise HTTPException(
            status_code=429,
            detail="too many failed auth attempts, retry later",
            headers={"Retry-After": str(cfg.auth_failure_window_seconds)},
        )


async def admin_guard(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(security),
    cfg: Config = Depends(get_config),
) -> None:
    throttle = get_admin_throttle(request)
    client_ip = get_client_ip(request)
    if await throttle.is_blocked(client_ip):
        raise HTTPException(
            status_code=429,
            detail="too many failed admin auth attempts, retry later",
            headers={"Retry-After": str(cfg.auth_failure_window_seconds)},
        )

    admin_pass = cfg.admin_pass.get_secret_value()
    if not admin_pass:
        raise HTTPException(status_code=503, detail="admin auth not configured")

    user_ok = secrets.compare_digest(credentials.username, cfg.admin_user)
    pass_ok = secrets.compare_digest(credentials.password, admin_pass)
    if not (user_ok and pass_ok):
        await throttle.record_failure(client_ip)
        raise HTTPException(status_code=401, detail="unauthorized")
