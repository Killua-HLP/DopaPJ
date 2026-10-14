from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers.anime import router as anime_router

app = FastAPI()

app.include_router(anime_router)

Base.metadata.create_all(engine)

app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def home():
    return FileResponse("frontend/anime.html")


@app.get("/anime-detail.html")
def anime_detail():
    return FileResponse("frontend/anime-detail.html")
