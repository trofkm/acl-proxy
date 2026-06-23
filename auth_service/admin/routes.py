from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from config import Config
from deps import admin_guard, get_config, templates

router = APIRouter(dependencies=[Depends(admin_guard)])


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    cfg: Config = Depends(get_config),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "default_ttl": cfg.token_ttl_seconds,
        },
    )
