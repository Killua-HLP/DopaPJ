import asyncio
from io import BytesIO
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from PIL import Image

from app.main import app
from app.routers import catalog as catalog_router
from app.routers import users as users_router
from app.auth import hash_password, verify_password
from app.database import SessionLocal
from app.models.anime import Anime
from app.models.anilist_cache import AniListCache
from app.models.anime_embedding import AnimeEmbedding
from app.models.admin_audit import AdminAudit
from app.models.comment import Comment
from app.models.user import User
from app.observability import JsonLogFormatter
from app.security import RequestBodySizeLimitMiddleware
from app.services.semantic_search import cosine_similarity, embed_text

ANIME = {
    "title": "A Test Anime",
    "genre": "Drama",
    "rating": 8.5,
    "episode": 12,
    "description": "A story created by an API test.",
}


def make_admin(email: str) -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        user.is_admin = True
        db.commit()


def register_user(
    client: TestClient,
    name: str,
    email: str,
) -> tuple[dict, dict[str, str]]:
    response = client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": "correct-horse-battery"},
    )
    assert response.status_code == 201
    result = response.json()
    return result, {"Authorization": f"Bearer {result['access_token']}"}


def test_health_home_and_cover_asset(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["database"] == "ok"
    assert isinstance(health.json()["anilist_cache_entries"], int)
    assert isinstance(health.json()["anime_embeddings"], int)
    policy = health.headers["content-security-policy"]
    assert "default-src 'none'" in policy
    assert "script-src 'self'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "'unsafe-inline'" not in policy.split("script-src", 1)[1].split(";", 1)[0]
    assert client.get("/").status_code == 200

    cover = client.get("/static/miyuki.jpg")
    assert cover.status_code == 200
    assert cover.headers["content-type"].startswith("image/jpeg")


def test_api_documentation_works_with_nonce_based_csp(client: TestClient) -> None:
    for path in ("/docs", "/docs/oauth2-redirect"):
        response = client.get(path)
        assert response.status_code == 200
        policy = response.headers["content-security-policy"]
        assert "nonce-" in policy
        assert b"<script nonce=" in response.content
        assert "unsafe-inline" not in policy.split("script-src", 1)[1].split(";", 1)[0]
    docs_policy = client.get("/docs").headers["content-security-policy"]
    assert "https://cdn.jsdelivr.net" in docs_policy
    redoc = client.get("/redoc")
    assert redoc.status_code == 200
    assert b"redoc.standalone.js" in redoc.content
    assert "https://cdn.jsdelivr.net" in redoc.headers["content-security-policy"]


def test_structured_log_formatter_emits_json_fields() -> None:
    import json
    import logging

    record = logging.LogRecord("app.test", logging.INFO, "", 0, "http_request", (), None)
    record.method = "GET"
    record.path = "/health"
    record.status_code = 200
    record.duration_ms = 1.5
    payload = json.loads(JsonLogFormatter().format(record))
    assert payload["message"] == "http_request"
    assert payload["method"] == "GET"
    assert payload["status_code"] == 200


def test_register_login_and_duplicate_account(client: TestClient) -> None:
    result, _ = register_user(client, "Test User", "test@example.com")
    assert result["user"]["email"] == "test@example.com"
    assert "hashed_password" not in result["user"]

    login = client.post(
        "/auth/login",
        json={"email": "TEST@example.com", "password": "correct-horse-battery"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]

    duplicate = client.post(
        "/auth/register",
        json={"name": "Another User", "email": "test@example.com", "password": "password123"},
    )
    assert duplicate.status_code == 409
    duplicate_name = client.post(
        "/auth/register",
        json={"name": "test USER", "email": "another@example.com", "password": "password123"},
    )
    assert duplicate_name.status_code == 409

    invalid_login = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "wrong-password"},
    )
    assert invalid_login.status_code == 401


def test_change_password_requires_current_password_and_replaces_hash(client: TestClient) -> None:
    _, headers = register_user(client, "Password User", "password-change@example.com")

    unauthenticated = client.post(
        "/auth/change-password",
        json={"current_password": "correct-horse-battery", "new_password": "new-correct-password"},
    )
    assert unauthenticated.status_code == 401

    unauthorized = client.post(
        "/auth/change-password",
        json={"current_password": "incorrect-password", "new_password": "new-correct-password"},
        headers=headers,
    )
    assert unauthorized.status_code == 400

    changed = client.post(
        "/auth/change-password",
        json={"current_password": "correct-horse-battery", "new_password": "new-correct-password"},
        headers=headers,
    )
    assert changed.status_code == 204

    old_password_login = client.post(
        "/auth/login",
        json={"email": "password-change@example.com", "password": "correct-horse-battery"},
    )
    assert old_password_login.status_code == 401
    new_password_login = client.post(
        "/auth/login",
        json={"email": "password-change@example.com", "password": "new-correct-password"},
    )
    assert new_password_login.status_code == 200


