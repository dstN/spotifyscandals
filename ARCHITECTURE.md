# spotifyscandals — Architecture

## Overview

A web application that lets users submit Spotify playlists, extracts all artists, and uses Google Gemini AI to discover scandals associated with approved artists. Features include admin review/approval workflows, community-submitted scandals, public voting on scandal relevance, Spotify OAuth for public users, and source verification via AI and web scraping. Admins manage artists, scandals, community submissions, and sources through a comprehensive dashboard.

---

## Tech Stack

| Layer      | Technology                               | Rationale                                            |
| ---------- | ---------------------------------------- | ---------------------------------------------------- |
| Frontend   | Svelte 5 + Vite                          | Lightweight, reactive, fast compilation              |
| Styling    | TailwindCSS v4                           | Utility-first CSS with Apple Glass design tokens     |
| Backend    | Python 3.12 + FastAPI                    | Async REST API, auto-generated OpenAPI docs          |
| Database   | SQLite + SQLAlchemy                      | Zero-config persistence, excellent for single-server |
| ORM        | SQLAlchemy 2.0                           | Declarative models, migration support                |
| API: Music | Spotify Web API                          | Playlist + artist metadata extraction                |
| API: AI    | Google Gemini (`gemini-3-flash-preview`) | Scandal detection via structured prompts + Batch API |
| Auth       | PyJWT                                    | JWT token generation/validation for admin + public   |
| HTTP       | httpx                                    | Async HTTP client for Spotify API + source fetching  |
| Scraping   | Playwright                               | Headless browser fallback for source verification    |
| Scraping   | BeautifulSoup4                           | HTML parsing for source content extraction           |

---

## Directory Structure

```text
spotifyscandals/
├── ARCHITECTURE.md
├── .env.example
├── start_backend.sh
├── start_frontend.sh
├── backend/
│   ├── requirements.txt
│   ├── main.py                     # FastAPI app, CORS, lifespan, security headers middleware
│   ├── config.py                   # Pydantic Settings (env vars)
│   ├── database.py                 # SQLAlchemy engine, session, init_db
│   ├── models.py                   # 7 ORM models
│   ├── schemas.py                  # Pydantic request/response schemas
│   ├── errors.py                   # HTTPException factory helpers (not_found, bad_request, etc.)
│   ├── auth_deps.py                # JWT auth dependencies (admin + public)
│   ├── scanner_cli.py              # Detached CLI scanner subprocess
│   ├── db_migrate.py               # Manual SQLite migration script
│   ├── reset_db.py                 # Database wipe utility
│   ├── requirements-dev.txt        # Dev dependencies (pytest, ruff, mypy)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── artists.py              # /api/artists CRUD
│   │   ├── scandals.py             # /api/scandals CRUD + scanning + voting
│   │   ├── playlists.py            # /api/playlists playlist submission
│   │   ├── auth.py                 # /api/auth admin login
│   │   ├── community.py            # /api/community-scandals admin review
│   │   └── spotify_auth.py         # /api/public/auth/spotify OAuth flow
│   └── services/
│       ├── __init__.py
│       ├── spotify.py              # Spotify Web API client
│       └── gemini/                 # Gemini AI scanning package
│           ├── __init__.py         # Re-exports all public functions
│           ├── rate_limiter.py     # Token-bucket rate limiter
│           ├── url_resolver.py     # URL resolution (httpx → curl → Playwright), SSRF protection
│           ├── source_matcher.py   # Match sources to scandals via groundingSupports
│           ├── scanner.py          # Core scanning: scan_artist(s)_for_scandals
│           ├── evaluator.py        # Source verification: verify/score/find_better_sources
│           └── batch.py            # Gemini Batch API: create/submit/poll/parse
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── svelte.config.js
│   ├── index.html
│   └── src/
│       ├── app.css                 # TailwindCSS v4 + Apple Glass tokens
│       ├── App.svelte              # Root component + History API router
│       ├── main.js                 # Entry point
│       ├── lib/
│       │   ├── api.js              # HTTP client for backend
│       │   ├── stores.js           # Svelte stores (auth, spotify)
│       │   ├── ScandalCard.svelte  # Scandal accordion card (voting, sources)
│       │   └── CommunitySubmitPopup.svelte # Community scandal submit modal
│       └── routes/
│           ├── Dashboard.svelte           # Admin dashboard
│           ├── Artists.svelte             # Admin artist management
│           ├── Scandals.svelte            # Admin scandal management
│           ├── Submit.svelte              # Playlist submission form
│           ├── Login.svelte               # Admin login form
│           ├── NotFound.svelte            # 404 page
│           ├── ArtistScandalsAdmin.svelte # Admin artist scandal detail
│           ├── CommunityAdmin.svelte      # Admin community scandal review
│           ├── CommunityArtistAdmin.svelte# Admin community artist view
│           ├── CommunitySourcesAdmin.svelte# Admin community source review
│           └── public/
│               ├── Home.svelte            # Public homepage + Spotify login
│               ├── AuthCallback.svelte    # Spotify OAuth callback
│               └── ArtistScandals.svelte  # Public artist scandal viewer
└── scripts/
    ├── init_db.py                  # Database initialization
    ├── batch_poller.py             # Gemini Batch API job poller
    └── test_voting.py              # Vote API test utility
```

