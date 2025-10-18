import fetch from 'node-fetch'

const DEFAULT_ALLOWED_DOMAINS = [
  'bbc.co.uk', 'bbc.com', 'nytimes.com', 'theguardian.com', 'reuters.com', 'apnews.com', 'npr.org',
  'washingtonpost.com', 'wsj.com', 'theatlantic.com', 'cnn.com', 'nbcnews.com', 'cbsnews.com',
  'abcnews.go.com', 'news.sky.com', 'aljazeera.com', 'time.com', 'bloomberg.com',
  'rollingstone.com', 'billboard.com', 'variety.com', 'hollywoodreporter.com', 'pitchfork.com', 'nme.com',
  'latimes.com', 'chicagotribune.com', 'usatoday.com',
  // pragmatic additions seen in results for artists/celebs
  'vox.com', 'itv.com', 'indianexpress.com', 'people.com', 'telegraph.co.uk', 'guardian.co.uk', 'sky.com'
]

const STRONG_KEYWORDS = [
  'arrest', 'arrested', 'charge', 'charged', 'convict', 'convicted', 'lawsuit', 'indicted', 'sentence', 'sentenced',
  'assault', 'rape', 'domestic violence', 'sexual assault', 'sexual misconduct', 'sexual harassment', 'misconduct',
  'battery', 'felony', 'misdemeanor', 'restraining order', 'probation', 'plea deal', 'court', 'trial'
]

// Filter out low-signal formats like listicles/explainers/timelines
const NEGATIVE_TITLE_PATTERNS: RegExp[] = [
  /timeline/i,
  /everything (we|you) know/i,
  /what to know/i,
  /explained/i,
  /who is/i,
  /bio(graphy)?/i,
  /facts? to know/i,
  /all (about|you need)/i,
]

function parseAllowedDomains(): string[] {
  const env = process.env.NEWS_ALLOWED_DOMAINS
  if (!env) return DEFAULT_ALLOWED_DOMAINS
  return env.split(',').map(s => s.trim().toLowerCase()).filter(Boolean)
}

function hostname(url: string): string | null {
  try {
    return new URL(url).hostname.replace(/^www\./, '').toLowerCase()
  } catch {
    return null
  }
}

function matchesStrongKeywords(text?: string): boolean {
  const t = `${text || ''}`.toLowerCase()
  return STRONG_KEYWORDS.some(k => t.includes(k))
}

// Minimal HTML parsing helpers
function extractAll(regex: RegExp, text: string): string[] {
  const out: string[] = []
  let m: RegExpExecArray | null
  while ((m = regex.exec(text)) !== null) {
    if (m[1]) out.push(m[1])
  }
  return out
}

export async function getFallbackSnippets(artistName: string): Promise<{ title: string; description: string; url: string }[]> {
  const allowed = parseAllowedDomains()
  const q = `${artistName} (arrested OR charged OR convicted OR lawsuit OR plea OR sentenced OR controversy OR domestic violence OR assault)`
  const url = `https://html.duckduckgo.com/html/?q=${encodeURIComponent(q)}&kl=us-en`
  // Setup 20s timeout
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 20000)
  const res = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36',
      'Accept-Language': 'en-US,en;q=0.9',
    },
    signal: controller.signal,
  }).catch((e) => {
    console.log('[fallback] fetch error:', e?.message || e)
    throw e
  })
  clearTimeout(timeout)
  const html = await res.text()

  // DuckDuckGo HTML: results are in <a class="result__a" href="...">Title</a>
  const linkRegex = /<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)<\/a>/gi
  const descRegex = /<a[^>]*class="result__snippet"[^>]*>(.*?)<\/a>|<div class="result__snippet">([\s\S]*?)<\/div>/gi

  const links: Array<{ url: string; title: string }> = []
  let match: RegExpExecArray | null
  const decodeDuckDuckGo = (href: string): string => {
    try {
      const u = new URL(href, 'https://duckduckgo.com')
      if (u.hostname.includes('duckduckgo.com')) {
        const uddg = u.searchParams.get('uddg')
        if (uddg) return decodeURIComponent(uddg)
      }
      return href
    } catch { return href }
  }

  while ((match = linkRegex.exec(html)) !== null) {
    const hrefRaw = match[1]
    const href = decodeDuckDuckGo(hrefRaw)
    // Decode HTML entities minimally
    const title = match[2]
      .replace(/<[^>]+>/g, '')
      .replace(/&amp;/g, '&')
      .replace(/&#x27;|&apos;/g, "'")
      .trim()
    links.push({ url: href, title })
    if (links.length >= 25) break
  }

  const descs = extractAll(descRegex, html).map(d => (d || '')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&#x27;|&apos;/g, "'")
    .trim())

  const results: { title: string; description: string; url: string }[] = []
  for (let i = 0; i < links.length; i++) {
    const { url, title } = links[i]
    const description = descs[i] || ''
    const host = hostname(url)
    if (!host || !allowed.some(d => host.endsWith(d))) continue
    if (NEGATIVE_TITLE_PATTERNS.some(r => r.test(title))) continue
    if (!matchesStrongKeywords(`${title} ${description}`)) continue
    results.push({ title, description, url })
    if (results.length >= 5) break
  }
  // relaxed second pass if nothing found: allow generic 'scandal/controversy' and widen domains slightly
  if (results.length === 0) {
    for (let i = 0; i < links.length; i++) {
      const { url, title } = links[i]
      const description = descs[i] || ''
      const host = hostname(url)
      if (!host) continue
      // allow if host in allowed OR is a well-known entertainment outlet
      const isKnown = allowed.some(d => host.endsWith(d)) || /\b(tmz|pagesix|eonline|etonline|insider|independent|mirror|metro)\./i.test(host)
      if (!isKnown) continue
      if (NEGATIVE_TITLE_PATTERNS.some(r => r.test(title))) continue
      const text = `${title} ${description}`.toLowerCase()
      if (!(text.includes('scandal') || text.includes('controvers') || matchesStrongKeywords(text))) continue
      results.push({ title, description, url })
      if (results.length >= 5) break
    }
  }
  // final ultra-relaxed pass (dev-friendly): return first 3 links regardless of domain if enabled
  const allowAny = (process.env.ALLOW_ANY_DOMAIN_WHEN_EMPTY || 'true').toLowerCase() === 'true'
  if (results.length === 0 && allowAny) {
    for (let i = 0; i < Math.min(links.length, 3); i++) {
      const { url, title } = links[i]
      const description = descs[i] || ''
      results.push({ title, description, url })
    }
  }
  return results
}
