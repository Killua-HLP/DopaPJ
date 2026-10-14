import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from fastapi import HTTPException


load_dotenv()

DB_URL = os.getenv("DB_URL")

if not DB_URL:
    raise HTTPException(
        status_code=404,
        detail="Database is not in .env"
    )

engine = create_engine(DB_URL)

Sessionlocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass