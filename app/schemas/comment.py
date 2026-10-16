from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CommentCreate(BaseModel):
    comment: str = Field(min_length=1, max_length=2000)
    is_spoiler: bool = False
    spoiler_episode: int | None = Field(default=None, ge=1)

    @field_validator("comment")
    @classmethod
    def validate_comment(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Comment cannot be blank.")
        return value

    @model_validator(mode="after")
    def validate_spoiler_episode(self) -> "CommentCreate":
        if self.is_spoiler and self.spoiler_episode is None:
            raise ValueError("Choose the episode this spoiler refers to.")
        if not self.is_spoiler and self.spoiler_episode is not None:
            raise ValueError("An episode threshold is only valid for spoiler comments.")
        return self


class CommentResponse(BaseModel):
    id: int
    comment: str
    user_id: int
    user_name: str
    anime_id: int
    is_spoiler: bool = False
    spoiler_episode: int | None = None
    is_revealed: bool = False
    created_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)
