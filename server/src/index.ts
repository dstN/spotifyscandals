import express from 'express'
import cors from 'cors'
import dotenv from 'dotenv'
import { getSpotifyAuthUrl, exchangeCodeForToken, getValidAccessToken, getTokenStatus } from './services/spotifyAuth'
import { flushCache, deleteCachedArtist, getCacheStats, transferCacheToDatabase, saveArtistWithScandals } from './services/db'

dotenv.config()

const app = express()
const PORT = process.env.PORT || 3001
const SPOTIFY_REDIRECT_URI = process.env.SPOTIFY_REDIRECT_URI

// Middleware
app.use(cors())
app.use(express.json())

// Routes
app.get('/api/health', (_req, res) => {
  res.json({ status: 'OK', message: 'Spotify Scandals API is running' })
})

// Spotify OAuth
app.get('/api/spotify/login', (_req, res) => {
  const clientId = process.env.SPOTIFY_CLIENT_ID
  if (!clientId) return res.status(500).send('Missing SPOTIFY_CLIENT_ID')
  if (!SPOTIFY_REDIRECT_URI) return res.status(500).send('Missing SPOTIFY_REDIRECT_URI (must be HTTPS and match Spotify Dashboard)')
  const scopes = ['playlist-read-private', 'playlist-read-collaborative']
  const state = Math.random().toString(36).slice(2)
  const url = getSpotifyAuthUrl(clientId, SPOTIFY_REDIRECT_URI as string, scopes, state)
  res.redirect(url)
})

app.get('/api/spotify/callback', async (req, res) => {
  const code = req.query.code as string | undefined
  const err = req.query.error as string | undefined
  console.log('Spotify callback query:', req.query)
  const clientId = process.env.SPOTIFY_CLIENT_ID
  const clientSecret = process.env.SPOTIFY_CLIENT_SECRET
  if (!clientId || !clientSecret) return res.status(500).send('Missing Spotify credentials')
  if (!SPOTIFY_REDIRECT_URI) return res.status(500).send('Missing SPOTIFY_REDIRECT_URI (must be HTTPS and match Spotify Dashboard)')
  if (err) return res.status(400).send(`Spotify auth error: ${err}`)
  if (!code) return res.status(400).send('Missing code')
  try {
  await exchangeCodeForToken(code, clientId, clientSecret, SPOTIFY_REDIRECT_URI as string)
    res.send('Spotify connected. You can close this tab and return to the app.')
  } catch (e: any) {
    res.status(500).send(`Spotify auth failed: ${e?.message || e}`)
  }
})

// Debug: return the constructed authorization URL instead of redirecting
app.get('/api/spotify/debug-login', (_req, res) => {
  const clientId = process.env.SPOTIFY_CLIENT_ID
  if (!clientId) return res.status(500).json({ error: 'Missing SPOTIFY_CLIENT_ID' })
  const scopes = ['playlist-read-private', 'playlist-read-collaborative']
  const state = Math.random().toString(36).slice(2)
  const url = getSpotifyAuthUrl(clientId, SPOTIFY_REDIRECT_URI as string, scopes, state)
  res.json({ url, redirectUri: SPOTIFY_REDIRECT_URI as string })
})

app.get('/api/spotify/status', (_req, res) => {
  res.json(getTokenStatus())
})