def test_swagger_openapi_uses_oauth2_password_auth_for_protected_routes(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    delete_operation = schema["paths"]["/anime/{anime_id}"]["delete"]
    assert delete_operation["security"] == [{"OAuth2PasswordBearer": []}]
    assert schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]["flows"]["password"] == {
        "tokenUrl": "/auth/token",
        "scopes": {},
    }


def test_oauth2_password_token_endpoint(client: TestClient) -> None:
    register_user(client, "OAuth User", "oauth@example.com")
    token_response = client.post(
        "/auth/token",
        data={"username": "OAUTH USER", "password": "correct-horse-battery"},
    )
    assert token_response.status_code == 200
    token = token_response.json()
    assert token["token_type"] == "bearer"
    account = client.get("/auth/me", headers={"Authorization": f"Bearer {token['access_token']}"})
    assert account.status_code == 200
    assert account.json()["email"] == "oauth@example.com"

    email_token = client.post(
        "/auth/token",
        data={"username": "oauth@example.com", "password": "correct-horse-battery"},
    )
    assert email_token.status_code == 200


def test_admin_routes_require_server_side_role(client: TestClient) -> None:
    assert client.get("/admin/overview").status_code == 401
    _, normal_headers = register_user(client, "Regular User", "regular@example.com")
    assert client.get("/admin/overview", headers=normal_headers).status_code == 403
    denied = client.post("/admin/anime", headers=normal_headers, json=ANIME)
    assert denied.status_code == 403

    _, admin_headers = register_user(client, "Console Admin", "admin@example.com")
    make_admin("admin@example.com")
    account = client.get("/auth/me", headers=admin_headers)
    assert account.status_code == 200
    assert account.json()["is_admin"] is True
    assert client.get("/admin/overview", headers=admin_headers).status_code == 200


