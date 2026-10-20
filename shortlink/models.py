from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Identity, Index, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Link(Base):
    __tablename__ = "links"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    original_url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    click_count: Mapped[int] = mapped_column(BigInteger, server_default="0")


class ClickEvent(Base):
    __tablename__ = "click_events"
    __table_args__ = (Index("ix_click_events_link_time", "link_id", "clicked_at"),)
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    stream_id: Mapped[str] = mapped_column(String(32), unique=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("links.id", ondelete="CASCADE"))
    clicked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip_hash: Mapped[str] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    referer: Mapped[str | None] = mapped_column(String(2048))
