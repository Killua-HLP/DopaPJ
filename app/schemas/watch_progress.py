from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.anime import AnimeResponse

WatchStatus = Literal["plan_to_watch", "watching", "completed", "on_hold", "dropped"]


class WatchProgressUpdate(BaseModel):
    status: WatchStatus
    episodes_watched: int = Field(default=0, ge=0)


class WatchProgressResponse(BaseModel):
    id: int
    anime_id: int
    status: WatchStatus
    episodes_watched: int
    updated_at: datetime
    completed_at: datetime | None = None
    queue_position: int | None = None
    anime: AnimeResponse
    model_config = ConfigDict(from_attributes=True)


class QueueOrderUpdate(BaseModel):
    anime_ids: list[int] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_unique_ids(self) -> "QueueOrderUpdate":
        if len(set(self.anime_ids)) != len(self.anime_ids):
            raise ValueError("Queue order cannot contain duplicate titles.")
        return self
