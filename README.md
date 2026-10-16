# Anime Hub

A responsive anime catalog built with FastAPI, SQLAlchemy, and plain HTML, CSS, and JavaScript.

## Run locally

Use Python 3.10 or newer.

1. Create and activate a Python virtual environment.
2. Install the packages with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env`. Set `DB_URL` to your PostgreSQL connection URL and `SECRET_KEY` to a long, random value.
4. Apply database migrations from the project root:

   ```powershell
   .\.venv\Scripts\python.exe -m alembic upgrade head
   ```

   For a database created by an older Anime Hub version, the first migration adopts its existing tables and adds the known missing columns. Back up the database before upgrading.
5. Start the app from the project root:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
   ```

5. Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Interactive API documentation is at `/docs`.

## Run with Docker

Copy `.env.example` to `.env`, replace the example `SECRET_KEY` and PostgreSQL password, then build and start the app:

```powershell
docker compose up --build
```

The app is available at [http://127.0.0.1:8000](http://127.0.0.1:8000). Compose starts PostgreSQL 16 with a persistent `postgres-data` volume, waits for its health check, runs the one-shot Alembic migration service, and starts the app only after migrations succeed. Port 5432 is also bound to loopback for local development. The database password is interpolated into the connection URL, so use URL-safe characters or percent-encode reserved characters. For a PostgreSQL server outside Compose, replace the web service's `DB_URL` with a host reachable from Docker (use `host.docker.internal` rather than `localhost` for a database running on the host).

For production deployments, run `alembic upgrade head` once as a controlled release/deployment step before rolling out application instances. Do not run schema migrations independently in every application worker. The initial legacy-baseline migration is intentionally irreversible to avoid dropping pre-existing tables or data; restore a tested database backup to roll back that baseline.

The Compose port is bound to loopback for local use. For public deployment, place the app behind a TLS-terminating reverse proxy and apply shared rate limiting/WAF protections there. App-level sliding-window limits cover login, registration, catalog requests, and general requests per client IP; unsuccessful login attempts are also throttled per normalized account. These in-memory limits are process-local and are not a substitute for edge protection against distributed denial-of-service attacks. Request bodies larger than 1 MiB are rejected based on their actual streamed size, including requests without a `Content-Length` header.

Signed-in users can upload a JPEG, PNG, or WebP profile picture up to 900 KiB. The server validates and re-encodes uploads as WebP before storing them. Docker Compose persists uploaded pictures in the `profile-uploads` volume; for AWS or other multi-instance deployments, use durable shared object storage such as S3 instead of instance-local files.

Passwords are hashed using PBKDF2-HMAC-SHA256 with a unique random salt and 310,000 iterations. SQLAlchemy ORM queries bind user-supplied values as parameters; raw migration SQL contains only fixed statements. Responses include a restrictive Content Security Policy and standard browser security headers. Inline scripts are blocked; Swagger's generated bootstrap scripts use per-response nonces, and documentation assets are allowlisted from their CDN hosts.

## Administrator console

Apply migrations, register the account that should administer the site, then grant it access from the project root using the configured `DB_URL`:

```powershell
.\.venv\Scripts\python.exe -m app.admin promote admin@example.com
```

This local-only command requires shell/database access; there is no public role-promotion API. Sign in with that account and open `/admin.html`. All `/admin/*` APIs independently enforce the database-backed administrator role. The console provides platform counts, new registrations, recent community and moderation activity, AniList cache freshness, anime editing, a pending-comment review queue, account suspension/reactivation, and an attributable moderation log. Anime imports are deduplicated by AniList ID; catalog edits retain source attribution and are marked as locally edited. Suspended accounts cannot sign in or use authenticated endpoints. The initial administrator role is granted manually with the CLI; administrator role changes remain a trusted-operator task.

## Run tests

Install the development dependencies and run pytest:

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```

The tests use a temporary SQLite database and do not connect to the database configured in `.env`. GitHub Actions runs the same test suite on Python 3.10, 3.12, and 3.14.

## Features

- Search, genre filters, sorting, featured title, and mobile-friendly anime catalog.
- Search the public AniList catalog from the add-title dialog and import one title or all matching results (up to 10 per search) with their synopsis, rating, release date, studio, cover, and source attribution.
- Browse the public anime catalog without importing, with paginated search, seasonal and trending lists, filters, and personal recommendations.
- Search the local collection by synopsis meaning with locally generated, persisted text vectors and cosine similarity.
- Request a short, spoiler-free AI recommendation explanation from an optional OpenAI-compatible API; successful responses are cached for 30 days.
- Refresh the popular AniList discovery cache asynchronously every 15 minutes, in addition to request-time cache refreshes.
- Cache AniList search results for 10 minutes, discovery results for 20 minutes, and detailed relations/credits for 24 hours in PostgreSQL; serve cached responses for up to 30 days when AniList is temporarily unavailable.
- Open an AniList-imported anime to browse its prequels, sequels, related titles, studios, staff, and characters.
- Use the mood-based picker to get popular recommendations by vibe, available watch time, and movie/series format.
- Track per-title watch status and episodes watched from anime details; see your progress from your profile.
- Hide episode-tagged spoiler comments until the signed-in reader has watched that episode.
- See upcoming episodes for saved/watching AniList titles, reorder a plan-to-watch queue, view a genre/studio taste map, and browse an Anime Wrapped-style yearly recap with monthly completions, completed-title posters, and genre/studio highlights.
- Account registration and sign-in with password hashing and expiring bearer tokens.
- Change your password from your profile after verifying your current password.
- Upload a JPEG, PNG, or WebP profile picture; uploads are validated, resized, and stored as WebP.
- Add anime titles, edit or delete titles you created, and manage a personal watchlist.
- Anime details, community comments, and a profile with watchlist and created titles.
- Guest watchlists are kept in browser storage; signed-in watchlists are stored in the database.
- Versioned Alembic migrations create the schema and adopt the known unversioned Anime Hub schema without dropping existing records. Yearly recaps include completions recorded after completion timestamps were added; older completed entries have no historical completion date to report.

## API

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| POST | `/auth/register` | Public | Create an account |
| POST | `/auth/login` | Public | Sign in |
| POST | `/auth/token` | Public | OAuth2 password flow for Swagger authorization; `username` accepts account email or display name |
| GET | `/auth/me` | Signed in | Get the current account |
| POST | `/auth/change-password` | Signed in | Change the current account password after verifying the existing password |
| GET | `/anime` | Public | List the catalog |
| GET | `/anime/{anime_id}` | Public | Get anime details |
| POST | `/anime` | Signed in | Add a title |
| PATCH / DELETE | `/anime/{anime_id}` | Creator | Update or delete a title |
| GET | `/anime/{anime_id}/comments` | Public | List comments |
| GET | `/catalog/search?q=...` | Public | Search the AniList anime catalog |
| GET | `/catalog/browse` | Public | Browse/filter AniList with pagination |
| GET | `/catalog/anime/{anilist_id}/details` | Public | Get AniList relations, studios, staff, and characters |
| POST | `/catalog/semantic-search` | Public | Search local anime by synopsis meaning (`query`, optional `limit`) |
| POST | `/catalog/recommendation-explanation` | Public | Generate/cache an AI explanation (`AI_API_KEY` required) |
| GET | `/catalog/trending` | Public | Browse trending titles |
| GET | `/catalog/seasonal` | Public | Browse currently airing seasonal titles |
| GET | `/catalog/recommendations` | Signed in | Recommend titles from your favorites and completed shows |
| GET | `/users/me/progress` | Signed in | List your watch progress |
| PUT / DELETE | `/users/me/progress/{anime_id}` | Signed in | Save or remove watch progress |
| POST | `/anime/{anime_id}/comments` | Signed in | Add a comment |
| DELETE | `/comments/{comment_id}` | Comment author | Delete a comment |
| GET | `/users/me` | Signed in | Get your profile |
| PATCH | `/users/me` | Signed in | Update your profile |
| POST | `/users/me/avatar` | Signed in | Upload and set a profile picture (multipart `image`; JPEG, PNG, or WebP up to 900 KiB) |
| GET | `/users/me/favorites` | Signed in | List your favorites |
| POST / DELETE | `/users/me/favorites/{anime_id}` | Signed in | Add or remove a favorite |

If `SECRET_KEY` is omitted, the server generates a temporary key and reports that sessions will expire when the process restarts. Set a persistent key for normal use.

Semantic search generates deterministic 384-dimensional local text vectors, normalizes common anime concepts (for example cooking/food and cozy/calm), and ranks collection synopses with cosine similarity; it does not call an embedding service. Synopsis edits automatically cause vectors to be regenerated. AI explanations require `AI_API_KEY`; configure an OpenAI-compatible chat-completions endpoint and model with `AI_API_URL` and `AI_MODEL`. With no key, the endpoint returns a clear 503 and does not make an external call. Keep credentials private and out of source control.

The AniList catalog search requires an internet connection when its cached response expires. It lets you look up and import titles on demand rather than copying the entire, continually changing anime catalog into your database. The `/health` endpoint checks PostgreSQL readiness and reports cache/vector counts. Application logs are JSON lines, including request method, path, status, and duration. GitHub Actions runs the tests and Python compile check on every push and pull request.
