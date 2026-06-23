from fastapi import APIRouter, Depends, HTTPException, Request

from admin.service import create_token, delete_token, list_tokens
from config import Config
from deps import admin_guard, get_config, get_store
from validators import (
    validate_comment,
    validate_email,
    validate_hosts,
    validate_token_hash,
)

router = APIRouter(prefix="/api", dependencies=[Depends(admin_guard)])


@router.post("/tokens", status_code=201)
async def create(
    request: Request,
    store=Depends(get_store),
    cfg: Config = Depends(get_config),
) -> dict:
    body = await request.json()
    hosts = body.get("hosts", "")
    validated_hosts = validate_hosts(hosts)
    stored_hosts = ",".join(validated_hosts)

    email = body.get("email")
    validated_email = validate_email(email)

    ttl_seconds = body.get("ttl_seconds")
    if ttl_seconds is not None:
        if not isinstance(ttl_seconds, int):
            raise HTTPException(status_code=422, detail="ttl_seconds must be integer")
        if ttl_seconds < 0:
            raise HTTPException(status_code=422, detail="ttl_seconds must be >= 0")

    comment = body.get("comment")
    if comment is not None:
        if not isinstance(comment, str):
            raise HTTPException(status_code=422, detail="comment must be string")
        comment = validate_comment(comment)

    raw_token = await create_token(
        store=store,
        hosts=stored_hosts,
        pepper=cfg.pepper.get_secret_value(),
        default_ttl=cfg.token_ttl_seconds,
        ttl_seconds=ttl_seconds,
        email=validated_email,
        comment=comment,
    )
    return {"token": raw_token}


@router.get("/tokens")
async def list_all(
    request: Request,
    store=Depends(get_store),
    page: int = 1,
    size: int = 20,
) -> dict:
    if page < 1:
        raise HTTPException(status_code=422, detail="page must be >= 1")
    if size < 1 or size > 100:
        raise HTTPException(status_code=422, detail="size must be 1..100")
    return await list_tokens(store, page=page, size=size)


@router.delete("/tokens/{token_hash}", status_code=204)
async def delete(
    token_hash: str,
    store=Depends(get_store),
) -> None:
    validate_token_hash(token_hash)
    await delete_token(store, token_hash)
