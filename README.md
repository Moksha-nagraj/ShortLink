# ShortLink

FastAPI URL shortener with Base62 codes, PostgreSQL storage, Redis read-through caching, rate limiting, and click analytics.

## Start

Requirements: Docker Desktop with the Linux engine running and Docker Compose.

```powershell
Copy-Item .env.example .env
# Replace IP_HASH_SECRET with a random value before use.
docker compose up --build -d
docker compose ps
python -m pip install -r requirements-dev.txt
python scripts/smoke.py
```

Open [API docs](http://localhost:8001/docs). Stop with `docker compose down`. Data remains in named PostgreSQL and Redis volumes; `docker compose down -v` removes it.

The example credentials and localhost public URL are for local development. Set `PUBLIC_BASE_URL` to your public origin for deployment. Do not expose PostgreSQL or Redis directly to the internet.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/links` | Create a short link; optional future `expires_at` in ISO 8601 |
| GET | `/{code}` | HTTP 307 redirect and queue a click |
| GET | `/api/v1/links/{code}/stats` | Total, last 24 hours, recent click times |
| GET | `/health` | PostgreSQL and Redis readiness |

```powershell
$body = @{ url = 'https://example.com/article' } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:8001/api/v1/links -Method Post -ContentType application/json -Body $body
```

Creation is limited to `RATE_LIMIT_PER_MINUTE` requests per client IP per 60 second window. The API uses the direct peer IP; configure trusted proxy handling if deployed behind a reverse proxy. Analytics is public in this demo, so add authentication before storing private links.

## Design

PostgreSQL identity IDs map bijectively to Base62 codes. Redirects first look in Redis, then read PostgreSQL and cache the result for at most `CACHE_TTL_SECONDS` (and no longer than the link expiry). Redirects enqueue click details in a Redis Stream and increment an immediate counter in one Redis transaction. The worker consumes the stream, inserts idempotent events into PostgreSQL, and updates each link's durable count. On restart it replays its pending entries. Redis AOF and PostgreSQL named volumes persist local data.

Total click counts are available immediately from Redis; the 24 hour count and recent event list follow the worker by a short delay. During a Redis outage, redirects still work from PostgreSQL, but clicks cannot be queued and are not recorded. Changing or deactivating links would need cache invalidation; this version only creates immutable links.

## Verify

```powershell
python -m pytest -q
python scripts/benchmark.py
docker compose exec redis redis-cli INFO stats
```

The benchmark reports redirect cache hits from the `X-Cache` response header. Redis keyspace counters include analytics operations, so they are not a redirect-only metric. Redirect load and cache hit rate depend on traffic distribution and machine capacity; no fixed percentage is claimed.

## Scale and production notes

API replicas can share PostgreSQL and Redis. The Compose file runs one worker; for multiple workers, use distinct Redis consumer names and pending-entry reclaiming. Add TLS, a reverse proxy, authenticated link management and analytics, observability, backups, and retention policy before an internet deployment. Database writes and Redis Stream memory need capacity planning for sustained traffic.
