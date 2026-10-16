from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models.anilist_cache import AniListCache

logger = logging.getLogger(__name__)
MAX_STALE_AGE = timedelta(days=30)


def get_cached_response(cache_key: str) -> tuple[dict, bool] | None:
    now = datetime.now(timezone.utc)
    try:
        with SessionLocal() as db:
            entry = db.get(AniListCache, cache_key)
            if entry is None:
                return None
            expires_at = entry.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < now - MAX_STALE_AGE:
                db.delete(entry)
                db.commit()
                return None
            return entry.payload, expires_at > now
    except SQLAlchemyError:
        logger.exception("Could not read the AniList response cache")
        return None


def store_cached_response(cache_key: str, payload: dict, ttl: timedelta) -> None:
    now = datetime.now(timezone.utc)
    try:
        with SessionLocal() as db:
            entry = db.get(AniListCache, cache_key)
            if entry is None:
                entry = AniListCache(cache_key=cache_key, payload=payload, expires_at=now + ttl)
                db.add(entry)
            else:
                entry.payload = payload
                entry.expires_at = now + ttl
            db.execute(
                delete(AniListCache).where(AniListCache.expires_at < now - MAX_STALE_AGE)
            )
            db.commit()
    except SQLAlchemyError:
        logger.exception("Could not store the AniList response cache")
