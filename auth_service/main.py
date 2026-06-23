import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from admin.api import router as api_router
from admin.routes import router as admin_router
from auth.routes import router as auth_router
from config import Config, StorageBackend
from infra.routes import router as infra_router
from log import LoggingMiddleware, configure_logging
from redis_store import RedisTokenStore
from sqlite_store import SQLiteTokenStore
from storage import TokenStore
from throttle import FailureStore, MemoryFailureStore, RedisFailureStore


async def init_store(cfg: Config) -> TokenStore:
    backend = cfg.storage_backend
    if backend == StorageBackend.REDIS:
        return RedisTokenStore(cfg)
    elif backend == StorageBackend.SQLITE:
        store = SQLiteTokenStore(str(cfg.sqlite_path))
        await store.init()
        return store
    else:
        raise ValueError(f"unknown STORAGE_BACKEND: {backend}")


async def init_auth_throttle(cfg: Config) -> FailureStore:
    backend = cfg.storage_backend
    window = cfg.auth_failure_window_seconds
    max_fail = cfg.auth_max_failures
    if backend == StorageBackend.REDIS:
        return RedisFailureStore(
            cfg, prefix="auth", window_seconds=window, max_failures=max_fail
        )
    else:
        return MemoryFailureStore(window_seconds=window, max_failures=max_fail)


async def init_admin_throttle(cfg: Config) -> FailureStore:
    backend = cfg.storage_backend
    window = cfg.auth_failure_window_seconds
    max_fail = cfg.auth_max_failures
    if backend == StorageBackend.REDIS:
        return RedisFailureStore(
            cfg, prefix="admin", window_seconds=window, max_failures=max_fail
        )
    else:
        return MemoryFailureStore(window_seconds=window, max_failures=max_fail)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(json_logs=True, level="INFO")

    try:
        cfg = Config()  # type: ignore[call-arg]
    except Exception as exc:
        if hasattr(exc, "errors"):
            print("Configuration errors:", file=sys.stderr)
            for err in exc.errors():  # type: ignore[union-attr]
                loc = " → ".join(str(p) for p in err["loc"])
                print(f"  • {loc}: {err['msg']}", file=sys.stderr)
        else:
            print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    app.state.config = cfg

    store = await init_store(cfg)
    app.state.store = store

    auth_throttle = await init_auth_throttle(cfg)
    app.state.auth_throttle = auth_throttle
    admin_throttle = await init_admin_throttle(cfg)
    app.state.admin_throttle = admin_throttle

    yield
    await auth_throttle.close()
    await admin_throttle.close()
    await store.close()


app = FastAPI(title="Wicket", version="0.1.0", lifespan=lifespan)
app.add_middleware(LoggingMiddleware)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(api_router)
app.include_router(infra_router)

Instrumentator().instrument(app).expose(app, include_in_schema=False)