---

## Database Schema

```text
┌──────────────────────────┐     ┌───────────────────────────┐     ┌────────────────────────────┐
│        artists           │     │         scandals          │     │     scandal_sources        │
├──────────────────────────┤     ├───────────────────────────┤     ├────────────────────────────┤
│ id           INTEGER PK  │────▸│ id            INTEGER PK  │────▸│ id             INTEGER PK  │
│ name         TEXT         │     │ artist_id     INTEGER FK  │     │ scandal_id     INTEGER FK  │
│ spotify_id   TEXT UNQ     │     │ title         TEXT        │     │ source_url     TEXT         │
│ image_url    TEXT         │     │ description   TEXT        │     │ source_title   TEXT         │
│ approved     BOOLEAN      │     │ date_detected DATETIME   │     │ is_reported    BOOLEAN      │
│ last_scanned_at DATETIME │     │ verified      BOOLEAN     │     │ is_verified    BOOLEAN      │
│ created_at   DATETIME     │     │ is_community  BOOLEAN     │     │ created_at     DATETIME     │
└──────────────────────────┘     │ created_at    DATETIME    │     └────────────────────────────┘
                                 └───────────────────────────┘

┌──────────────────────────┐     ┌───────────────────────────┐     ┌────────────────────────────┐
│  scandal_votings         │     │   community_scandals      │     │   community_sources        │
├──────────────────────────┤     ├───────────────────────────┤     ├────────────────────────────┤
│ id           INTEGER PK  │     │ id            INTEGER PK  │     │ id             INTEGER PK  │
│ scandal_id   INTEGER FK  │     │ artist_id     INTEGER FK  │     │ scandal_id     INTEGER FK  │
│ spotify_user_id TEXT     │     │ spotify_user_id TEXT      │     │ spotify_user_id TEXT        │
│ vote_value   INTEGER      │     │ title         TEXT        │     │ source_url     TEXT         │
│ created_at   DATETIME     │     │ description   TEXT        │     │ created_at     DATETIME     │
│ updated_at   DATETIME     │     │ source_url    TEXT        │     └────────────────────────────┘
└──────────────────────────┘     │ created_at    DATETIME    │
                                 └───────────────────────────┘

┌──────────────────────────┐
│       batch_jobs         │
├──────────────────────────┤
│ id           INTEGER PK  │
│ job_name     TEXT UNQ     │
│ status       TEXT         │
│ artist_ids_json TEXT(JSON)│
│ created_at   DATETIME     │
│ completed_at DATETIME     │
└──────────────────────────┘
```

---

## Authentication

### Admin Authentication

