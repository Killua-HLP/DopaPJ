"""Adopt existing Anime Hub databases and create the current schema.

Revision ID: 20261016_0001
Revises:
Create Date: 2026-10-16
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20261016_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    return column_name in {
        column["name"] for column in inspect(op.get_bind()).get_columns(table_name)
    }


def _ensure_column(table_name: str, column: sa.Column) -> None:
    if not _has_column(table_name, column.name):
        if op.get_bind().dialect.name == "sqlite":
            with op.batch_alter_table(table_name) as batch:
                batch.add_column(column)
        else:
            op.add_column(table_name, column)


def _ensure_index(
    name: str,
    table_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    indexes = {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name)}
    if name not in indexes:
        op.create_index(name, table_name, columns, unique=unique)


def upgrade() -> None:
    if not _has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=50), nullable=False),
            sa.Column("email", sa.String(length=254), nullable=False),
            sa.Column("hashed_password", sa.String(length=255), nullable=False),
            sa.Column("bio", sa.Text(), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("cover_image", sa.String(length=500), nullable=True),
        )

    if not _has_table("anime"):
        op.create_table(
            "anime",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey(
                    "users.id",
                    ondelete="SET NULL",
                    name="fk_anime_user_id_users",
                ),
                nullable=True,
            ),
            sa.Column("title", sa.String(length=100), nullable=False),
            sa.Column("genre", sa.String(length=100), nullable=False),
            sa.Column("rating", sa.Float(), nullable=True),
            sa.Column("episode", sa.Integer(), nullable=True),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("studio", sa.String(length=100), nullable=True),
            sa.Column("released_date", sa.Date(), nullable=True),
            sa.Column("cover_image", sa.String(length=500), nullable=True),
            sa.Column("source_url", sa.String(length=500), nullable=True),
        )
    else:
        _ensure_column(
            "anime",
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey(
                    "users.id",
                    ondelete="SET NULL",
                    name="fk_anime_user_id_users",
                ),
                nullable=True,
            ),
        )
        _ensure_column("anime", sa.Column("source_url", sa.String(length=500), nullable=True))

    if not _has_table("anime_genre"):
        op.create_table(
            "anime_genre",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=50), nullable=False),
        )

    if not _has_table("favourite"):
        op.create_table(
            "favourite",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("anime_id", sa.Integer(), sa.ForeignKey("anime.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("user_id", "anime_id", name="uq_favourite_user_anime_pair"),
        )

    if not _has_table("comment"):
        op.create_table(
            "comment",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("comment", sa.Text(), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("anime_id", sa.Integer(), sa.ForeignKey("anime.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("is_spoiler", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("spoiler_episode", sa.Integer(), nullable=True),
        )
    else:
        _ensure_column(
            "comment",
            sa.Column("is_spoiler", sa.Boolean(), server_default=sa.false(), nullable=False),
        )
        _ensure_column("comment", sa.Column("spoiler_episode", sa.Integer(), nullable=True))

    if not _has_table("watch_progress"):
        op.create_table(
            "watch_progress",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("anime_id", sa.Integer(), sa.ForeignKey("anime.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("episodes_watched", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("queue_position", sa.Integer(), nullable=True),
            sa.UniqueConstraint("user_id", "anime_id", name="uq_watch_progress_user_anime"),
            sa.CheckConstraint(
                "status IN ('plan_to_watch', 'watching', 'completed', 'on_hold', 'dropped')",
                name="ck_watch_progress_status",
            ),
            sa.CheckConstraint("episodes_watched >= 0", name="ck_watch_progress_episodes"),
        )
    else:
        _ensure_column(
            "watch_progress",
            sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        )
        _ensure_column("watch_progress", sa.Column("queue_position", sa.Integer(), nullable=True))

    if not _has_table("anilist_cache"):
        op.create_table(
            "anilist_cache",
            sa.Column("cache_key", sa.String(length=64), primary_key=True),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _has_table("anime_embedding"):
        op.create_table(
            "anime_embedding",
            sa.Column(
                "anime_id",
                sa.Integer(),
                sa.ForeignKey("anime.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            sa.Column("vector", sa.JSON(), nullable=False),
        )

    _ensure_index("ix_users_name", "users", ["name"], unique=True)
    _ensure_index("ix_users_email", "users", ["email"], unique=True)
    _ensure_index("ix_anime_title", "anime", ["title"], unique=True)
    _ensure_index("ix_anime_user_id", "anime", ["user_id"])
    _ensure_index("ix_anime_genre_name", "anime_genre", ["name"], unique=True)
    _ensure_index("ix_favourite_user_id", "favourite", ["user_id"])
    _ensure_index("ix_favourite_anime_id", "favourite", ["anime_id"])
    _ensure_index("ix_comment_user_id", "comment", ["user_id"])
    _ensure_index("ix_comment_anime_id", "comment", ["anime_id"])
    _ensure_index("ix_watch_progress_user_id", "watch_progress", ["user_id"])
    _ensure_index("ix_watch_progress_anime_id", "watch_progress", ["anime_id"])
    _ensure_index("ix_anilist_cache_expires_at", "anilist_cache", ["expires_at"])


def downgrade() -> None:
    raise RuntimeError(
        "The baseline migration cannot be downgraded safely. Restore a database backup instead."
    )