// Test-Endpunkt für Skandal-Recherche ohne Playlist
app.get('/api/test-scandal', async (req, res) => {
  try {
    const artistName = (req.query.artist as string) || 'Lostprophets'
    console.log(`[Test-Scandal] Suche für: ${artistName}`)
    
    const { getCachedArtist, setCachedArtist } = await import('./services/db')
    const { getWikipediaScandals } = await import('./services/wiki')
    const { getNewsSnippets } = await import('./services/news')
    const { getFallbackSnippets } = await import('./services/fallback')
  const { clusterArticlesWithAlternatives } = await import('./utils/dedupe')
    const newsApiKey = process.env.NEWS_API_KEY || ''
    
    // Cache prüfen
    let cache = await getCachedArtist(artistName)
    if (cache && cache.payload && typeof cache.payload === 'object' && 'scandals' in cache.payload) {
      const payload = cache.payload as { scandals: any[] }
      console.log(`[Test-Scandal] Aus Cache: ${payload.scandals.length} Skandale`)
      return res.json({ artist: artistName, scandals: payload.scandals, source: 'cache' })
    }
    
    // Start with News-API (more reliable)
    let scandals: any[] = []
    if (newsApiKey) {
      try {
        console.log(`  → News-API-Suche...`)
        const news = await getNewsSnippets(artistName, newsApiKey)
        console.log(`  ← News-API: ${news.length} Ergebnisse`)
        if (news.length) scandals.push(...news.map(n => ({ source: 'News', ...n })))
      } catch (e: any) {
        console.log(`  ✗ News-API-Fehler:`, e?.message || e)
      }
    }
    
    // Fallback (DuckDuckGo) wenn nötig
    if (scandals.length === 0) {
      try {
        console.log(`  → Fallback-Suche (DuckDuckGo HTML)...`)
        const fallback = await getFallbackSnippets(artistName)
        console.log(`  ← Fallback: ${fallback.length} Ergebnisse`)
        if (fallback.length) scandals.push(...fallback.map(f => ({ source: 'Fallback', ...f })))
      } catch (e: any) {
        console.log(`  ✗ Fallback-Fehler:`, e?.message || e)
      }
    }

    // Optional: Wikipedia (only if enabled)
    const useWiki = (process.env.WIKI_ENABLED || 'false').toLowerCase() === 'true'
    if (useWiki) {
      try {
        console.log(`  → Wikipedia-Suche...`)
        const wiki = await getWikipediaScandals(artistName)
        console.log(`  ← Wikipedia: ${wiki.length} Ergebnisse`)
        if (wiki.length) scandals.push(...wiki.map(w => ({ source: 'Wikipedia', text: w.text, url: w.url, title: w.pageTitle })))
      } catch (e: any) {
        console.log(`  ✗ Wikipedia-Fehler:`, e?.message || e)
      }
    }
    
    // Cross-source clustering: primary + alternatives per incident
    const clustered = clusterArticlesWithAlternatives(
      scandals.map(s => ({ title: s.title || s.text || '', description: s.description || s.text || '', url: s.url || s.sourceUrl || '', source: s.source })),
      artistName,
      4
    )
    scandals = clustered.map(c => ({
      title: c.primary.title,
      description: c.primary.description,
      url: c.primary.url,
      source: (c.primary as any).source,
      alternatives: c.alternatives.map(a => ({ title: a.title, url: a.url, source: (a as any).source }))
    }))

  console.log(`  → Gesamt: ${scandals.length} Skandale gefunden (nach Dedupe)`)
    await setCachedArtist(artistName, { scandals })
    
    // Save to main database
    if (scandals.length > 0) {
      console.log(`  💾 Saving to database...`)
          const saveResult = await saveArtistWithScandals({
        name: artistName,
            scandals: scandals.map((s: any, idx: number) => ({
          title: s.title || `${s.source} - Scandal`,
          description: s.text || s.description,
          // Use real URL from source
          sourceUrl: s.url 
            ? s.url 
            : s.sourceUrl 
              ? s.sourceUrl
              : `${s.source}://scandal/${encodeURIComponent(artistName)}/${idx}`,
          sourceName: s.source,
              altSources: Array.isArray(s.alternatives) ? s.alternatives : [],
          date: s.publishedAt ? new Date(s.publishedAt) : undefined,
        })),
      })
      if (saveResult.success) {
        console.log(`  ✅ Database: ${saveResult.scandalsAdded} new scandal(s) saved`)
      } else {
        console.log(`  ⚠️  Database save failed:`, saveResult.error)
      }
    }
    
    res.json({ artist: artistName, scandals, source: 'fresh' })
  } catch (error) {
    console.error('[Test-Scandal] Fehler:', error)
    res.status(500).json({ error: 'Internal server error' })
  }
})

