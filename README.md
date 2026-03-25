# spotifyscandals

A web app that scans Spotify playlists for artist controversies using Google Gemini AI. Submit a playlist, and the app extracts artists, discovers scandals via AI-powered web search, and lets the community vote on severity.

## Features

- **Playlist Scanning** — Paste a Spotify playlist URL to extract all artists
- **AI Scandal Detection** — Google Gemini discovers controversies with source verification
- **Community Voting** — Spotify-authenticated users rate scandal severity (0-10)
- **Safety Scores** — Aggregated severity ratings per artist
- **Community Submissions** — Users can submit scandals and sources for admin review
- **Source Verification** — AI + web scraping validates scandal sources
- **Batch Processing** — Gemini Batch API support for scanning many artists at once
- **Admin Dashboard** — Full CRUD for artists, scandals, sources, and community submissions

## Tech Stack

| Layer    | Technology                             |
| -------- | -------------------------------------- |
| Frontend | Svelte 5, Vite, TailwindCSS v4         |
| Backend  | Python 3.12, FastAPI                   |
| Database | SQLite + SQLAlchemy 2.0                |
| AI       | Google Gemini (gemini-3-flash-preview) |
| Auth     | JWT (admin) + Spotify OAuth (public)   |

## Setup

### Prerequisites

- Python 3.12+
- Node.js 18+
- Spotify Developer App ([developer.spotify.com](https://developer.spotify.com))
- Google Gemini API key ([aistudio.google.com](https://aistudio.google.com))

### 1. Clone & configure

```bash
git clone https://github.com/yourusername/spotifyscandals.git
cd spotifyscandals
cp .env.example .env
```

Edit `.env` with your credentials:

```env
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
GEMINI_API_KEY=your_gemini_api_key
JWT_SECRET=generate_a_random_secret_here
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=$2b$12$...
```

Generate an admin password hash:

```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The database is created automatically on first start (SQLite, WAL mode).

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server runs on `http://localhost:5173` and proxies `/api` to the backend.

### Production build

```bash
cd frontend
npm run build
```

The backend serves the built `dist/` folder as static files at `/`.

## Usage

1. **Submit a playlist** — Paste a Spotify playlist URL on the home page
2. **Admin approves artists** — Login at `/login`, approve extracted artists
3. **Scan for scandals** — Trigger AI scanning from the admin dashboard
4. **Review & verify** — Admin verifies scandals and sources
5. **Public voting** — Anyone with a Spotify account can vote on scandal severity

## Project Structure

```text
spotifyscandals/
├── backend/          # FastAPI API server
│   ├── routers/      # Route handlers (artists, scandals, auth, community)
│   ├── services/     # Spotify client, Gemini AI scanner, background tasks
│   └── main.py       # App entry point with middleware
├── frontend/         # Svelte 5 SPA
│   └── src/
│       ├── lib/      # API client, stores, shared components
│       └── routes/   # Page components (admin + public)
└── scripts/          # DB init, batch poller, test utilities
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed documentation.

## License

See [LICENSE](LICENSE).
