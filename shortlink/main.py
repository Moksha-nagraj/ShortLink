import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shortlink.base62 import decode, encode
from shortlink.config import settings
from shortlink.db import get_session
from shortlink.models import ClickEvent, Link
from shortlink.redis_client import get_redis
from shortlink.schemas import LinkCreate, LinkResponse, StatsResponse

logger = logging.getLogger(__name__)
app = FastAPI(title="ShortLink", version="1.0.0")
STREAM = "shortlink:clicks"
RATE_SCRIPT = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return n
"""


def cache_key(code: str) -> str:
    return f"shortlink:link:{code}"


def link_is_live(link: Link, now: datetime) -> bool:
    return bool(link.is_active and (link.expires_at is None or link.expires_at > now))


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


@app.get("/api/v1/links/{code}/stats", response_model=StatsResponse)
async def link_stats(
    code: str, session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis)
):
    try:
        link_id = decode(code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Link not found") from exc
    link = await session.get(Link, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    last_24h = await session.scalar(
        select(func.count(ClickEvent.id)).where(ClickEvent.link_id == link_id, ClickEvent.clicked_at >= cutoff)
    )
    recent = (await session.scalars(
        select(ClickEvent.clicked_at)
        .where(ClickEvent.link_id == link_id)
        .order_by(ClickEvent.clicked_at.desc())
        .limit(10)
    )).all()
    try:
        live_count = int(await redis.get(f"shortlink:count:{link_id}") or 0)
    except RedisError:
        live_count = 0
    return StatsResponse(
        code=code,
        original_url=link.original_url,
        total_clicks=max(link.click_count, live_count),
        clicks_last_24_hours=last_24h or 0,
        recent_clicks=recent,
    )


@app.get("/{code}", include_in_schema=False)
async def redirect(
    code: str,
    request: Request,
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
        if link is None or not link_is_live(link, now):
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
    client_ip = request.client.host if request.client else "unknown"
    ip_hash = hmac.new(
        settings.ip_hash_secret.encode(), client_ip.encode(), hashlib.sha256
    ).hexdigest()
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.xadd(STREAM, {
                "link_id": str(link_id),
                "clicked_at": now.isoformat(),
                "ip_hash": ip_hash,
                "user_agent": request.headers.get("user-agent", "")[:512],
                "referer": request.headers.get("referer", "")[:2048],
            })
            pipe.incr(f"shortlink:count:{link_id}")
            await pipe.execute()
    except RedisError:
        logger.exception("Click could not be queued for %s", code)
    return RedirectResponse(target, status_code=307, headers={"X-Cache": cache_status})
