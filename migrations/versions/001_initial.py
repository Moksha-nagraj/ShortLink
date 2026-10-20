"""Initial links and click events.

Revision ID: 001_initial
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "links",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("click_count", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.create_table(
        "click_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("stream_id", sa.String(32), nullable=False, unique=True),
        sa.Column("link_id", sa.BigInteger(), sa.ForeignKey("links.id", ondelete="CASCADE"), nullable=False),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_hash", sa.String(64), nullable=False),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("referer", sa.String(2048), nullable=True),
    )
    op.create_index("ix_click_events_link_time", "click_events", ["link_id", "clicked_at"])


def downgrade():
    op.drop_index("ix_click_events_link_time", table_name="click_events")
    op.drop_table("click_events")
    op.drop_table("links")
