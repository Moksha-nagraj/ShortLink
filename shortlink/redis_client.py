from redis.asyncio import Redis

from shortlink.config import settings

redis = Redis.from_url(settings.redis_url, decode_responses=True)


async def get_redis():
    return redis
