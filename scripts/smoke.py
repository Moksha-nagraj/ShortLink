"""Run after docker compose up --build -d."""

import time
import os

import httpx

BASE = os.getenv("SHORTLINK_BASE_URL", "http://localhost:8001")


def main():
    with httpx.Client(timeout=5) as client:
        health = client.get(f"{BASE}/health")
        health.raise_for_status()
        created = client.post(f"{BASE}/api/v1/links", json={"url": "https://example.com/demo"})
        created.raise_for_status()
        link = created.json()
        assert link["short_url"] == f"{BASE}/{link['code']}"
        for _ in range(3):
            redirected = client.get(link["short_url"], follow_redirects=False)
            assert redirected.status_code == 307
            assert redirected.headers["location"] == "https://example.com/demo"
        deadline = time.monotonic() + 10
        while True:
            stats = client.get(f"{BASE}/api/v1/links/{link['code']}/stats")
            stats.raise_for_status()
            if stats.json()["total_clicks"] >= 3 and stats.json()["clicks_last_24_hours"] >= 3:
                break
            if time.monotonic() > deadline:
                raise AssertionError(f"Analytics did not catch up: {stats.json()}")
            time.sleep(0.2)
        missing = client.get(f"{BASE}/invalid!code", follow_redirects=False)
        assert missing.status_code == 404
        print(f"PASS: {link['short_url']} redirects and records three clicks")


if __name__ == "__main__":
    main()
