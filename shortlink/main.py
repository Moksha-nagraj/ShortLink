import json
import logging
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shortlink.base62 import decode, encode
from shortlink.config import settings
from shortlink.db import get_session
from shortlink.models import Link
from shortlink.redis_client import get_redis
from shortlink.schemas import LinkCreate, LinkResponse

logger = logging.getLogger(__name__)
app = FastAPI(title="ShortLink", version="1.0.0")
RATE_SCRIPT = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return n
"""


def cache_key(code: str) -> str:
    return f"shortlink:link:{code}"


async def limit_creation(request: Request, redis: Redis = Depends(get_redis)):
    client_ip = request.client.host if request.client else "unknown"
    key = f"shortlink:rate:create:{client_ip}"
    try:
        count = await redis.eval(RATE_SCRIPT, 1, key, 60)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable") from exc
    if count > settings.rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": "60"})


@app.get("/health")
async def health(session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis)):
    try:
        await session.execute(text("SELECT 1"))
        await redis.ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Dependency unavailable") from exc
    return {"status": "ok"}


@app.post("/api/v1/links", response_model=LinkResponse, status_code=201, dependencies=[Depends(limit_creation)])
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
async def redirect(
    code: str,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    try:
        link_id = decode(code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Link not found") from exc
    now = datetime.now(timezone.utc)
    target = None
    cache_status = "MISS"
    try:
        cached = await redis.get(cache_key(code))
        if cached:
            data = json.loads(cached)
            if data["expires_at"] is None or datetime.fromisoformat(data["expires_at"]) > now:
                target = data["url"]
                cache_status = "HIT"
    except (RedisError, ValueError, KeyError, TypeError):
        logger.warning("Cache read failed for %s", code)
    if target is None:
        link = await session.get(Link, link_id)
        if link is None or not link.is_active or (link.expires_at is not None and link.expires_at <= now):
            raise HTTPException(status_code=404, detail="Link not found")
        target = link.original_url
        ttl = settings.cache_ttl_seconds
        if link.expires_at is not None:
            ttl = min(ttl, max(1, int((link.expires_at - now).total_seconds())))
        try:
            await redis.setex(cache_key(code), ttl, json.dumps({
                "url": target,
                "expires_at": link.expires_at.isoformat() if link.expires_at else None,
            }))
        except RedisError:
            logger.warning("Cache write failed for %s", code)
    return RedirectResponse(target, status_code=307, headers={"X-Cache": cache_status})
