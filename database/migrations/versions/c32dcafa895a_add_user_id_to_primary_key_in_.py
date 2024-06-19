"""add user_id to primary key in UserMessageSchema

Revision ID: c32dcafa895a
Revises:
Create Date: 2024-06-19 20:24:32.817566

Description: Add user_id to primary key in UserMessageSchema

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c32dcafa895a"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Note: This is a workaround for SQLite, which does not allow ALTER TABLE statements
    # to modify primary keys. This workaround creates a new table with the desired primary key,
    # copies the data over, and then drops the old table.
    with op.batch_alter_table("user_messages", recreate="always") as batch_op:
        batch_op.create_primary_key("pk_user_messages", ["user_id", "id"])


def downgrade() -> None:
    with op.batch_alter_table("user_messages", recreate="always") as batch_op:
        batch_op.drop_constraint("pk_user_messages", type_="primary")
        batch_op.create_primary_key("pk_user_messages", ["id"])
