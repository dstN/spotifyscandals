# Spotify Scandals

Ein Monorepo-Projekt zur Analyse von Spotify- und YouTube-Playlists mit automatischer Erkennung von Künstler-Skandalen.

## 🎯 Features

- 📊 Playlist-Analyse (Spotify/YouTube)
- 🔍 Automatische Künstler-Extraktion
- ⚠️ Skandal-Datenbank (Wikipedia, News-APIs)
- 🎨 Moderne UI mit Vue 3 & Tailwind CSS
- 🚀 TypeScript-first Development
- 📦 Monorepo-Struktur mit npm Workspaces

## 📁 Struktur

```
spotifyscandals/
├── client/          # Vue 3 Frontend
│   ├── src/
│   │   ├── App.vue
│   │   ├── main.ts
│   │   └── style.css
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
├── server/          # Express Backend
│   ├── src/
│   │   └── index.ts
│   ├── tsconfig.json
│   └── package.json
├── shared/          # Gemeinsame TypeScript-Typen
│   ├── src/
│   │   ├── types.ts
│   │   └── index.ts
│   └── package.json
├── package.json     # Root Workspace
├── turbo.json       # TurboRepo Config
└── README.md
```

## 🛠️ Tech Stack

### Client
- **Vue 3** (neueste Version) - Progressive JavaScript Framework
- **Vite** (neueste Version) - Next Generation Frontend Tooling
- **TypeScript** - Type-safe Development
- **Tailwind CSS** - Utility-first CSS Framework

### Server
- **Node.js 23** (neueste LTS)
- **Express** (neueste Version) - Web Framework
- **TypeScript** - Type-safe Backend
- **tsx** - TypeScript Execution & Watch Mode

### Shared
- **TypeScript** - Gemeinsame Typen/Interfaces für API und Datenmodelle

### Monorepo Tooling
- **npm Workspaces** - Package Management
- **TurboRepo** - High-performance Build System

## 🚀 Schnellstart

### Voraussetzungen
- Node.js 20.19+ oder 22.12+ (empfohlen: v23)
- npm 10+

### Installation

```bash
# Alle Abhängigkeiten installieren
npm install

# Optional: Installiere Abhängigkeiten für einzelne Packages
npm install --prefix client
npm install --prefix server
npm install --prefix shared
```

### Development

```bash
# Alle Packages im Dev-Modus starten
npm run dev

# Nur Client (Port 3000)
npm run dev --prefix client

# Nur Server (Port 3001)
npm run dev --prefix server

# Shared Types im Watch-Modus
npm run dev --prefix shared
```

### Build

```bash
# Alle Packages builden
npm run build

# Einzelne Packages builden
npm run build --prefix client
npm run build --prefix server
npm run build --prefix shared
```

## 🌐 Deployment

### Client (Frontend)
**Empfohlen: Vercel oder Netlify**

#### Vercel
```bash
cd client
npm run build
# Verbinde Vercel CLI und deploye
vercel --prod
```

#### Netlify
```bash
cd client
npm run build
# dist/ Ordner auf Netlify hochladen
```

### Server (Backend)
**Empfohlen: Railway oder Render**

#### Railway
1. Erstelle neues Projekt auf [Railway](https://railway.app)
2. Verbinde GitHub Repository
3. Setze Root Directory auf `server`
4. Environment Variables konfigurieren
5. Deploy

#### Render
1. Erstelle neuen Web Service auf [Render](https://render.com)
2. Verbinde GitHub Repository
3. Build Command: `npm install --prefix server && npm run build --prefix server`
4. Start Command: `npm start --prefix server`
5. Environment Variables konfigurieren

## 🔐 Environment Variables

Erstelle eine `.env` Datei im `server/` Ordner (siehe `.env.example`):

```env
PORT=3001
NODE_ENV=development

# Spotify API (optional)
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret

# YouTube API (optional)
YOUTUBE_API_KEY=your_api_key

# News API (optional - für Skandal-Recherche)
NEWS_API_KEY=your_api_key
```

## 📝 Nächste Schritte

### Zu implementieren:
1. **Spotify API Integration**
   - OAuth 2.0 Authentication
   - Playlist Tracks abrufen
   - Artist Informationen extrahieren

2. **YouTube API Integration**
   - API Key Authentication
   - Playlist Items abrufen
   - Video Details & Channel-Infos

3. **Skandal-Datenbank**
   - Wikipedia API Integration
   - News API Integration
   - Eigene Datenbank mit Prisma ORM (optional)

4. **UI/UX Verbesserungen**
   - Artist Cards mit Bildern
   - Loading States
   - Error Handling
   - Responsive Design

## 📚 Dokumentation

- [Vue 3 Docs](https://vuejs.org/)
- [Vite Docs](https://vitejs.dev/)
- [Express Docs](https://expressjs.com/)
- [TailwindCSS Docs](https://tailwindcss.com/)
- [TurboRepo Docs](https://turbo.build/)

## 📄 Lizenz

MIT License - siehe [LICENSE](LICENSE) Datei

## 👨‍💻 Entwickler

dstN - [GitHub](https://github.com/dstN)

