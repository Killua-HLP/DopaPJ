"""Add administrator accounts, audit history, and moderation state.

Revision ID: 20261016_0002
Revises: 20261016_0001
Create Date: 2026-10-16
"""
from typing import Sequence
import re

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20261016_0002"
down_revision: str | None = "20261016_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    return column_name in {
        column["name"] for column in inspect(op.get_bind()).get_columns(table_name)
    }


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column("users", "is_admin"):
        op.add_column(
            "users",
            sa.Column("is_admin", sa.Boolean(), server_default=sa.false(), nullable=False),
        )
    if not _has_column("users", "is_active"):
        op.add_column(
            "users",
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        )
    if not _has_column("users", "suspended_at"):
        op.add_column("users", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))
    if not _has_column("users", "suspension_reason"):
        op.add_column("users", sa.Column("suspension_reason", sa.String(length=500), nullable=True))

    if not _has_column("anime", "anilist_id"):
        op.add_column("anime", sa.Column("anilist_id", sa.Integer(), nullable=True))
    if not _has_column("anime", "locally_edited"):
        op.add_column(
            "anime",
            sa.Column("locally_edited", sa.Boolean(), server_default=sa.false(), nullable=False),
        )
    if not _has_column("anime", "created_at"):
        op.add_column("anime", sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=True))

    if not _has_column("comment", "reviewed_at"):
        op.add_column("comment", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    if not _has_column("comment", "reviewed_by"):
        reviewed_by = sa.Column(
                "reviewed_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_comment_reviewed_by_users"),
                nullable=True,
            )
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("comment") as batch:
                batch.add_column(reviewed_by)
        else:
            op.add_column("comment", reviewed_by)
    comment_indexes = {index["name"] for index in inspect(bind).get_indexes("comment")}
    if "ix_comment_reviewed_at" not in comment_indexes:
        op.create_index("ix_comment_reviewed_at", "comment", ["reviewed_at"])
    existing_comment_date = "created_at" if _has_column("comment", "created_at") else "CURRENT_TIMESTAMP"
    bind.execute(
        sa.text(f"UPDATE comment SET reviewed_at = {existing_comment_date} WHERE reviewed_at IS NULL")
    )

    anime_rows = bind.execute(
        sa.text("SELECT id, source_url FROM anime WHERE source_url IS NOT NULL ORDER BY id")
    ).all()
    used_anilist_ids: set[int] = set()
    for anime_id, source_url in anime_rows:
        match = re.search(r"/anime/(\d+)(?:/|$)", source_url)
        if match is None:
            continue
        anilist_id = int(match.group(1))
        if anilist_id in used_anilist_ids:
            continue
        bind.execute(
            sa.text("UPDATE anime SET anilist_id = :anilist_id WHERE id = :anime_id"),
            {"anilist_id": anilist_id, "anime_id": anime_id},
        )
        used_anilist_ids.add(anilist_id)

    indexes = {index["name"] for index in inspect(bind).get_indexes("anime")}
    if "ix_anime_anilist_id" not in indexes:
        op.create_index("ix_anime_anilist_id", "anime", ["anilist_id"], unique=True)
    if not _has_audit_table():
        op.create_table(
            "admin_audit",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "actor_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_admin_audit_actor_user_id_users"),
                nullable=True,
            ),
            sa.Column("actor_name", sa.String(length=50), nullable=False),
            sa.Column("actor_email", sa.String(length=254), nullable=False),
            sa.Column("action", sa.String(length=50), nullable=False),
            sa.Column("target_type", sa.String(length=30), nullable=False),
            sa.Column("target_id", sa.Integer(), nullable=True),
            sa.Column("details", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_admin_audit_action", "admin_audit", ["action"])
        op.create_index("ix_admin_audit_target_id", "admin_audit", ["target_id"])
        op.create_index("ix_admin_audit_created_at", "admin_audit", ["created_at"])


def _has_audit_table() -> bool:
    return inspect(op.get_bind()).has_table("admin_audit")


def downgrade() -> None:
    raise RuntimeError(
        "The admin migration contains moderation audit history and cannot be downgraded safely."
    )
