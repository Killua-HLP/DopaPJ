from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.anime_sources import anilist_id_from_source_url
from app.auth import get_current_user
from app.database import get_db
from app.models.anime import Anime
from app.models.user import User
from app.schemas.anime import AnimeCreate, AnimeResponse, AnimeUpdate

router = APIRouter(tags=["Anime"])


@router.post("/anime", response_model=AnimeResponse, status_code=status.HTTP_201_CREATED)
def create_anime(
    anime_in: AnimeCreate,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Anime:
    anilist_id = anilist_id_from_source_url(anime_in.source_url)
    if anilist_id is not None:
        existing_import = db.query(Anime).filter(Anime.anilist_id == anilist_id).first()
        if existing_import:
            response.status_code = status.HTTP_200_OK
            return existing_import

    if db.query(Anime.id).filter(Anime.title.ilike(anime_in.title)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An anime with that title already exists.")

    anime = Anime(**anime_in.model_dump(), user_id=user.id, anilist_id=anilist_id)
    db.add(anime)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if anilist_id is not None:
            existing_import = db.query(Anime).filter(Anime.anilist_id == anilist_id).first()
            if existing_import:
                response.status_code = status.HTTP_200_OK
                return existing_import
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An anime with that title already exists.") from exc
    db.refresh(anime)
    return anime


@router.get("/anime", response_model=list[AnimeResponse])
def get_anime(db: Session = Depends(get_db)) -> list[Anime]:
    return db.query(Anime).order_by(Anime.rating.desc().nullslast(), Anime.title.asc()).all()


@router.get("/anime/{anime_id}", response_model=AnimeResponse)
def get_anime_by_id(anime_id: int, db: Session = Depends(get_db)) -> Anime:
    anime = db.query(Anime).filter(Anime.id == anime_id).first()
    if not anime:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anime not found.")
    return anime


@router.patch("/anime/{anime_id}", response_model=AnimeResponse)
def update_anime(
    anime_id: int,
    anime_data: AnimeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Anime:
    anime = db.query(Anime).filter(Anime.id == anime_id).first()
    if not anime:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anime not found.")
    if anime.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the title's creator can edit it.")

    update_data = anime_data.model_dump(exclude_unset=True)
    if "title" in update_data and db.query(Anime.id).filter(
        Anime.title.ilike(update_data["title"]),
        Anime.id != anime_id,
    ).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An anime with that title already exists.")
    for field, value in update_data.items():
        setattr(anime, field, value)
    if "source_url" in update_data:
        anime.anilist_id = anilist_id_from_source_url(anime.source_url)
    anime.locally_edited = True
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An anime with that title already exists.") from exc
    db.refresh(anime)
    return anime


@router.delete("/anime/{anime_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_anime(
    anime_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    anime = db.query(Anime).filter(Anime.id == anime_id).first()
    if not anime:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anime not found.")
    if anime.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the title's creator can delete it.")
    db.delete(anime)
    db.commit()
