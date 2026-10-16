from datetime import date, datetime, timezone
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models.anime import Anime
from app.models.user import User
from app.models.watch_progress import WatchProgress
from app.schemas.watch_progress import QueueOrderUpdate, WatchProgressResponse, WatchProgressUpdate

router = APIRouter(prefix="/users/me/progress", tags=["Watch progress"])


@router.get("", response_model=list[WatchProgressResponse])
def list_progress(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[WatchProgress]:
    return (
        db.query(WatchProgress)
        .options(joinedload(WatchProgress.anime))
        .filter(WatchProgress.user_id == user.id)
        .order_by(WatchProgress.queue_position.asc().nullslast(), WatchProgress.updated_at.desc())
        .all()
    )


@router.patch("/queue", response_model=list[WatchProgressResponse])
def update_queue_order(
    order: QueueOrderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[WatchProgress]:
    queue = (
        db.query(WatchProgress)
        .filter(
            WatchProgress.user_id == user.id,
            WatchProgress.status == "plan_to_watch",
        )
        .all()
    )
    by_anime_id = {item.anime_id: item for item in queue}
    if set(order.anime_ids) != set(by_anime_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Queue order must include each of your plan-to-watch titles exactly once.",
        )
    for position, anime_id in enumerate(order.anime_ids):
        by_anime_id[anime_id].queue_position = position
    db.commit()
    return (
        db.query(WatchProgress)
        .options(joinedload(WatchProgress.anime))
        .filter(WatchProgress.user_id == user.id)
        .order_by(WatchProgress.queue_position.asc().nullslast(), WatchProgress.updated_at.desc())
        .all()
    )


@router.get("/recap")
def yearly_recap(
    year: int = Query(default_factory=lambda: datetime.now().year, ge=2000, le=2100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    completed = (
        db.query(WatchProgress)
        .options(joinedload(WatchProgress.anime))
        .filter(
            WatchProgress.user_id == user.id,
            WatchProgress.completed_at.is_not(None),
        )
        .all()
    )
    year_completed: list[tuple[WatchProgress, datetime]] = []
    for item in completed:
        completed_at = item.completed_at
        if completed_at is not None and completed_at.year == year:
            year_completed.append((item, completed_at))
    genre_counts: dict[str, int] = {}
    studio_counts: dict[str, int] = {}
    monthly_completions = [0] * 12
    completion_days: set[date] = set()
    for item, _ in year_completed:
        anime_genres = cast(str | None, item.anime.genre)
        anime_studio = cast(str | None, item.anime.studio)
        completed_at = item.completed_at
        if completed_at is not None:
            monthly_completions[completed_at.month - 1] += 1
            completion_days.add(completed_at.date())
        for genre in (anime_genres or "").split(","):
            label = genre.strip()
            if label:
                genre_counts[label] = genre_counts.get(label, 0) + 1
        if anime_studio:
            studio_counts[anime_studio] = studio_counts.get(anime_studio, 0) + 1
    return {
        "year": year,
        "completed_count": len(year_completed),
        "episodes_watched": sum(item.episodes_watched for item, _ in year_completed),
        "completion_days": len(completion_days),
        "monthly_completions": monthly_completions,
        "top_genre": max(genre_counts, key=lambda genre: genre_counts[genre]) if genre_counts else None,
        "top_studio": max(studio_counts, key=lambda studio: studio_counts[studio]) if studio_counts else None,
        "titles": [
            {
                "anime_id": item.anime_id,
                "title": item.anime.title,
                "cover_image": item.anime.cover_image,
                "episodes_watched": item.episodes_watched,
                "completed_at": item.completed_at,
            }
            for item, _ in sorted(
                year_completed,
                key=lambda entry: entry[1],
                reverse=True,
            )
        ],
    }


@router.put("/{anime_id}", response_model=WatchProgressResponse)
def update_progress(
    anime_id: int,
    progress_data: WatchProgressUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WatchProgress:
    anime = db.query(Anime).filter(Anime.id == anime_id).first()
    if anime is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anime not found.")
    progress = db.query(WatchProgress).filter_by(user_id=user.id, anime_id=anime_id).first()
    previous_status = progress.status if progress else None
    episodes_watched = progress_data.episodes_watched
    if progress_data.status == "completed" and anime.episode is not None:
        episodes_watched = anime.episode
    if anime.episode is not None and episodes_watched > anime.episode:
        raise HTTPException(
            status_code=422,
            detail=f"Watched episodes cannot exceed this anime's {anime.episode} episodes.",
        )

    if progress is None:
        progress = WatchProgress(user_id=user.id, anime_id=anime_id)
        db.add(progress)
    progress.status = progress_data.status
    progress.episodes_watched = episodes_watched
    if progress_data.status == "completed" and previous_status != "completed":
        progress.completed_at = datetime.now(timezone.utc)
    if progress_data.status == "plan_to_watch" and previous_status != "plan_to_watch":
        progress.queue_position = (
            db.query(WatchProgress.queue_position)
            .filter(
                WatchProgress.user_id == user.id,
                WatchProgress.status == "plan_to_watch",
            )
            .order_by(WatchProgress.queue_position.desc().nullslast())
            .limit(1)
            .scalar()
            or -1
        ) + 1
    db.commit()
    db.refresh(progress)
    return db.query(WatchProgress).options(joinedload(WatchProgress.anime)).filter(
        WatchProgress.id == progress.id
    ).one()


@router.delete("/{anime_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_progress(
    anime_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    progress = db.query(WatchProgress).filter_by(user_id=user.id, anime_id=anime_id).first()
    if progress is not None:
        db.delete(progress)
        db.commit()
