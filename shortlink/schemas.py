from datetime import datetime, timezone

from pydantic import BaseModel, Field, HttpUrl, field_validator


class LinkCreate(BaseModel):
    url: HttpUrl
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def future_expiry(cls, value: datetime | None):
        if value is not None:
            if value.tzinfo is None or value <= datetime.now(timezone.utc):
                raise ValueError("expires_at must be a future timestamp with timezone")
        return value


class LinkResponse(BaseModel):
    code: str
    short_url: str
    original_url: str
    created_at: datetime
    expires_at: datetime | None


class StatsResponse(BaseModel):
    code: str
    original_url: str
    total_clicks: int
    clicks_last_24_hours: int
    recent_clicks: list[datetime] = Field(default_factory=list)
