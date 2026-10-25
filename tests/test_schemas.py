from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from shortlink.schemas import LinkCreate


def test_http_url_and_future_expiry():
    future = datetime.now(timezone.utc) + timedelta(days=1)
    result = LinkCreate(url="https://example.com/path", expires_at=future)
    assert str(result.url) == "https://example.com/path"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///etc/passwd", "not-a-url"])
def test_reject_non_http_urls(url):
    with pytest.raises(ValidationError):
        LinkCreate(url=url)


def test_reject_expired_timestamp():
    with pytest.raises(ValidationError):
        LinkCreate(url="https://example.com", expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))


def test_reject_naive_timestamp():
    with pytest.raises(ValidationError):
        LinkCreate(url="https://example.com", expires_at=datetime.now())
