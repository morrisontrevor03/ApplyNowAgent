"""add open_to_similar_companies to user_preferences

Revision ID: 002
Revises: 001
Create Date: 2026-04-11

"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column("open_to_similar_companies", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "open_to_similar_companies")
