from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _upgrade_on_connection(connection) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.attributes["connection"] = connection
    command.upgrade(config, "head")
    return config


def test_baseline_migrates_fresh_and_existing_sqlite_databases() -> None:
    fresh_engine = create_engine("sqlite://")
    try:
        with fresh_engine.connect() as connection:
            config = _upgrade_on_connection(connection)
            tables = set(inspect(connection).get_table_names())
            assert {
                "users",
                "anime",
                "anime_genre",
                "favourite",
                "comment",
                "watch_progress",
                "anilist_cache",
                "anime_embedding",
                "admin_audit",
                "alembic_version",
            } <= tables
            assert "user_id" in {
                column["name"] for column in inspect(connection).get_columns("anime")
            }
            assert {"is_admin", "is_active", "suspension_reason"} <= {
                column["name"] for column in inspect(connection).get_columns("users")
            }
            assert {"anilist_id", "locally_edited", "created_at"} <= {
                column["name"] for column in inspect(connection).get_columns("anime")
            }
            command.check(config)
    finally:
        fresh_engine.dispose()

    legacy_engine = create_engine("sqlite://")
    try:
        with legacy_engine.connect() as connection:
            connection.execute(
                text(
                    "CREATE TABLE users (id INTEGER PRIMARY KEY, name VARCHAR(50) NOT NULL, "
                    "email VARCHAR(254) NOT NULL, hashed_password VARCHAR(255) NOT NULL, "
                    "bio TEXT, created_at TIMESTAMP, cover_image VARCHAR(500))"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE anime (id INTEGER PRIMARY KEY, title VARCHAR(100) NOT NULL, "
                    "genre VARCHAR(100) NOT NULL, rating FLOAT, episode INTEGER, "
                    "description TEXT NOT NULL, studio VARCHAR(100), released_date DATE, "
                    "cover_image VARCHAR(500))"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE comment (id INTEGER PRIMARY KEY, comment TEXT NOT NULL, "
                    "user_id INTEGER NOT NULL, anime_id INTEGER NOT NULL, created_at TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE watch_progress (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, "
                    "anime_id INTEGER NOT NULL, status VARCHAR(20) NOT NULL, "
                    "episodes_watched INTEGER NOT NULL, updated_at TIMESTAMP NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO anime (id, title, genre, description) "
                    "VALUES (42, 'Legacy title', 'Drama', 'Keep this row')"
                )
            )
            connection.commit()

            _upgrade_on_connection(connection)

            columns = {
                column["name"] for column in inspect(connection).get_columns("anime")
            }
            assert {"user_id", "source_url"} <= columns
            assert {"is_spoiler", "spoiler_episode"} <= {
                column["name"] for column in inspect(connection).get_columns("comment")
            }
            assert {"completed_at", "queue_position"} <= {
                column["name"]
                for column in inspect(connection).get_columns("watch_progress")
            }
            retained = connection.execute(
                text("SELECT title, description, created_at FROM anime WHERE id = 42")
            ).one()
            assert retained == ("Legacy title", "Keep this row", None)

            _upgrade_on_connection(connection)
            assert connection.execute(
                text("SELECT COUNT(*) FROM anime WHERE id = 42")
            ).scalar_one() == 1
    finally:
        legacy_engine.dispose()


def test_admin_migration_backfills_unique_anilist_ids() -> None:
    engine = create_engine("sqlite://")
    try:
        with engine.connect() as connection:
            config = Config(str(PROJECT_ROOT / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "20261016_0001")
            connection.execute(
                text(
                    "INSERT INTO anime (title, genre, description, source_url) "
                    "VALUES ('First title', 'Drama', 'First', 'https://anilist.co/anime/77')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO anime (title, genre, description, source_url) "
                    "VALUES ('Duplicate title', 'Drama', 'Duplicate', 'https://anilist.co/anime/77')"
                )
            )
            connection.commit()
            command.upgrade(config, "head")
            matches = connection.execute(
                text("SELECT anilist_id FROM anime ORDER BY id")
            ).scalars().all()
            assert matches == [77, None]
    finally:
        engine.dispose()
