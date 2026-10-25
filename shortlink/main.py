from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shortlink.base62 import decode, encode
from shortlink.config import settings
from shortlink.db import get_session
from shortlink.models import Link
from shortlink.schemas import LinkCreate, LinkResponse

app = FastAPI(title="ShortLink", version="1.0.0")


@app.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok"}


@app.post("/api/v1/links", response_model=LinkResponse, status_code=201)
async def create_link(data: LinkCreate, session: AsyncSession = Depends(get_session)):
    link = Link(original_url=str(data.url), expires_at=data.expires_at)
    session.add(link)
    await session.commit()
    await session.refresh(link)
    code = encode(link.id)
    return LinkResponse(
        code=code,
        short_url=f"{settings.public_base_url.rstrip('/')}/{code}",
        original_url=link.original_url,
        created_at=link.created_at,
        expires_at=link.expires_at,
    )


@app.get("/{code}", include_in_schema=False)
async def redirect(code: str, session: AsyncSession = Depends(get_session)):
    try:
        link_id = decode(code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Link not found") from exc
    link = await session.get(Link, link_id)
    now = datetime.now(timezone.utc)
    if link is None or not link.is_active or (link.expires_at is not None and link.expires_at <= now):
        raise HTTPException(status_code=404, detail="Link not found")
    return RedirectResponse(link.original_url, status_code=307)