def test_admin_moderation_and_audit_trail(client: TestClient) -> None:
    user, user_headers = register_user(client, "Community User", "community@example.com")
    _, admin_headers = register_user(client, "Console Admin", "admin@example.com")
    make_admin("admin@example.com")
    admin_id = client.get("/auth/me", headers=admin_headers).json()["id"]
    with SessionLocal() as db:
        db.add_all(
            [
                AniListCache(
                    cache_key="admin-cache-fresh",
                    payload={},
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                ),
                AniListCache(
                    cache_key="admin-cache-stale",
                    payload={},
                    expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
                ),
            ]
        )
        db.commit()
    created_anime = client.post("/anime", headers=user_headers, json=ANIME)
    assert created_anime.status_code == 201
    anime_id = created_anime.json()["id"]
    created_comment = client.post(
        f"/anime/{anime_id}/comments",
        headers=user_headers,
        json={"comment": "A thoughtful comment"},
    )
    assert created_comment.status_code == 201
    comment_id = created_comment.json()["id"]

    overview = client.get("/admin/overview", headers=admin_headers)
    assert overview.status_code == 200
    assert overview.json()["totals"]["users"] == 2
    assert overview.json()["totals"]["anime"] == 1
    assert overview.json()["totals"]["pending_comments"] == 1
    assert overview.json()["registrations_last_7_days"] == 2
    assert overview.json()["anilist_cache"] == {"entries": 2, "fresh": 1, "stale": 1}
    assert any(event["kind"] == "comment" for event in overview.json()["recent_activity"])
    queue = client.get("/admin/comments", headers=admin_headers)
    assert queue.status_code == 200
    assert queue.json()["items"][0]["id"] == comment_id

    reviewed = client.post(f"/admin/comments/{comment_id}/review", headers=admin_headers)
    assert reviewed.status_code == 204
    assert client.get("/admin/comments", headers=admin_headers).json()["total"] == 0
    with SessionLocal() as db:
        comment = db.query(Comment).filter(Comment.id == comment_id).one()
        assert comment.reviewed_by == admin_id

    suspended = client.patch(
        f"/admin/users/{user['user']['id']}/status",
        params={"is_active": "false", "reason": "Spam"},
        headers=admin_headers,
    )
    assert suspended.status_code == 200
    assert suspended.json()["is_active"] is False
    assert client.get("/auth/me", headers=user_headers).status_code == 403
    assert client.post(
        "/auth/login",
        json={"email": "community@example.com", "password": "correct-horse-battery"},
    ).status_code == 401

    audit = client.get("/admin/audit", headers=admin_headers)
    assert audit.status_code == 200
    assert {entry["action"] for entry in audit.json()} >= {"comment_approved", "user_suspended"}
    assert all(entry["actor_user_id"] == admin_id for entry in audit.json())
    with SessionLocal() as db:
        assert db.query(AdminAudit).count() == 2
    self_suspend = client.patch(
        f"/admin/users/{admin_id}/status",
        params={"is_active": "false"},
        headers=admin_headers,
    )
    assert self_suspend.status_code == 400

    reactivated = client.patch(
        f"/admin/users/{user['user']['id']}/status",
        params={"is_active": "true"},
        headers=admin_headers,
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["is_active"] is True
    assert client.get("/auth/me", headers=user_headers).status_code == 200


def test_admin_anime_crud_marks_local_edits_and_rejects_duplicate_imports(client: TestClient) -> None:
    _, admin_headers = register_user(client, "Console Admin", "admin@example.com")
    make_admin("admin@example.com")
    imported = {**ANIME, "title": "Imported Series", "source_url": "https://anilist.co/anime/12345"}
    created = client.post("/admin/anime", headers=admin_headers, json=imported)
    assert created.status_code == 201
    listed = client.get("/admin/anime", headers=admin_headers)
    title = next(item for item in listed.json()["items"] if item["title"] == "Imported Series")
    assert title["source_type"] == "AniList"
    assert title["anilist_id"] == 12345
    assert title["locally_edited"] is False

    duplicate = client.post(
        "/admin/anime",
        headers=admin_headers,
        json={**imported, "title": "A translated title"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["existing_id"] == created.json()["id"]

    updated = client.patch(
        f"/admin/anime/{created.json()['id']}",
        headers=admin_headers,
        json={"description": "Corrected synopsis", "cover_image": "https://example.com/cover.jpg"},
    )
    assert updated.status_code == 200
    updated_title = client.get("/anime/" + str(created.json()["id"])).json()
    assert updated_title["description"] == "Corrected synopsis"
    assert updated_title["locally_edited"] is True

    deleted = client.delete(f"/admin/anime/{created.json()['id']}", headers=admin_headers)
    assert deleted.status_code == 204
    assert client.get("/anime/" + str(created.json()["id"])).status_code == 404

    local_created = client.post(
        "/admin/anime",
        headers=admin_headers,
        json={**ANIME, "title": "Created Locally"},
    )
    assert local_created.status_code == 201
    local_entry = next(
        item for item in client.get("/admin/anime", headers=admin_headers).json()["items"]
        if item["title"] == "Created Locally"
    )
    assert local_entry["source_type"] == "Local"
    assert local_entry["locally_edited"] is False


def test_anilist_import_is_idempotent_for_existing_catalog_id(client: TestClient) -> None:
    _, headers = register_user(client, "Catalog User", "catalog-user@example.com")
    imported = {**ANIME, "title": "Imported One", "source_url": "https://anilist.co/anime/98765"}
    first = client.post("/anime", headers=headers, json=imported)
    assert first.status_code == 201
    duplicate = client.post(
        "/anime",
        headers=headers,
        json={**imported, "title": "Alternate English Title"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == first.json()["id"]
    with SessionLocal() as db:
        assert db.query(Anime).filter(Anime.anilist_id == 98765).count() == 1


def test_local_cli_promotes_only_existing_accounts() -> None:
    from app.admin import promote_user

    assert promote_user("missing@example.com") is False
    with SessionLocal() as db:
        db.add(
            User(
                name="Promoted User",
                email="promoted@example.com",
                hashed_password=hash_password("correct-horse-battery"),
            )
        )
        db.commit()
    assert promote_user(" PROMOTED@example.com ") is True
    with SessionLocal() as db:
        promoted = db.query(User).filter(User.email == "promoted@example.com").one()
        assert promoted.is_admin is True


def test_security_controls_rate_limit_and_headers(client: TestClient) -> None:
    for _ in range(5):
        assert client.post(
            "/auth/login",
            json={"email": "missing@example.com", "password": "incorrect-password"},
        ).status_code == 401

    limited = client.post(
        "/auth/login",
        json={"email": "missing@example.com", "password": "incorrect-password"},
    )
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) > 0
    assert limited.headers["x-content-type-options"] == "nosniff"
    assert limited.headers["x-frame-options"] == "DENY"

    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"

    for anime_id in range(-30, 0):
        catalog_response = client.get(f"/catalog/anime/{anime_id}/details")
        assert catalog_response.status_code == 422
    shared_catalog_limit = client.get("/catalog/search?q=xx")
    assert shared_catalog_limit.status_code == 429


def test_passwords_are_salted_and_hashed() -> None:
    password = "correct-horse-battery"
    encoded = hash_password(password)
    algorithm, iterations, salt, digest = encoded.split("$")
    assert algorithm == "pbkdf2_sha256"
    assert int(iterations) >= 310_000
    assert salt and digest
    assert encoded != password
    assert verify_password(password, encoded)
    assert not verify_password("wrong-password", encoded)
    assert not verify_password(password, "malformed-hash")


def test_sql_like_title_is_stored_as_data(client: TestClient) -> None:
    _, headers = register_user(client, "Injection Test", "injection@example.com")
    payload = {**ANIME, "title": "'; DROP TABLE anime; --"}

    created = client.post("/anime", json=payload, headers=headers)
    assert created.status_code == 201
    assert created.json()["title"] == payload["title"]
    assert client.get("/anime").json()[0]["title"] == payload["title"]


def test_request_body_size_limit(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        content=b" " * (1_048_577),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'none'" in response.headers["content-security-policy"]


def test_request_body_stream_limit_without_content_length() -> None:
    async def run_middleware() -> tuple[list[dict], bool]:
        messages = iter(
            [
                {"type": "http.request", "body": b"123456", "more_body": True},
                {"type": "http.request", "body": b"78901", "more_body": False},
            ]
        )
        sent: list[dict] = []
        downstream_called = False

        async def receive() -> dict:
            return next(messages)

        async def send(message: dict) -> None:
            sent.append(message)

        async def downstream(scope: dict, receive, send) -> None:
            nonlocal downstream_called
            downstream_called = True

        middleware = RequestBodySizeLimitMiddleware(downstream, max_body_bytes=10)
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/auth/register",
            "raw_path": b"/auth/register",
            "query_string": b"",
            "root_path": "",
            "headers": [(b"transfer-encoding", b"chunked")],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
        await middleware(scope, receive, send)
        return sent, downstream_called

    sent, downstream_called = asyncio.run(run_middleware())
    response_start = next(message for message in sent if message["type"] == "http.response.start")
    response_headers = dict(response_start["headers"])
    assert response_start["status"] == 413
    assert b"content-security-policy" in response_headers
    assert not downstream_called


def test_anime_crud_enforces_creator_permissions(client: TestClient) -> None:
    _, owner_headers = register_user(client, "Anime Owner", "owner@example.com")
    _, other_headers = register_user(client, "Other User", "other@example.com")

    assert client.post("/anime", json=ANIME).status_code == 401
    assert client.post(
        "/anime",
        json={**ANIME, "source_url": "javascript:alert(1)"},
        headers=owner_headers,
    ).status_code == 422

    created = client.post("/anime", json=ANIME, headers=owner_headers)
    assert created.status_code == 201
    anime_id = created.json()["id"]
    assert created.json()["user_id"] is not None
    assert client.get(f"/anime/{anime_id}").json()["title"] == ANIME["title"]

    forbidden_update = client.patch(
        f"/anime/{anime_id}",
        json={"title": "Changed by another user"},
        headers=other_headers,
    )
    assert forbidden_update.status_code == 403

    updated = client.patch(
        f"/anime/{anime_id}",
        json={"title": "Updated Test Anime"},
        headers=owner_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated Test Anime"

    deleted = client.delete(f"/anime/{anime_id}", headers=owner_headers)
    assert deleted.status_code == 204
    assert client.get(f"/anime/{anime_id}").status_code == 404


def test_favorites_and_comments_require_authentication(client: TestClient) -> None:
    _, headers = register_user(client, "Community User", "community@example.com")
    created = client.post("/anime", json=ANIME, headers=headers)
    anime_id = created.json()["id"]

    assert client.post(f"/users/me/favorites/{anime_id}").status_code == 401
    assert client.post(f"/anime/{anime_id}/comments", json={"comment": "Nice story"}).status_code == 401

    favorite = client.post(f"/users/me/favorites/{anime_id}", headers=headers)
    assert favorite.status_code == 204
    assert client.get("/users/me/favorites", headers=headers).json()[0]["id"] == anime_id

    comment = client.post(
        f"/anime/{anime_id}/comments",
        json={"comment": "Nice story"},
        headers=headers,
    )
    assert comment.status_code == 201
    comments = client.get(f"/anime/{anime_id}/comments")
    assert comments.status_code == 200
    assert comments.json()[0]["comment"] == "Nice story"


def test_profile_picture_upload_is_authenticated_validated_and_replaces_previous(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _, headers = register_user(client, "Picture User", "picture@example.com")
    monkeypatch.setattr(users_router, "UPLOAD_DIR", tmp_path)
    uploads_static = next(route.app for route in app.routes if getattr(route, "name", None) == "uploads")
    monkeypatch.setattr(uploads_static, "directory", str(tmp_path))
    monkeypatch.setattr(uploads_static, "all_directories", [str(tmp_path)])

    image_buffer = BytesIO()
    Image.new("RGB", (1600, 1200), color=(75, 110, 170)).save(image_buffer, format="PNG")
    image_bytes = image_buffer.getvalue()
    uploaded = client.post(
        "/users/me/avatar",
        files={"image": ("avatar.png", image_bytes, "image/png")},
    )
    assert uploaded.status_code == 401

    invalid = client.post(
        "/users/me/avatar",
        files={"image": ("avatar.png", b"not an image", "image/png")},
        headers=headers,
    )
    assert invalid.status_code == 400
    unsupported = client.post(
        "/users/me/avatar",
        files={"image": ("avatar.svg", b"<svg/>", "image/svg+xml")},
        headers=headers,
    )
    assert unsupported.status_code == 415
    oversized = client.post(
        "/users/me/avatar",
        files={"image": ("avatar.png", b"x" * (900 * 1024 + 1), "image/png")},
        headers=headers,
    )
    assert oversized.status_code == 413

    first = client.post(
        "/users/me/avatar",
        files={"image": ("avatar.png", image_bytes, "image/png")},
        headers=headers,
    )
    assert first.status_code == 200
    first_url = first.json()["cover_image"]
    first_path = tmp_path / str(first.json()["id"]) / first_url.rsplit("/", 1)[-1]
    assert first_path.is_file()
    served_image = client.get(first_url)
    assert served_image.status_code == 200
    assert served_image.headers["content-type"] == "image/webp"
    with Image.open(first_path) as saved_image:
        assert saved_image.format == "WEBP"
        assert saved_image.size == (1024, 768)

    second = client.post(
        "/users/me/avatar",
        files={"image": ("avatar.png", image_bytes, "image/png")},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["cover_image"] != first_url
    assert not first_path.exists()


def test_spoiler_comments_are_revealed_after_episode_progress(client: TestClient) -> None:
    _, headers = register_user(client, "Spoiler Fan", "spoiler@example.com")
    anime_id = client.post("/anime", json={**ANIME, "episode": 12}, headers=headers).json()["id"]
    created = client.post(
        f"/anime/{anime_id}/comments",
        json={
            "comment": "The reveal in this episode changes everything.",
            "is_spoiler": True,
            "spoiler_episode": 5,
        },
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["is_spoiler"] is True

    hidden = client.get(f"/anime/{anime_id}/comments").json()[0]
    assert hidden["is_revealed"] is False
    assert "Spoiler hidden" in hidden["comment"]

    headers = {"Authorization": f"Bearer {register_user(client, 'Another Fan', 'another@example.com')[0]['access_token']}"}
    before_episode = client.put(
        f"/users/me/progress/{anime_id}",
        json={"status": "watching", "episodes_watched": 4},
        headers=headers,
    )
    assert before_episode.status_code == 200
    assert client.get(f"/anime/{anime_id}/comments", headers=headers).json()[0]["is_revealed"] is False
    client.put(
        f"/users/me/progress/{anime_id}",
        json={"status": "watching", "episodes_watched": 5},
        headers=headers,
    )
    revealed = client.get(f"/anime/{anime_id}/comments", headers=headers).json()[0]
    assert revealed["is_revealed"] is True
    assert revealed["comment"] == "The reveal in this episode changes everything."

    invalid_spoiler = client.post(
        f"/anime/{anime_id}/comments",
        json={"comment": "Missing episode", "is_spoiler": True},
        headers=headers,
    )
    assert invalid_spoiler.status_code == 422


def test_public_catalog_search_maps_results_and_imports_attribution(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_anilist(search: str) -> dict:
        assert search == "Frieren"
        return {
            "data": {
                "Page": {
                    "media": [
                        {
                            "id": 52991,
                            "title": {"english": "Frieren: Beyond Journey's End", "romaji": "Sousou no Frieren"},
                            "genres": ["Adventure", "Drama", "Fantasy"],
                            "format": "TV",
                            "averageScore": 96,
                            "episodes": 28,
                            "duration": 24,
                            "description": "<p>After the journey, <b>Frieren</b> continues.</p>",
                            "coverImage": {
                                "extraLarge": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/test.jpg"
                            },
                            "startDate": {"year": 2023, "month": 9, "day": 29},
                            "studios": {"nodes": [{"name": "Madhouse"}]},
                        }
                    ]
                }
            }
        }

    monkeypatch.setattr(catalog_router, "_fetch_anilist", fake_fetch_anilist)
    result = client.get("/catalog/search", params={"q": "Frieren"})
    assert result.status_code == 200
    imported_anime = result.json()[0]
    assert imported_anime["rating"] == 9.6
    assert imported_anime["format"] == "TV"
    assert imported_anime["duration"] == 24
    assert imported_anime["description"] == "After the journey, Frieren continues."
    assert imported_anime["released_date"] == "2023-09-29"
    assert imported_anime["source_url"] == "https://anilist.co/anime/52991"

    _, headers = register_user(client, "Catalog Importer", "importer@example.com")
    created = client.post("/anime", json=imported_anime, headers=headers)
    assert created.status_code == 201
    anime_id = created.json()["id"]
    assert client.get(f"/anime/{anime_id}").json()["source_url"] == imported_anime["source_url"]
    duplicate_import = client.post("/anime", json=imported_anime, headers=headers)
    assert duplicate_import.status_code == 200
    assert duplicate_import.json()["id"] == anime_id


def test_catalog_search_requires_two_characters(client: TestClient) -> None:
    response = client.get("/catalog/search", params={"q": "a"})
    assert response.status_code == 422


def test_public_catalog_browse_filters_and_paginates(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_discovery(variables: dict) -> dict:
        assert variables["page"] == 2
        assert variables["year"] == 2024
        assert variables["season"] == "FALL"
        assert variables["format"] == "TV"
        assert variables["status"] == "FINISHED"
        assert variables["genres"] == ["Drama"]
        assert variables["minScore"] == 79
        assert "excludedIds" not in variables
        assert "search" not in variables
        return {
            "data": {
                "Page": {
                    "pageInfo": {
                        "currentPage": 2,
                        "hasNextPage": True,
                        "total": 60,
                        "perPage": 24,
                    },
                    "media": [],
                }
            }
        }

    monkeypatch.setattr(catalog_router, "_fetch_discovery", fake_discovery)
    response = client.get(
        "/catalog/browse",
        params={
            "page": 2,
            "year": 2024,
            "season": "FALL",
            "format": "TV",
            "status": "FINISHED",
            "genre": "Drama",
            "min_rating": 8,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"results": [], "page": 2, "has_next": True, "total": 60}


def test_catalog_discovery_uses_database_cache(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "data": {
            "Page": {
                "pageInfo": {"currentPage": 1, "hasNextPage": False, "total": 0, "perPage": 24},
                "media": [],
            }
        }
    }
    calls = 0

    class FakeResponse:
        is_error = False

        @staticmethod
        def json() -> dict:
            return payload

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            assert kwargs["timeout"] > 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            _ = args
            assert len(args) == 3
            return None

        async def post(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            return FakeResponse()

    monkeypatch.setattr(catalog_router.httpx, "AsyncClient", FakeAsyncClient)
    first = client.get("/catalog/browse", params={"sort": "SCORE_DESC"})
    second = client.get("/catalog/browse", params={"sort": "SCORE_DESC"})
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert calls == 1
    with SessionLocal() as db:
        cached = db.query(AniListCache).one()
        cached.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()

    class OfflineAsyncClient:
        def __init__(self, **kwargs):
            assert kwargs["timeout"] > 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            _ = args
            assert len(args) == 3
            return None

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("AniList is unavailable")

    monkeypatch.setattr(catalog_router.httpx, "AsyncClient", OfflineAsyncClient)
    stale = client.get("/catalog/browse", params={"sort": "SCORE_DESC"})
    assert stale.status_code == 200
    assert stale.json() == first.json()


def test_scheduled_popular_refresh_bypasses_fresh_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    class FakeResponse:
        is_error = False

        @staticmethod
        def json() -> dict:
            return {
                "data": {
                    "Page": {
                        "pageInfo": {
                            "currentPage": 1,
                            "hasNextPage": False,
                            "total": 0,
                            "perPage": 24,
                        },
                        "media": [],
                    }
                }
            }

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            assert kwargs["timeout"] == 12.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            _ = args
            return None

        async def post(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            return FakeResponse()

    monkeypatch.setattr(catalog_router.httpx, "AsyncClient", FakeAsyncClient)
    import asyncio

    asyncio.run(catalog_router.refresh_popular_catalog_cache())
    asyncio.run(catalog_router.refresh_popular_catalog_cache())
    assert calls == 2


def test_semantic_search_matches_synonyms_and_persists_embedding(
    client: TestClient,
) -> None:
    assert cosine_similarity(
        embed_text("cozy slice of life with cooking"),
        embed_text("a calm everyday food story"),
    ) > 0
    title = client.post(
        "/anime",
        json={
            **ANIME,
            "title": "Cozy Kitchen Story",
            "genre": "Slice of Life",
            "description": "A gentle everyday story about a chef making food for friends.",
        },
        headers=register_user(client, "Embedding User", "embedding@example.com")[1],
    ).json()

    response = client.post(
        "/catalog/semantic-search",
        json={"query": "cozy slice of life with cooking", "limit": 5},
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["id"] == title["id"]
    with SessionLocal() as db:
        embedding = db.get(AnimeEmbedding, title["id"])
        assert embedding is not None
        assert len(embedding.vector) == 384
        initial_hash = embedding.content_hash
        stored_title = db.get(Anime, title["id"])
        assert stored_title is not None
        stored_title.description = "A mystery about a detective investigating a quiet town."
        db.commit()

    changed = client.post(
        "/catalog/semantic-search",
        json={"query": "quiet town detective mystery", "limit": 5},
    )
    assert changed.status_code == 200
    with SessionLocal() as db:
        refreshed = db.get(AnimeEmbedding, title["id"])
        assert refreshed is not None
        assert refreshed.content_hash != initial_hash


def test_ai_recommendation_explanation_is_cached(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_API_KEY", "test-only-key")
    monkeypatch.setenv("AI_API_URL", "https://ai.example.test/v1/chat/completions")
    monkeypatch.setenv("AI_MODEL", "test-model")
    calls = 0

    class FakeResponse:
        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict:
            return {"choices": [{"message": {"content": "A gentle story with a strong found-family theme."}}]}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            assert kwargs["timeout"] == 20.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            _ = args
            return None

        async def post(self, url, *, headers, json):
            nonlocal calls
            calls += 1
            assert url == "https://ai.example.test/v1/chat/completions"
            assert headers["Authorization"] == "Bearer test-only-key"
            assert json["model"] == "test-model"
            return FakeResponse()

    monkeypatch.setattr(catalog_router.httpx, "AsyncClient", FakeAsyncClient)
    request = {
        "title": "Gentle Adventure",
        "synopsis": "A group of friends travels across a quiet fantasy world.",
        "genres": ["Adventure", "Fantasy"],
    }
    first = client.post("/catalog/recommendation-explanation", json=request)
    second = client.post("/catalog/recommendation-explanation", json=request)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert calls == 1


def test_ai_recommendation_explanation_is_explicitly_optional(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AI_API_KEY", raising=False)
    response = client.post(
        "/catalog/recommendation-explanation",
        json={"title": "A title", "synopsis": "A short synopsis."},
    )
    assert response.status_code == 503
    assert "AI_API_KEY" in response.json()["detail"]


def test_catalog_anime_details_maps_related_titles_and_credits(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_request(query: str, variables: dict, **kwargs: object) -> dict:
        assert "Media(id: $id, type: ANIME)" in query
        assert variables == {"id": 16498}
        assert kwargs["ttl"] == catalog_router.DETAIL_CACHE_TTL
        return {
            "data": {
                "Media": {
                    "relations": {
                        "edges": [
                            {
                                "relationType": "SEQUEL",
                                "node": {
                                    "id": 20958,
                                    "type": "ANIME",
                                    "title": {"english": "Attack on Titan Season 2", "romaji": None},
                                    "format": "TV",
                                    "coverImage": {"medium": "https://example.com/cover.jpg"},
                                },
                            }
                        ]
                    },
                    "studios": {"nodes": [{"id": 858, "name": "WIT STUDIO", "isAnimationStudio": True}]},
                    "staff": {
                        "edges": [
                            {"role": "Director", "node": {"id": 123, "name": {"full": "Tetsuro Araki"}}}
                        ]
                    },
                    "characters": {
                        "edges": [
                            {
                                "role": "MAIN",
                                "node": {"id": 456, "name": {"full": "Eren Yeager"}, "image": {"medium": None}},
                            }
                        ]
                    },
                }
            }
        }

    monkeypatch.setattr(catalog_router, "_request_anilist_cached", fake_request)
    response = client.get("/catalog/anime/16498/details")
    assert response.status_code == 200
    data = response.json()
    assert data["relations"][0]["relation"] == "SEQUEL"
    assert data["relations"][0]["url"] == "https://anilist.co/anime/20958"
    assert data["studios"][0]["is_animation_studio"] is True
    assert data["staff"][0]["name"] == "Tetsuro Araki"
    assert data["characters"][0]["name"] == "Eren Yeager"


def test_trending_seasonal_and_recommendations_catalogs(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict] = []

    async def fake_discovery(**kwargs: object) -> dict:
        captured.append(kwargs)
        return {"results": [], "page": 1, "has_next": False, "total": 0}

    monkeypatch.setattr(catalog_router, "_discover", fake_discovery)
    assert client.get("/catalog/trending").status_code == 200
    assert captured[-1]["sort"] == "TRENDING_DESC"
    assert client.get("/catalog/seasonal").status_code == 200
    assert captured[-1]["anime_status"] == "RELEASING"
    assert captured[-1]["season"] in {"WINTER", "SPRING", "SUMMER", "FALL"}

    assert client.get("/catalog/recommendations").status_code == 401
    _, headers = register_user(client, "Anime Fan", "fan@example.com")
    created = client.post(
        "/anime",
        json={
            **ANIME,
            "genre": "Adventure, Fantasy",
            "source_url": "https://anilist.co/anime/100",
        },
        headers=headers,
    )
    anime_id = created.json()["id"]
    assert client.post(f"/users/me/favorites/{anime_id}", headers=headers).status_code == 204
    completed_anime = client.post(
        "/anime",
        json={
            **ANIME,
            "title": "A Completed Favorite",
            "genre": "Comedy",
            "source_url": "https://anilist.co/anime/101",
        },
        headers=headers,
    ).json()
    assert client.put(
        f"/users/me/progress/{completed_anime['id']}",
        json={"status": "completed", "episodes_watched": 1},
        headers=headers,
    ).status_code == 200
    response = client.get("/catalog/recommendations", headers=headers)
    assert response.status_code == 200
    assert set(captured[-1]["genre"]) == {"Adventure", "Comedy", "Fantasy"}
    assert captured[-1]["excluded_ids"] == [100, 101]


def test_watch_progress_is_private_and_validates_episode_counts(client: TestClient) -> None:
    _, owner_headers = register_user(client, "Progress Owner", "progress@example.com")
    _, other_headers = register_user(client, "Progress Guest", "guest@example.com")
    created = client.post(
        "/anime",
        json={**ANIME, "episode": 12},
        headers=owner_headers,
    )
    anime_id = created.json()["id"]

    assert client.get("/users/me/progress").status_code == 401
    assert client.put(
        f"/users/me/progress/{anime_id}",
        json={"status": "watching", "episodes_watched": 13},
        headers=owner_headers,
    ).status_code == 422
    assert client.put(
        f"/users/me/progress/{anime_id}",
        json={"status": "watching", "episodes_watched": 4},
        headers=owner_headers,
    ).status_code == 200
    assert client.put(
        f"/users/me/progress/{anime_id}",
        json={"status": "invalid", "episodes_watched": 0},
        headers=owner_headers,
    ).status_code == 422

    saved = client.get("/users/me/progress", headers=owner_headers)
    assert len(saved.json()) == 1
    assert saved.json()[0]["episodes_watched"] == 4
    assert saved.json()[0]["status"] == "watching"
    assert client.get("/users/me/progress", headers=other_headers).json() == []
    completed = client.put(
        f"/users/me/progress/{anime_id}",
        json={"status": "completed", "episodes_watched": 1},
        headers=owner_headers,
    )
    assert completed.json()["episodes_watched"] == 12
    assert client.delete(f"/users/me/progress/{anime_id}", headers=owner_headers).status_code == 204
    assert client.get("/users/me/progress", headers=owner_headers).json() == []


def test_watch_queue_order_and_yearly_recap(client: TestClient) -> None:
    _, headers = register_user(client, "Queue Fan", "queue@example.com")
    first = client.post("/anime", json={**ANIME, "title": "Queue First", "episode": 8}, headers=headers).json()
    second = client.post("/anime", json={**ANIME, "title": "Queue Second", "episode": 12}, headers=headers).json()
    for anime in (first, second):
        assert client.put(
            f"/users/me/progress/{anime['id']}",
            json={"status": "plan_to_watch", "episodes_watched": 0},
            headers=headers,
        ).status_code == 200
    reordered = client.patch(
        "/users/me/progress/queue",
        json={"anime_ids": [second["id"], first["id"]]},
        headers=headers,
    )
    assert reordered.status_code == 200
    assert [item["anime_id"] for item in reordered.json() if item["status"] == "plan_to_watch"] == [
        second["id"],
        first["id"],
    ]
    assert client.patch(
        "/users/me/progress/queue",
        json={"anime_ids": [first["id"]]},
        headers=headers,
    ).status_code == 422

    completed = client.put(
        f"/users/me/progress/{first['id']}",
        json={"status": "completed", "episodes_watched": 1},
        headers=headers,
    )
    assert completed.json()["completed_at"] is not None
    year = datetime.now(timezone.utc).year
    recap = client.get(f"/users/me/progress/recap?year={year}", headers=headers)
    assert recap.status_code == 200
    assert recap.json()["completed_count"] == 1
    assert recap.json()["episodes_watched"] == 8
    assert recap.json()["titles"][0]["title"] == "Queue First"
    assert recap.json()["titles"][0]["cover_image"] == anime["cover_image"]
    assert recap.json()["completion_days"] == 1
    assert len(recap.json()["monthly_completions"]) == 12
    assert sum(recap.json()["monthly_completions"]) == 1


def test_airing_calendar_uses_only_saved_anilist_titles(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, headers = register_user(client, "Airing Fan", "airing@example.com")
    anime = client.post(
        "/anime",
        json={**ANIME, "title": "Airing Anime", "source_url": "https://anilist.co/anime/999"},
        headers=headers,
    ).json()
    assert client.post(f"/users/me/favorites/{anime['id']}", headers=headers).status_code == 204
    captured: list[dict] = []

    async def fake_discovery(variables: dict) -> dict:
        captured.append(variables)
        return {
            "data": {
                "Page": {
                    "pageInfo": {"currentPage": 1, "hasNextPage": False, "total": 1, "perPage": 1},
                    "media": [
                        {
                            "id": 999,
                            "title": {"english": "Airing Anime", "romaji": "Airing Anime"},
                            "genres": ["Drama"],
                            "format": "TV",
                            "averageScore": 80,
                            "episodes": 12,
                            "duration": 24,
                            "description": "Airing episode.",
                            "coverImage": {"large": "https://example.com/cover.jpg"},
                            "startDate": {"year": 2024, "month": 1, "day": 1},
                            "studios": {"nodes": []},
                            "nextAiringEpisode": {
                                "airingAt": int(datetime.now(timezone.utc).timestamp()) + 3600,
                                "timeUntilAiring": 3600,
                                "episode": 7,
                            },
                        }
                    ],
                }
            }
        }

    monkeypatch.setattr(catalog_router, "_fetch_discovery", fake_discovery)
    response = client.get("/catalog/airing", headers=headers)
    assert response.status_code == 200
    assert captured[0]["ids"] == [999]
    assert "airingAfter" not in captured[0]
    assert "airingAt_greater" not in catalog_router.DISCOVERY_QUERY
    assert "nextAiringEpisode" in catalog_router.DISCOVERY_QUERY
    assert response.json()["results"][0]["local_anime_id"] == anime["id"]
    assert response.json()["results"][0]["next_episode"]["episode"] == 7
