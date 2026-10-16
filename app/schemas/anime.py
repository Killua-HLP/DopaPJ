from datetime import date
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


def validate_source_url(value: str | None) -> str | None:
    if value is None:
        return value
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Source links must use a valid HTTPS URL.")
    return value


class AnimeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    genre: str = Field(min_length=1, max_length=100)
    rating: float | None = Field(default=None, ge=0, le=10)
    episode: int | None = Field(default=None, ge=1)
    studio: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=1, max_length=10000)
    released_date: date | None = None
    cover_image: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=500)

    @field_validator("title", "genre", "description")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    _validate_source_url = field_validator("source_url")(validate_source_url)


class AnimeResponse(AnimeCreate):
    id: int
    user_id: int | None = None
    anilist_id: int | None = None
    locally_edited: bool = False
    model_config = ConfigDict(from_attributes=True)


class AnimeCatalogResult(BaseModel):
    title: str = Field(max_length=100)
    genre: str = Field(max_length=100)
    format: str | None = None
    rating: float | None = Field(default=None, ge=0, le=10)
    episode: int | None = Field(default=None, ge=1)
    duration: int | None = Field(default=None, ge=1)
    studio: str | None = Field(default=None, max_length=100)
    description: str = Field(max_length=10000)
    released_date: date | None = None
    cover_image: str | None = Field(default=None, max_length=500)
    source_url: str = Field(max_length=500)


class AnimeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    genre: str | None = Field(default=None, min_length=1, max_length=100)
    rating: float | None = Field(default=None, ge=0, le=10)
    episode: int | None = Field(default=None, ge=1)
    studio: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, min_length=1, max_length=10000)
    released_date: date | None = None
    cover_image: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=500)

    @field_validator("title", "genre", "description")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    _validate_source_url = field_validator("source_url")(validate_source_url)
