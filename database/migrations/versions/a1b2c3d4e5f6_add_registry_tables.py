"""add_registry_tables

Revision ID: a1b2c3d4e5f6
Revises: 9d4a6b7c8e12
Create Date: 2026-06-06 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "9d4a6b7c8e12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "poller_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("module", sa.String(length=255), nullable=False),
        sa.Column("api_name", sa.String(length=100), nullable=False),
        sa.Column("output_schema", sa.Text(), nullable=False),
        sa.Column("config", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("module"),
        sa.UniqueConstraint("api_name"),
    )
    op.create_table(
        "processor_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("module", sa.String(length=255), nullable=False),
        sa.Column("api_name", sa.String(length=100), nullable=False),
        sa.Column("input_schema", sa.Text(), nullable=False),
        sa.Column("config", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("module"),
        sa.UniqueConstraint("api_name"),
    )
    op.create_table(
        "processor_poller_link",
        sa.Column("processor_id", sa.Integer(), nullable=False),
        sa.Column("poller_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["processor_id"], ["processor_config.id"]),
        sa.ForeignKeyConstraint(["poller_id"], ["poller_config.id"]),
        sa.PrimaryKeyConstraint("processor_id", "poller_id"),
    )


def downgrade() -> None:
    op.drop_table("processor_poller_link")
    op.drop_table("processor_config")
    op.drop_table("poller_config")
