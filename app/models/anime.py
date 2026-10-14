from sqlalchemy import Column, Integer, String, Float,Date
from app.database import Base


class Anime(Base):
    __tablename__ = "anime"

    id = Column(Integer, primary_key=True)
    title = Column(String(100), unique=True, nullable=False)
    genre = Column(String(100), nullable=False)
    rating = Column(Float)
    episode = Column(Integer)
    description = Column(String, nullable=False)
    studio = Column(String(100))
    released_date = Column(Date)
    cover_image = Column(String(255))

