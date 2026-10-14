from fastapi import APIRouter, Depends
from fastapi import HTTPException, status

from sqlalchemy.orm import Session
from app.database import Sessionlocal
from app.models.anime import Anime
from app.schemas.anime import AnimeCreate, AnimeResponse, AnimeUpdate

router = APIRouter(prefix="", tags=["Anime Session"])

def get_db():
    db = Sessionlocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/anime", status_code=status.HTTP_201_CREATED)
def create_anime(anime_in: AnimeCreate, db: Session = Depends(get_db)):
    existing_anime = db.query(Anime).filter(Anime.title == anime_in.title).first()
    if existing_anime:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Anime with title '{anime_in.title}' already exists."
        )

    new_anime = Anime(**anime_in.model_dump())
    db.add(new_anime)
    db.commit()
    db.refresh(new_anime)

    return new_anime

@router.get("/anime", response_model=list[AnimeResponse])
def get_anime(db: Session = Depends(get_db)):
    return db.query(Anime).all()

@router.get("/anime/{anime_id}")
def get_anime_by_id(anime_id: int, db: Session = Depends(get_db)):
    anime = db.query(Anime).filter(Anime.id == anime_id).first()
    if not anime:
        raise HTTPException(status_code=404,detail="Not Found!")
    return anime

@router.patch("/anime/{anime_id}", response_model=AnimeResponse)
def update_anime(
    anime_id: int, 
    anime_data: AnimeUpdate ,
    db: Session = Depends(get_db)):

    anime = db.query(Anime).filter(Anime.id == anime_id).first()

    if not anime:
        raise HTTPException(status_code=404, detail="Not Found")
    
    update_data = anime_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(anime, field, value)

    db.commit()
    db.refresh(anime)

    return anime

@router.delete("/anime/{anime_id}")
def delete_anime(anime_id: int, db: Session = Depends(get_db)):
    anime = db.query(Anime).filter(Anime.id == anime_id).first()
    if not anime:
        raise HTTPException(
            status_code=404,
            detail="Not Found"
        )
    db.delete(anime)
    db.commit()
    return {f"Successuflluy Deleted {anime_id} "}