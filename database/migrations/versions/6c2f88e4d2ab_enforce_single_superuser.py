"""enforce_single_superuser

Revision ID: 6c2f88e4d2ab
Revises: 3f2c1b7e9a42
Create Date: 2026-05-29 22:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6c2f88e4d2ab"
down_revision: str | Sequence[str] | None = "3f2c1b7e9a42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ux_users_single_superuser",
        "users",
        ["role"],
        unique=True,
        sqlite_where=sa.text("role = 'superuser'"),
        postgresql_where=sa.text("role = 'superuser'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ux_users_single_superuser", table_name="users")
