from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.anime_sources import anilist_id_from_source_url
from app.auth import get_current_user
from app.database import get_db
from app.models.admin_audit import AdminAudit
from app.models.anime import Anime
from app.models.anilist_cache import AniListCache
from app.models.comment import Comment
from app.models.user import User
from app.schemas.anime import AnimeCreate, AnimeUpdate
from app.schemas.user import UserResponse

router = APIRouter(prefix="/admin", tags=["Administration"])


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access is required.",
        )
    return user


def _record_action(
    db: Session,
    actor: User,
    action: str,
    target_type: str,
    target_id: int | None,
    details: dict,
) -> None:
    db.add(
        AdminAudit(
            actor_user_id=actor.id,
            actor_name=actor.name,
            actor_email=actor.email,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )
    )


def _timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


@router.get("/overview")
def get_overview(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_anime = db.query(func.count(Anime.id)).scalar() or 0
    total_comments = db.query(func.count(Comment.id)).scalar() or 0
    registrations = (
        db.query(func.count(User.id)).filter(User.created_at >= week_ago).scalar() or 0
    )
    pending_comments = (
        db.query(func.count(Comment.id)).filter(Comment.reviewed_at.is_(None)).scalar() or 0
    )
    cache_total = db.query(func.count(AniListCache.cache_key)).scalar() or 0
    cache_fresh = (
        db.query(func.count(AniListCache.cache_key))
        .filter(AniListCache.expires_at > func.now())
        .scalar()
        or 0
    )

    registrations_recent = (
        db.query(User).order_by(User.created_at.desc(), User.id.desc()).limit(8).all()
    )
    comments_recent = (
        db.query(Comment)
        .options(joinedload(Comment.user), joinedload(Comment.anime))
        .order_by(Comment.created_at.desc(), Comment.id.desc())
        .limit(8)
        .all()
    )
    anime_recent = (
        db.query(Anime)
        .filter(Anime.created_at.is_not(None))
        .order_by(Anime.created_at.desc(), Anime.id.desc())
        .limit(8)
        .all()
    )
    audits_recent = (
        db.query(AdminAudit).order_by(AdminAudit.created_at.desc(), AdminAudit.id.desc()).limit(8).all()
    )

    activity = [
        {
            "kind": "registration",
            "at": _timestamp(user.created_at),
            "summary": f"{user.name} joined Anime Hub",
            "target_id": user.id,
        }
        for user in registrations_recent
    ]
    activity.extend(
        {
            "kind": "comment",
            "at": _timestamp(comment.created_at),
            "summary": f"{comment.user.name} commented on {comment.anime.title}",
            "target_id": comment.id,
        }
        for comment in comments_recent
    )
    activity.extend(
        {
            "kind": "anime",
            "at": _timestamp(anime.created_at),
            "summary": f"{anime.title} was added to the catalog",
            "target_id": anime.id,
        }
        for anime in anime_recent
    )
    activity.extend(
        {
            "kind": "moderation",
            "at": _timestamp(audit.created_at),
            "summary": f"{audit.actor_name} performed {audit.action} on {audit.target_type}",
            "target_id": audit.target_id,
        }
        for audit in audits_recent
    )
    activity.sort(key=lambda entry: entry["at"] or "", reverse=True)
    return {
        "totals": {
            "users": total_users,
            "active_users": db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0,
            "anime": total_anime,
            "comments": total_comments,
            "pending_comments": pending_comments,
        },
        "registrations_last_7_days": registrations,
        "anilist_cache": {"entries": cache_total, "fresh": cache_fresh, "stale": cache_total - cache_fresh},
        "recent_activity": activity[:20],
    }


@router.get("/anime")
def list_managed_anime(
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    query = db.query(Anime)
    if q and q.strip():
        query = query.filter(Anime.title.ilike(f"%{q.strip()}%"))
    total = query.count()
    anime_list = (
        query.order_by(Anime.title.asc(), Anime.id.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                **{
                    key: getattr(anime, key)
                    for key in (
                        "id", "title", "genre", "rating", "episode", "studio",
                        "description", "released_date", "cover_image", "source_url",
                        "user_id", "anilist_id", "locally_edited", "created_at",
                    )
                },
                "source_type": "AniList" if anime.anilist_id is not None else "Local",
            }
            for anime in anime_list
        ],
        "page": page,
        "limit": limit,
        "total": total,
    }


@router.post("/anime", status_code=status.HTTP_201_CREATED)
def create_managed_anime(
    anime_data: AnimeCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> dict:
    anilist_id = anilist_id_from_source_url(anime_data.source_url)
    if anilist_id is not None:
        existing = db.query(Anime).filter(Anime.anilist_id == anilist_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"message": "This AniList title is already imported.", "existing_id": existing.id},
            )
    duplicate = db.query(Anime).filter(func.lower(Anime.title) == anime_data.title.lower()).first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "An anime with this title already exists.", "existing_id": duplicate.id},
        )
    anime = Anime(
        **anime_data.model_dump(),
        anilist_id=anilist_id,
        locally_edited=False,
    )
    db.add(anime)
    db.flush()
    _record_action(db, actor, "anime_created", "anime", anime.id, {"title": anime.title})
    db.commit()
    db.refresh(anime)
    return {"id": anime.id, "title": anime.title}