- `POST /api/auth/login` with username/password
- Server validates credentials against environment variables
- Returns JWT (HS256, 24h expiry) with `sub: admin_username`
- Frontend stores in `localStorage` as `admin_token`
- Protected endpoints use `Depends(require_admin)` from `auth_deps.py`

### Public User Authentication (Spotify OAuth)

- `GET /api/public/auth/spotify/login` redirects to Spotify authorization
- Spotify callback returns authorization code
- Server exchanges code for access token via Spotify API
- Server creates JWT (HS256, 30 days) with Spotify user claims
- Frontend receives JWT + Spotify access token via redirect URL
- Protected endpoints use `Depends(get_current_public_user)` from `auth_deps.py`

---

## API Endpoints

### Auth

| Method | Path              | Auth | Description       |
| ------ | ----------------- | ---- | ----------------- |
| POST   | `/api/auth/login` | None | Admin login → JWT |

### Spotify OAuth

| Method | Path                                | Auth | Description                   |
| ------ | ----------------------------------- | ---- | ----------------------------- |
| GET    | `/api/public/auth/spotify/login`    | None | Initiate Spotify OAuth flow   |
| GET    | `/api/public/auth/spotify/callback` | None | Handle Spotify OAuth callback |

### Playlists

| Method | Path                    | Auth | Description                                   |
| ------ | ----------------------- | ---- | --------------------------------------------- |
| POST   | `/api/playlists/submit` | None | Submit Spotify playlist URL → extract artists |

### Artists

| Method | Path                                   | Auth   | Description                     |
| ------ | -------------------------------------- | ------ | ------------------------------- |
| GET    | `/api/artists`                         | Admin  | List all artists with filters   |
| GET    | `/api/artists/{id}`                    | Admin  | Get single artist with scandals |
| GET    | `/api/artists/public`                  | None   | List approved artists (public)  |
| PATCH  | `/api/artists/{id}/approve`            | Admin  | Approve artist for scanning     |
| POST   | `/api/artists/approve-all`             | Admin  | Approve all pending artists     |
| DELETE | `/api/artists/{id}`                    | Admin  | Delete artist                   |
| POST   | `/api/artists/{id}/community-scandals` | Public | Submit community scandal        |

### Scandals

| Method | Path                                      | Auth   | Description                    |
| ------ | ----------------------------------------- | ------ | ------------------------------ |
| GET    | `/api/scandals`                           | None   | List all scandals with filters |
| GET    | `/api/scandals/stats`                     | None   | Get aggregate statistics       |
| POST   | `/api/scandals/scan`                      | Admin  | Trigger AI scandal scan        |
| POST   | `/api/scandals/{id}/vote`                 | Public | Submit vote (0-10)             |
| POST   | `/api/scandals/{id}/sources`              | Admin  | Add source to scandal          |
| POST   | `/api/scandals/{id}/community-sources`    | Public | Submit community source        |
| POST   | `/api/scandals/{id}/sources/{sid}/report` | Public | Report a source                |
| PATCH  | `/api/scandals/{id}/verify`               | Admin  | Toggle scandal verification    |
| PATCH  | `/api/scandals/{id}/sources/{sid}/verify` | Admin  | Toggle source verification     |
| DELETE | `/api/scandals/{id}`                      | Admin  | Delete scandal                 |
| DELETE | `/api/scandals/{id}/sources/{sid}`        | Admin  | Delete source                  |

### Community

| Method | Path                                           | Auth  | Description                         |
| ------ | ---------------------------------------------- | ----- | ----------------------------------- |
| GET    | `/api/community-scandals`                      | Admin | List community submissions          |
| GET    | `/api/community-scandals/{id}`                 | Admin | Get submission detail               |
| GET    | `/api/community-scandals/pending-count`        | Admin | Get count of pending submissions    |
| GET    | `/api/community-scandals/sources`              | Admin | List community source submissions   |
| POST   | `/api/community-scandals/{id}/verify`          | Admin | Approve submission → create scandal |
| POST   | `/api/community-scandals/sources/{id}/approve` | Admin | Approve community source            |
| DELETE | `/api/community-scandals/{id}`                 | Admin | Delete/reject submission            |
| DELETE | `/api/community-scandals/sources/{id}`         | Admin | Delete/reject community source      |

