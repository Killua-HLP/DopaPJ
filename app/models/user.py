from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import TIMESTAMP

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(254), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    bio = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    cover_image = Column(String(500), nullable=True)
    is_admin = Column(Boolean, nullable=False, default=False, server_default="false")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    suspended_at = Column(DateTime(timezone=True), nullable=True)
    suspension_reason = Column(String(500), nullable=True)

    anime = relationship("Anime", back_populates="owner")
    comments = relationship(
        "Comment",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Comment.user_id",
    )
    favorites = relationship("Favourite", back_populates="user", cascade="all, delete-orphan")
    watch_progress = relationship("WatchProgress", back_populates="user", cascade="all, delete-orphan")
