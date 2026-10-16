from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_optional_current_user
from app.database import get_db
from app.models.anime import Anime
from app.models.comment import Comment
from app.models.user import User
from app.models.watch_progress import WatchProgress
from app.schemas.comment import CommentCreate, CommentResponse

router = APIRouter(tags=["Comments"])


def serialize_comment(
    comment: Comment,
    episodes_watched: int = 0,
) -> CommentResponse:
    revealed = not comment.is_spoiler or (
        comment.spoiler_episode is not None and episodes_watched >= comment.spoiler_episode
    )
    return CommentResponse(
        id=comment.id,
        comment=comment.comment if revealed else "Spoiler hidden. Watch the marked episode to reveal this comment.",
        user_id=comment.user_id,
        user_name=comment.user.name,
        anime_id=comment.anime_id,
        created_at=comment.created_at,
        is_spoiler=comment.is_spoiler,
        spoiler_episode=comment.spoiler_episode,
        is_revealed=revealed,
    )


@router.get("/anime/{anime_id}/comments", response_model=list[CommentResponse])
def get_comments(
    anime_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
) -> list[CommentResponse]:
    if not db.query(Anime.id).filter(Anime.id == anime_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anime not found.")
    comments = (
        db.query(Comment)
        .filter(Comment.anime_id == anime_id)
        .order_by(Comment.created_at.desc(), Comment.id.desc())
        .all()
    )
    progress = None
    if user is not None:
        progress = db.query(WatchProgress).filter_by(user_id=user.id, anime_id=anime_id).first()
    episodes_watched = progress.episodes_watched if progress else 0
    return [serialize_comment(comment, episodes_watched) for comment in comments]


@router.post(
    "/anime/{anime_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    anime_id: int,
    comment_data: CommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CommentResponse:
    if not db.query(Anime.id).filter(Anime.id == anime_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anime not found.")
    comment = Comment(
        comment=comment_data.comment,
        anime_id=anime_id,
        user_id=user.id,
        is_spoiler=comment_data.is_spoiler,
        spoiler_episode=comment_data.spoiler_episode,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return serialize_comment(comment)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")
    if comment.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only remove your own comments.")
    db.delete(comment)
    db.commit()
