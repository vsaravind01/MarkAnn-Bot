"""add_auth_fields_and_refresh_tokens

Revision ID: 3f2c1b7e9a42
Revises: 8e0bcfd0a752
Create Date: 2026-05-29 18:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f2c1b7e9a42"
down_revision: str | Sequence[str] | None = "8e0bcfd0a752"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "users", sa.Column("role", sa.String(length=20), nullable=False, server_default="trader")
    )
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "users", sa.Column("first_name", sa.String(length=100), nullable=False, server_default="")
    )
    op.add_column(
        "users", sa.Column("last_name", sa.String(length=100), nullable=False, server_default="")
    )
    op.add_column(
        "users", sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True)
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.execute("UPDATE users SET email = 'user-' || id || '@local.test' WHERE email IS NULL")
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("email", nullable=False)

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False)
    op.create_index(
        "ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "created_by")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
    op.drop_column("users", "is_active")
    op.drop_column("users", "role")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "email")
