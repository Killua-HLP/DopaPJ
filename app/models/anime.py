from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    TIMESTAMP,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Anime(Base):
    __tablename__ = "anime"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    genre: Mapped[str] = mapped_column(String(100), nullable=False)
    rating = Column(Float, nullable=True)
    episode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description = Column(Text, nullable=False)
    studio = Column(String(100), nullable=True)
    released_date = Column(Date, nullable=True)
    cover_image = Column(String(500), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    anilist_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True, index=True)
    locally_edited = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=True)

    owner = relationship("User", back_populates="anime")
    comments = relationship("Comment", back_populates="anime", cascade="all, delete-orphan")
    favorites = relationship("Favourite", back_populates="anime", cascade="all, delete-orphan")
    watch_progress = relationship("WatchProgress", back_populates="anime", cascade="all, delete-orphan")


class Genre(Base):
    __tablename__ = "anime_genre"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False, index=True)


class Favourite(Base):
    __tablename__ = "favourite"
    __table_args__ = (UniqueConstraint("user_id", "anime_id", name="uq_favourite_user_anime_pair"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    anime_id = Column(Integer, ForeignKey("anime.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="favorites")
    anime = relationship("Anime", back_populates="favorites")
