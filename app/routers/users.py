from io import BytesIO
from http import HTTPStatus
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.anime import Anime, Favourite
from app.models.user import User
from app.schemas.anime import AnimeResponse
from app.schemas.user import UserResponse, UserUpdate
from app.upload_storage import UPLOAD_DIR

router = APIRouter(prefix="/users", tags=["Users"])
logger = logging.getLogger(__name__)
MAX_AVATAR_BYTES = 900 * 1024
MAX_AVATAR_PIXELS = 12_000_000
MAX_AVATAR_DIMENSION = 4096
ALLOWED_AVATAR_FORMATS = {"JPEG", "PNG", "WEBP"}


@router.get("/me", response_model=UserResponse)
def get_my_profile(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/me", response_model=UserResponse)
def update_my_profile(
    profile: UserUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    changes = profile.model_dump(exclude_unset=True)
    if "name" in changes and db.query(User.id).filter(
        User.name.ilike(changes["name"]),
        User.id != user.id,
    ).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That display name is already in use.")
    for field, value in changes.items():
        setattr(user, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That display name is already in use.") from exc
    db.refresh(user)
    return user


@router.post("/me/avatar", response_model=UserResponse)
async def upload_my_avatar(
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Choose a JPEG, PNG, or WebP image.",
        )

    image_bytes = await image.read(MAX_AVATAR_BYTES + 1)
    await image.close()
    if len(image_bytes) > MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            detail="Profile pictures must be 900 KiB or smaller.",
        )

    try:
        with Image.open(BytesIO(image_bytes)) as source:
            if source.format not in ALLOWED_AVATAR_FORMATS:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Choose a JPEG, PNG, or WebP image.",
                )
            if (
                source.width > MAX_AVATAR_DIMENSION
                or source.height > MAX_AVATAR_DIMENSION
                or source.width * source.height > MAX_AVATAR_PIXELS
            ):
                raise HTTPException(
                    status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    detail="Profile picture dimensions are too large.",
                )
            source.load()
            normalized = ImageOps.exif_transpose(source)
            if normalized.mode not in {"RGB", "RGBA"}:
                normalized = normalized.convert("RGBA" if "A" in normalized.getbands() else "RGB")
            normalized.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            output = BytesIO()
            normalized.save(output, format="WEBP", quality=85, method=6)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is not a valid supported image.",
        ) from exc

    filename = f"{uuid4().hex}.webp"
    user_upload_dir = UPLOAD_DIR / str(user.id)
    user_upload_dir.mkdir(parents=True, exist_ok=True)
    destination = user_upload_dir / filename
    try:
        destination.write_bytes(output.getvalue())
    except OSError:
        destination.unlink(missing_ok=True)
        raise

    previous_image = user.cover_image
    user.cover_image = f"/uploads/{user.id}/{filename}"
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise

    upload_prefix = f"/uploads/{user.id}/"
    if previous_image and previous_image.startswith(upload_prefix):
        previous_filename = previous_image.removeprefix(upload_prefix)
        if previous_filename == Path(previous_filename).name and previous_filename.endswith(".webp"):
            try:
                (destination.parent / previous_filename).unlink(missing_ok=True)
            except OSError:
                logger.exception("Could not remove a replaced profile picture")
    db.refresh(user)
    return user


@router.get("/me/favorites", response_model=list[AnimeResponse])
def get_favorites(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Anime]:
    return (
        db.query(Anime)
        .join(Favourite, Favourite.anime_id == Anime.id)
        .filter(Favourite.user_id == user.id)
        .order_by(Favourite.created_at.desc())
        .all()
    )


@router.post("/me/favorites/{anime_id}", status_code=status.HTTP_204_NO_CONTENT)
def add_favorite(
    anime_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    anime = db.query(Anime).filter(Anime.id == anime_id).first()
    if not anime:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anime not found.")
    existing = db.query(Favourite).filter_by(user_id=user.id, anime_id=anime_id).first()
    if existing:
        return
    db.add(Favourite(user_id=user.id, anime_id=anime_id))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Could not save this favorite.") from exc


@router.delete("/me/favorites/{anime_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    anime_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    favorite = db.query(Favourite).filter_by(user_id=user.id, anime_id=anime_id).first()
    if favorite:
        db.delete(favorite)
        db.commit()
