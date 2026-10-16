# Anime Hub data structure

```text
User 1 ───── * Anime
  │              │
  ├──── * Comment * ──── 1
  │
  └──── * Favourite * ── 1

Genre
```

- A user can add anime, write comments, and save favorites.
- Each anime can have comments and favorites; deleting an anime removes those dependent rows.
- Each comment and favorite belongs to one user and one anime.
- A user's watch-progress record tracks status and episodes watched per anime.
- `Anime.genre` stores the comma-separated genre labels displayed by the catalog. `Genre` is retained as a lookup table for future normalization.

## Models and API modules

- `models/user.py`, `models/anime.py`, and `models/comment.py` define the SQLAlchemy entities.
- `schemas/` validates API input and shapes API responses.
- `routers/` exposes anime, account, favorite, comment, AniList discovery, recommendations, and watch-progress endpoints.
- `database.py` configures the SQLAlchemy engine. SQLite is the local default; `DB_URL` can select another supported database.
- Catalog imports retain their AniList source URL for attribution; database initialization adds this nullable field to existing anime tables.
