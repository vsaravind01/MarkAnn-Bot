"""add_announcement_processing_mode

Revision ID: 9d4a6b7c8e12
Revises: 6c2f88e4d2ab
Create Date: 2026-06-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d4a6b7c8e12"
down_revision: str | Sequence[str] | None = "6c2f88e4d2ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "announcements",
        sa.Column(
            "processing_mode",
            sa.String(length=20),
            nullable=False,
            server_default="text",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("announcements", "processing_mode")
