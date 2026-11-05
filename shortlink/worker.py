import asyncio
import logging
from datetime import datetime

from redis.exceptions import ResponseError
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert

from shortlink.db import Session
from shortlink.main import STREAM
from shortlink.models import ClickEvent, Link
from shortlink.redis_client import redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
GROUP = "analytics"
CONSUMER = "worker-1"


async def persist_event(stream_id: str, fields: dict[str, str]) -> None:
    async with Session() as session:
        statement = (
            insert(ClickEvent)
            .values(
                stream_id=stream_id,
                link_id=int(fields["link_id"]),
                clicked_at=datetime.fromisoformat(fields["clicked_at"]),
                ip_hash=fields["ip_hash"],
                user_agent=fields.get("user_agent") or None,
                referer=fields.get("referer") or None,
            )
            .on_conflict_do_nothing(index_elements=["stream_id"])
            .returning(ClickEvent.id)
        )
        inserted = await session.scalar(statement)
        if inserted is not None:
            await session.execute(
                update(Link)
                .where(Link.id == int(fields["link_id"]))
                .values(click_count=Link.click_count + 1)
            )
        await session.commit()
    await redis.xack(STREAM, GROUP, stream_id)


async def run() -> None:
    try:
        await redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise
    while True:
        try:
            for position in ("0", ">"):
                records = await redis.xreadgroup(
                    GROUP, CONSUMER, {STREAM: position}, count=100, block=2000 if position == ">" else None
                )
                for _, events in records:
                    for stream_id, fields in events:
                        await persist_event(stream_id, fields)
        except Exception:
            logger.exception("Analytics worker failed; retrying")
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(run())
