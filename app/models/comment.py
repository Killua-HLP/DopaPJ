from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Text, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Comment(Base):
    __tablename__ = "comment"

    id = Column(Integer, primary_key=True)
    comment = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    anime_id = Column(Integer, ForeignKey("anime.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    is_spoiler = Column(Boolean, nullable=False, default=False, server_default="false")
    spoiler_episode = Column(Integer, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    user = relationship("User", back_populates="comments", foreign_keys=[user_id])
    anime = relationship("Anime", back_populates="comments")