### Internal

| Method | Path          | Auth | Description           |
| ------ | ------------- | ---- | --------------------- |
| GET    | `/api/health` | None | Health check endpoint |

---

## Workflow

### Flow 1 — Playlist Submission

```text
User submits playlist URL
        │
        ▼
Backend extracts Spotify playlist ID from URL
        │
        ▼
Spotify API → fetch playlist tracks → extract unique artists
        │
        ▼
Upsert artists in DB (by spotify_id)
        │
        ▼
Return artist list to frontend
```

### Flow 2 — Scandal Scanning

```text
Admin triggers manual scan from dashboard
        │
        ▼
Select approved artists that haven't been scanned recently
        │
        ▼
Mode A: Interactive → Gemini generate_content per artist
Mode B: Batch → Create JSONL, submit to Gemini Batch API
        │
        ▼
Parse structured response → store scandals + sources
        │
        ▼
Source verification: Gemini url_context → httpx → Playwright
        │
        ▼
Update artist last_scanned_at timestamp
        │
        ▼
Admin reviews scandals → verifies sources → updates DB
```

### Flow 3 — Community Submission

```text
Public user (Spotify-authenticated) submits scandal
        │
        ▼
Store as community_scandal (pending admin review)
        │
        ▼
User optionally adds community_sources
        │
        ▼
Admin reviews → verify (creates real scandal) / reject (deletes)
```

### Flow 4 — Public Voting

```text
Public user views artist scandals
        │
        ▼
User votes 0-10 on scandal relevance
        │
        ▼
Vote stored in scandal_votings (one per user per scandal)
        │
        ▼
Vote counts aggregated on query (no denormalized columns)
```

---

## Security

- **Security Headers Middleware**: All responses include CSP, X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy
- **SPA Path Traversal Protection**: Static file serving validates resolved paths stay within the frontend dist directory
- **JWT Secret Validation**: Rejects secrets shorter than 32 characters or containing 'change'; auto-generates a cryptographically secure secret if unset
- **SSRF Protection**: URL resolver in `gemini/url_resolver.py` blocks private/reserved IP ranges and internal hostnames
- **Role Validation**: `require_admin` uses positive role check (`role == "admin"`) to prevent bypass via unexpected role values
- **Rate Limiting**: Per-endpoint rate limiting on public-facing auth endpoints (429 Too Many Requests)
- **OAuth CSRF Protection**: Spotify OAuth flow uses a cryptographic `state` parameter stored in an httponly cookie, validated with constant-time comparison on callback
- **Stale Scan Lock Cleanup**: The `scan.lock` file includes PID tracking and a 2-hour timeout; stale locks are automatically removed to prevent deadlocks

---

## Deployment

The application requires the environment variables documented in `.env.example`.

**Backend**:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Frontend**:

```bash
cd frontend
npm install
npm run build    # Production build → dist/
npm run dev      # Development with HMR
```

The backend serves the frontend's `dist/` folder as static files at `/` in production. In development, Vite proxies `/api` requests to the backend.

**Database**: SQLite, created automatically at first start. WAL mode is enabled for concurrent reads.

---

## Design: Apple Glass 2025

Key design tokens for the UI:

- **Backgrounds**: Frosted glass (`backdrop-filter: blur(20px)`) with translucent surfaces
- **Colors**: Neutral grays, soft whites, subtle gradients, accent: Spotify green `#1db954` / `#1ed760`
- **Typography**: Inter font family, light weights, generous spacing
- **Cards**: Rounded (`border-radius: 20px`), soft shadows, glass morphism
- **Animations**: Subtle `transition: all 0.3s ease`, hover scale/glow effects
- **Dark Mode**: Default dark palette with OLED blacks and glass overlays
