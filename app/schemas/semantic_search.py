from pydantic import BaseModel, Field


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=240)
    limit: int = Field(default=12, ge=1, le=30)


class RecommendationExplanationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    synopsis: str = Field(min_length=1, max_length=5000)
    genres: list[str] = Field(default_factory=list, max_length=12)
