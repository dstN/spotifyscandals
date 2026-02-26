# Spotify Skandal Tracker — Architecture

## Overview

A web application that lets users submit Spotify playlists, extracts all artists, and uses Google Gemini Pro to discover scandals associated with approved artists. Admins review, approve, and verify scandal data through a modern dashboard.

---

## Tech Stack

| Layer      | Technology            | Rationale                                            |
| ---------- | --------------------- | ---------------------------------------------------- |
| Frontend   | Svelte 5 + Vite       | Lightweight, reactive, fast compilation              |
| Styling    | TailwindCSS v4        | Utility-first CSS with Apple Glass design tokens     |
| Backend    | Python 3.12 + FastAPI | Async REST API, auto-generated OpenAPI docs          |
| Database   | SQLite + SQLAlchemy   | Zero-config persistence, excellent for single-server |
| ORM        | SQLAlchemy 2.0        | Declarative models, migration support                |
| API: Music | Spotify Web API       | Playlist + artist metadata extraction                |
| API: AI    | Google Gemini Pro     | Scandal detection via structured prompts             |

---

## Directory Structure

```
spotifyscandals/
├── ARCHITECTURE.md
├── .env.example
├── backend/
│   ├── requirements.txt
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Environment & settings
│   ├── database.py              # SQLAlchemy engine & session
│   ├── models.py                # ORM models (artists, scandals, sources)
│   ├── schemas.py               # Pydantic request/response schemas
│   ├── routers/
│   │   ├── artists.py           # /api/artists endpoints
│   │   ├── scandals.py          # /api/scandals endpoints
│   │   └── playlists.py         # /api/playlists endpoints
│   └── services/
│       ├── spotify.py           # Spotify Web API client
│       └── gemini.py            # Gemini Pro client
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── app.css              # Global styles + Apple Glass tokens
│   │   ├── App.svelte           # Root component + router
│   │   ├── lib/
│   │   │   ├── api.js           # HTTP client for backend
│   │   │   └── stores.js        # Svelte stores
│   │   └── routes/
│   │       ├── Dashboard.svelte
│   │       ├── Artists.svelte
│   │       ├── Scandals.svelte
│   │       └── Submit.svelte
│   └── index.html
└── scripts/
    └── init_db.py               # Database initialization
```

---

## Database Schema

```
┌─────────────────────┐     ┌─────────────────────────┐     ┌──────────────────────────┐
│      artists        │     │        scandals          │     │    scandal_sources       │
├─────────────────────┤     ├─────────────────────────┤     ├──────────────────────────┤
│ id         INTEGER PK│────▸│ id          INTEGER PK  │────▸│ id           INTEGER PK  │
│ name       TEXT      │     │ artist_id   INTEGER FK  │     │ scandal_id   INTEGER FK  │
│ spotify_id TEXT UNQ  │     │ description TEXT        │     │ source_url   TEXT        │
│ image_url  TEXT      │     │ date_detected DATETIME  │     │ created_at   DATETIME   │
│ approved   BOOLEAN   │     │ verified    BOOLEAN     │     └──────────────────────────┘
│ created_at DATETIME  │     │ created_at  DATETIME    │
└─────────────────────┘     └─────────────────────────┘
```

---

## API Endpoints

### Playlists

| Method | Path                    | Description                                   |
| ------ | ----------------------- | --------------------------------------------- |
| POST   | `/api/playlists/submit` | Submit Spotify playlist URL → extract artists |

### Artists

| Method | Path                        | Description                         |
| ------ | --------------------------- | ----------------------------------- |
| GET    | `/api/artists`              | List all artists (filter: approved) |
| GET    | `/api/artists/{id}`         | Get single artist + scandals        |
| PATCH  | `/api/artists/{id}/approve` | Admin: approve artist for scanning  |

### Scandals

| Method | Path                        | Description                          |
| ------ | --------------------------- | ------------------------------------ |
| GET    | `/api/scandals`             | List all scandals (filter: verified) |
| POST   | `/api/scandals/scan`        | Scan approved artists via Gemini     |
| PATCH  | `/api/scandals/{id}/verify` | Admin: verify scandal                |

---

## Workflow

```
User submits playlist URL
        │
        ▼
Backend extracts playlist ID from URL
        │
        ▼
Spotify API → fetch playlist tracks → extract unique artists
        │
        ▼
Store artists in DB (upsert by spotify_id)
        │
        ▼
Admin reviews artist list → approves selected artists
        │
        ▼
Approved artists → Gemini Pro structured prompt
        │
        ▼
Gemini returns JSON: [{description, sources: [url, ...]}]
        │
        ▼
Store in `scandals` + `scandal_sources` tables
        │
        ▼
Admin reviews scandals → verifies sources → updates DB
```

---

## Design: Apple Glass 2025

Key design tokens for the UI:

- **Backgrounds**: Frosted glass (`backdrop-filter: blur(20px)`) with translucent surfaces
- **Colors**: Neutral grays, soft whites, subtle gradients, accent: electric blue `#007AFF`
- **Typography**: Inter font family, light weights, generous spacing
- **Cards**: Rounded (`border-radius: 20px`), soft shadows, glass morphism
- **Animations**: Subtle `transition: all 0.3s ease`, hover scale/glow effects
- **Dark Mode**: Default dark palette with OLED blacks and glass overlays