@router.patch("/anime/{anime_id}")
def update_managed_anime(
    anime_id: int,
    anime_data: AnimeUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> dict:
    anime = db.query(Anime).filter(Anime.id == anime_id).first()
    if anime is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anime not found.")
    updates = anime_data.model_dump(exclude_unset=True)
    if "title" in updates:
        duplicate = (
            db.query(Anime)
            .filter(func.lower(Anime.title) == updates["title"].lower(), Anime.id != anime_id)
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"message": "An anime with this title already exists.", "existing_id": duplicate.id},
            )
    if "source_url" in updates:
        new_anilist_id = anilist_id_from_source_url(updates["source_url"])
        if new_anilist_id is not None:
            duplicate_import = (
                db.query(Anime)
                .filter(Anime.anilist_id == new_anilist_id, Anime.id != anime_id)
                .first()
            )
            if duplicate_import:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "message": "This AniList title is already imported.",
                        "existing_id": duplicate_import.id,
                    },
                )
        anime.anilist_id = new_anilist_id
    for field, value in updates.items():
        setattr(anime, field, value)
    anime.locally_edited = True
    _record_action(
        db,
        actor,
        "anime_updated",
        "anime",
        anime.id,
        {"title": anime.title, "fields": sorted(updates)},
    )
    db.commit()
    db.refresh(anime)
    return {"id": anime.id, "title": anime.title, "locally_edited": anime.locally_edited}


@router.delete("/anime/{anime_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_managed_anime(
    anime_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> None:
    anime = db.query(Anime).filter(Anime.id == anime_id).first()
    if anime is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anime not found.")
    _record_action(db, actor, "anime_deleted", "anime", anime.id, {"title": anime.title})
    db.delete(anime)
    db.commit()


@router.get("/users")
def list_users(
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    query = db.query(User)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter((User.name.ilike(pattern)) | (User.email.ilike(pattern)))
    total = query.count()
    users = query.order_by(User.created_at.desc(), User.id.desc()).offset((page - 1) * limit).limit(limit).all()
    return {
        "items": [
            {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "created_at": _timestamp(user.created_at),
                "is_admin": user.is_admin,
                "is_active": user.is_active,
                "suspended_at": _timestamp(user.suspended_at),
                "suspension_reason": user.suspension_reason,
            }
            for user in users
        ],
        "page": page,
        "limit": limit,
        "total": total,
    }


@router.patch("/users/{user_id}/status")
def set_user_status(
    user_id: int,
    is_active: bool,
    reason: str | None = Query(default=None, max_length=500),
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> UserResponse:
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if target.id == actor.id and not is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot suspend your own account.")
    if target.is_admin and not is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrator accounts must be managed through the local CLI.",
        )
    target.is_active = is_active
    target.suspended_at = None if is_active else datetime.now(timezone.utc)
    target.suspension_reason = None if is_active else (reason.strip() if reason and reason.strip() else None)
    action = "user_reactivated" if is_active else "user_suspended"
    _record_action(
        db,
        actor,
        action,
        "user",
        target.id,
        {"name": target.name, "reason": target.suspension_reason},
    )
    db.commit()
    db.refresh(target)
    return UserResponse.model_validate(target)


@router.get("/comments")
def list_comment_queue(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    query = (
        db.query(Comment)
        .options(joinedload(Comment.user), joinedload(Comment.anime))
        .filter(Comment.reviewed_at.is_(None))
    )
    total = query.count()
    comments = (
        query.order_by(Comment.created_at.asc(), Comment.id.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": comment.id,
                "comment": comment.comment,
                "created_at": _timestamp(comment.created_at),
                "user_id": comment.user_id,
                "user_name": comment.user.name,
                "anime_id": comment.anime_id,
                "anime_title": comment.anime.title,
                "is_spoiler": comment.is_spoiler,
            }
            for comment in comments
        ],
        "page": page,
        "limit": limit,
        "total": total,
    }


@router.post("/comments/{comment_id}/review", status_code=status.HTTP_204_NO_CONTENT)
def review_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> None:
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")
    if comment.reviewed_at is None:
        comment.reviewed_at = datetime.now(timezone.utc)
        comment.reviewed_by = actor.id
        _record_action(db, actor, "comment_approved", "comment", comment.id, {"anime_id": comment.anime_id})
        db.commit()


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_managed_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> None:
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")
    _record_action(
        db,
        actor,
        "comment_deleted",
        "comment",
        comment.id,
        {"user_id": comment.user_id, "anime_id": comment.anime_id, "preview": comment.comment[:120]},
    )
    db.delete(comment)
    db.commit()


@router.get("/audit")
def list_moderation_audit(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    actions = db.query(AdminAudit).order_by(AdminAudit.created_at.desc(), AdminAudit.id.desc()).limit(limit).all()
    return [
        {
            "id": action.id,
            "actor_user_id": action.actor_user_id,
            "actor_name": action.actor_name,
            "actor_email": action.actor_email,
            "action": action.action,
            "target_type": action.target_type,
            "target_id": action.target_id,
            "details": action.details,
            "created_at": _timestamp(action.created_at),
        }
        for action in actions
    ]
