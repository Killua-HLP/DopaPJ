from pydantic import BaseModel, ConfigDict
from datetime import date

class AnimeCreate(BaseModel):
    title: str
    genre: str
    rating: float | None =  None
    episode: int | None | None
    studio: str | None = None
    description: str 
    released_date: date | None = None
    cover_image: str | None = None

class AnimeResponse(AnimeCreate):
    id : int
    model_config = ConfigDict(from_attributes=True)

class AnimeUpdate(BaseModel):
    title: str | None =  None
    genre: str | None =  None
    rating: float | None =  None
    episode: int | None = None
    studio: str | None = None
    description: str | None =  None
    released_date: date | None = None
    cover_image: str | None = None

    model_config = ConfigDict(from_attributes=True)
