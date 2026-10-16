import asyncio
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import re
import secrets
from time import perf_counter
from collections.abc import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine
from app.models import admin_audit, anime, anime_embedding, anilist_cache, comment, user, watch_progress
from app.observability import configure_logging
from app.security import (
    CONTENT_SECURITY_POLICY,
    SECURITY_HEADERS,
    RequestBodySizeLimitMiddleware,
    rate_limiter,
)
from app.upload_storage import UPLOAD_DIR
from app.routers.anime import router as anime_router
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.comments import router as comments_router
from app.routers.catalog import router as catalog_router
from app.routers.progress import router as progress_router
from app.routers.users import router as users_router
from app.routers.catalog import refresh_popular_catalog_cache

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
logger = logging.getLogger(__name__)
POPULAR_REFRESH_INTERVAL_SECONDS = 15 * 60


async def _refresh_popular_catalog_periodically() -> None:
    while True:
        await asyncio.sleep(POPULAR_REFRESH_INTERVAL_SECONDS)
        try:
            await refresh_popular_catalog_cache()
            logger.info("Popular AniList catalog cache refreshed")
        except Exception:
            logger.exception("Scheduled popular AniList catalog refresh failed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    refresh_task = asyncio.create_task(_refresh_popular_catalog_periodically())
    app.state.anilist_refresh_task = refresh_task
    try:
        yield
    finally:
        refresh_task.cancel()
        try:
            await refresh_task
        except asyncio.CancelledError:
            pass
        del app.state.anilist_refresh_task


configure_logging()
app = FastAPI(
    title="Anime Hub",
    description="Discover anime, build a watchlist, and share what you love.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(anime_router)
app.include_router(users_router)
app.include_router(comments_router)
app.include_router(catalog_router)
app.include_router(progress_router)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

_MAX_REQUEST_BYTES = 1_048_576
app.add_middleware(
    RequestBodySizeLimitMiddleware,
    max_body_bytes=_MAX_REQUEST_BYTES,
)


def _add_security_headers(response):
    for name, value in SECURITY_HEADERS.items():
        if name.lower() == "content-security-policy" and name in response.headers:
            continue
        response.headers[name] = value
    return response


def _secure_api_document(response: HTMLResponse) -> HTMLResponse:
    nonce = secrets.token_urlsafe(18)
    inline_script = re.compile(r"<script\b[^>]*>", re.IGNORECASE)

    def add_nonce(match: re.Match[str]) -> str:
        tag = match.group(0)
        if re.search(r"\bsrc\s*=", tag, re.IGNORECASE):
            return tag
        return f'{tag[:-1]} nonce="{nonce}">'

    html = inline_script.sub(add_nonce, response.body.decode("utf-8"))

    policy = CONTENT_SECURITY_POLICY.replace(
        "script-src 'self';",
        f"script-src 'self' https://cdn.jsdelivr.net https://cdn.redoc.ly 'nonce-{nonce}';",
    ).replace(
        "https://fonts.googleapis.com;",
        "https://fonts.googleapis.com https://cdn.jsdelivr.net;",
    )
    headers = {
        **SECURITY_HEADERS,
        "Content-Security-Policy": policy,
    }
    return HTMLResponse(html, status_code=response.status_code, headers=headers)


@app.middleware("http")
async def apply_security_controls(request: Request, call_next):
    started_at = perf_counter()
    if request.url.path != "/health" and not request.url.path.startswith("/static/"):
        client_host = request.client.host if request.client else "unknown"
        if request.url.path in {"/auth/login", "/auth/token"}:
            bucket, limit = "auth-login", 15
        elif request.url.path == "/auth/register":
            bucket, limit = "auth-register", 5
        elif request.url.path.startswith("/catalog/"):
            bucket, limit = "catalog", 30
        else:
            bucket, limit = "api", 120
        allowed, retry_after = rate_limiter.check(
            f"ip:{client_host}:{bucket}",
            limit,
            60,
        )
        if not allowed:
            return _add_security_headers(
                JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please try again later."},
                    headers={"Retry-After": str(retry_after)},
                )
            )

    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "http_request_failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            },
        )
        raise
    logger.info(
        "http_request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
        },
    )
    return _add_security_headers(response)


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "anime.html")


@app.get("/anime-detail.html", include_in_schema=False)
def anime_detail() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "anime-detail.html")


@app.get("/login.html", include_in_schema=False)
def login_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "login.html")


@app.get("/profile.html", include_in_schema=False)
def profile_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "profile.html")


@app.get("/admin.html", include_in_schema=False)
def admin_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "admin.html")


@app.get("/docs", include_in_schema=False)
def swagger_docs() -> HTMLResponse:
    response = get_swagger_ui_html(
        openapi_url=app.openapi_url or "/openapi.json",
        title=f"{app.title} - Swagger UI",
        oauth2_redirect_url="/docs/oauth2-redirect",
    )
    return _secure_api_document(response)


@app.get("/docs/oauth2-redirect", include_in_schema=False)
def swagger_oauth2_redirect() -> HTMLResponse:
    return _secure_api_document(get_swagger_ui_oauth2_redirect_html())


@app.get("/redoc", include_in_schema=False)
def redoc_docs() -> HTMLResponse:
    response = get_redoc_html(
        openapi_url=app.openapi_url or "/openapi.json",
        title=f"{app.title} - ReDoc",
    )
    return _secure_api_document(response)


@app.get("/health", tags=["Health"])
def health() -> dict[str, str | int]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            cache_entries = connection.execute(
                text("SELECT COUNT(*) FROM anilist_cache")
            ).scalar_one()
            embedding_entries = connection.execute(
                text("SELECT COUNT(*) FROM anime_embedding")
            ).scalar_one()
    except SQLAlchemyError as exc:
        logger.exception("Database readiness check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from exc
    return {
        "status": "ok",
        "database": "ok",
        "anilist_cache_entries": cache_entries,
        "anime_embeddings": embedding_entries,
    }
