"""Simple local redirect load check; reports observed latency, not a guaranteed target."""

import asyncio
import statistics
import time
import os

import httpx

BASE = os.getenv("SHORTLINK_BASE_URL", "http://localhost:8001")
REQUESTS = 1000
CONCURRENCY = 50


async def main():
    limits = httpx.Limits(max_connections=CONCURRENCY)
    async with httpx.AsyncClient(timeout=10, limits=limits) as client:
        created = await client.post(f"{BASE}/api/v1/links", json={"url": "https://example.com/load"})
        created.raise_for_status()
        url = created.json()["short_url"]
        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def hit():
            async with semaphore:
                start = time.perf_counter()
                response = await client.get(url, follow_redirects=False)
                assert response.status_code == 307
                return (time.perf_counter() - start) * 1000, response.headers["x-cache"]

        started = time.perf_counter()
        results = await asyncio.gather(*(hit() for _ in range(REQUESTS)))
        elapsed = time.perf_counter() - started
        latencies = [latency for latency, _ in results]
        hits = sum(status == "HIT" for _, status in results)
        sorted_latencies = sorted(latencies)
        print(f"{REQUESTS} redirects in {elapsed:.2f}s ({REQUESTS / elapsed:.1f} req/s)")
        print(f"p50={statistics.median(latencies):.1f}ms p95={sorted_latencies[int(0.95 * REQUESTS) - 1]:.1f}ms")
        print(f"Redirect cache hits: {hits}/{REQUESTS} ({hits / REQUESTS:.1%})")


if __name__ == "__main__":
    asyncio.run(main())