app.post('/api/analyze', async (req, res) => {
  try {
    const { playlistUrl } = req.body

    if (!playlistUrl) {
      return res.status(400).json({ error: 'Playlist URL is required' })
    }

  let artists: { name: string; scandals: any[] }[] = []
    if (playlistUrl.includes('spotify.com')) {
      // Spotify
      const { parseSpotifyPlaylistId } = await import('./utils/spotifyParser')
      const playlistId = parseSpotifyPlaylistId(playlistUrl)
      if (!playlistId) {
        return res.status(400).json({ error: 'Invalid Spotify playlist URL' })
      }
      const clientId = process.env.SPOTIFY_CLIENT_ID
      const clientSecret = process.env.SPOTIFY_CLIENT_SECRET
      if (!clientId || !clientSecret) {
        return res.status(500).json({ error: 'Spotify API credentials missing in .env' })
      }
      const { getSpotifyAccessToken, getSpotifyPlaylistTracks } = await import('./services/spotify')
      // Prefer user token if available; fallback to client credentials
      const userToken = await getValidAccessToken(clientId, clientSecret)
      const accessToken = userToken || await getSpotifyAccessToken(clientId, clientSecret)
      const tracks = await getSpotifyPlaylistTracks(playlistId, accessToken)
  // Logging entfernt: Spotify API tracks response
  const artistsMap: Record<string, { name: string; scandals: any[] }> = {}
      for (const item of tracks) {
        const trackArtists = item.track?.artists || []
        for (const artist of trackArtists) {
          if (!artistsMap[artist.name]) {
            artistsMap[artist.name] = { name: artist.name, scandals: [] }
          }
        }
      }
      // Skandal-Recherche und Caching
      const { getCachedArtist, setCachedArtist } = await import('./services/db')
  const { getWikipediaScandals } = await import('./services/wiki')
  const { getNewsSnippets } = await import('./services/news')
  const { getFallbackSnippets } = await import('./services/fallback')
  const { clusterArticlesWithAlternatives } = await import('./utils/dedupe')
      const newsApiKey = process.env.NEWS_API_KEY || ''
  // DEV: Nur den ersten Artist testen
  const devArtists = Object.values(artistsMap).slice(0, 1)
  for (const artist of devArtists) {
    console.log(`[Scandal-Check] Suche für Artist: ${artist.name}`)
        // Cache prüfen
        let cache = await getCachedArtist(artist.name)
        if (cache && cache.payload && typeof cache.payload === 'object' && 'scandals' in cache.payload) {
          const payload = cache.payload as { scandals: any[] }
          artist.scandals = payload.scandals
          continue
        }
        // Start with News-API first
        let scandals: any[] = []
        if (newsApiKey) {
          try {
            console.log(`  → News-API-Suche...`)
            const news = await getNewsSnippets(artist.name, newsApiKey)
            console.log(`  ← News-API: ${news.length} Ergebnisse`)
            if (news.length) scandals.push(...news.map(n => ({ source: 'News', ...n })))
          } catch (e: any) {
            console.log(`  ✗ News-API-Fehler:`, e?.message || e)
          }
        }
        // Fallback (nur wenn noch keine Skandale)
        if (scandals.length === 0) {
          try {
            console.log(`  → Fallback-Suche (DuckDuckGo HTML)...`)
            const fallback = await getFallbackSnippets(artist.name)
            console.log(`  ← Fallback: ${fallback.length} Ergebnisse`)
            if (fallback.length) scandals.push(...fallback.map(f => ({ source: 'Fallback', ...f })))
          } catch (e: any) {
            console.log(`  ✗ Fallback-Fehler:`, e?.message || e)
          }
        }
        // Optional: Wikipedia zuletzt
        const useWiki = (process.env.WIKI_ENABLED || 'false').toLowerCase() === 'true'
        if (useWiki) {
          try {
            console.log(`  → Wikipedia-Suche...`)
            const wiki = await getWikipediaScandals(artist.name)
            console.log(`  ← Wikipedia: ${wiki.length} Ergebnisse`)
            if (wiki.length) scandals.push(...wiki.map(w => ({ source: 'Wikipedia', text: w.text, url: w.url, title: w.pageTitle })))
          } catch (e: any) {
            console.log(`  ✗ Wikipedia-Fehler:`, e?.message || e)
          }
        }
        // Cross-source clustering with alternatives
        const clustered = clusterArticlesWithAlternatives(
          scandals.map(s => ({ title: s.title || s.text || '', description: s.description || s.text || '', url: s.url || s.sourceUrl || '', source: s.source })),
          artist.name,
          4
        )
        artist.scandals = clustered.map(c => ({
          title: c.primary.title,
          description: c.primary.description,
          url: c.primary.url,
          source: (c.primary as any).source,
          alternatives: c.alternatives.map(a => ({ title: a.title, url: a.url, source: (a as any).source }))
        }))
        console.log(`  → Gesamt: ${artist.scandals.length} Skandale gefunden (nach Clustering)`)        
        await setCachedArtist(artist.name, { scandals: artist.scandals })
        
        // Save to main database immediately if scandals found
        if (scandals.length > 0) {
          console.log(`  💾 Saving to database...`)
          const saveResult = await saveArtistWithScandals({
            name: artist.name,
            scandals: artist.scandals.map((s: any, idx: number) => ({
              title: s.title || `${s.source} - Scandal`,
              description: s.text || s.description,
              // Use real URL from source
              sourceUrl: s.url 
                ? s.url 
                : s.sourceUrl 
                  ? s.sourceUrl
                  : `${s.source}://scandal/${encodeURIComponent(artist.name)}/${idx}`,
              sourceName: s.source,
              altSources: Array.isArray(s.alternatives) ? s.alternatives : [],
              date: s.publishedAt ? new Date(s.publishedAt) : undefined,
            })),
          })
          if (saveResult.success) {
            console.log(`  ✅ Database: ${saveResult.scandalsAdded} new scandal(s) saved`)
          } else {
            console.log(`  ⚠️  Database save failed:`, saveResult.error)
          }
        }
      }
      artists = Object.values(artistsMap)
    } else if (playlistUrl.includes('youtube.com')) {
      // YouTube
      const { parseYouTubePlaylistId } = await import('./utils/youtubeParser')
      const playlistId = parseYouTubePlaylistId(playlistUrl)
      if (!playlistId) {
        return res.status(400).json({ error: 'Invalid YouTube playlist URL' })
      }
      // Mock: Use static artists
      const { getYouTubePlaylistItems } = await import('./services/youtube')
      const apiKey = process.env.YOUTUBE_API_KEY || ''
      const tracks = await getYouTubePlaylistItems(playlistId, apiKey)
      const artistsMap: Record<string, { name: string; scandals: string[] }> = {}
      for (const item of tracks) {
        const trackArtists = item.track?.artists || []
        for (const artist of trackArtists) {
          if (!artistsMap[artist.name]) {
            artistsMap[artist.name] = { name: artist.name, scandals: [] }
          }
        }
      }
      artists = Object.values(artistsMap)
    } else {
      return res.status(400).json({ error: 'Unsupported playlist URL. Only Spotify and YouTube are supported.' })
    }
    res.json({ artists })
  } catch (error) {
    console.error('Error analyzing playlist:', error)
    res.status(500).json({ error: 'Internal server error' })
  }
})

// Cache Management Endpoints
app.get('/api/cache/stats', async (_req, res) => {
  const stats = await getCacheStats()
  res.json(stats)
})

app.post('/api/cache/transfer', async (req, res) => {
  const flushAfter = req.query.flush === 'true' || req.body.flush === true
  console.log(`📦 Transferring cache to main database (flush after: ${flushAfter})...`)
  const result = await transferCacheToDatabase(flushAfter)
  console.log(`✅ Transfer complete: ${result.transferred}/${result.total} artists saved`)
  res.json(result)
})

app.delete('/api/cache/flush', async (_req, res) => {
  console.log('🗑️ Flushing entire cache...')
  const result = await flushCache()
  console.log(`✅ Cache flushed: ${result.count} entries deleted`)
  res.json(result)
})

app.delete('/api/cache/artist/:name', async (req, res) => {
  const artistName = req.params.name
  console.log(`🗑️ Deleting cache for artist: ${artistName}`)
  const result = await deleteCachedArtist(artistName)
  res.json(result)
})

app.listen(PORT, () => {
  console.log(`🚀 Server running on http://localhost:${PORT}`)
})
