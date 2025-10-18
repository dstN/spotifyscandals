import fetch from 'node-fetch'
import { dedupeGeneric } from '../utils/dedupe'

type NewsApiResponse = { articles?: { title: string; description: string; url: string }[] }

const DEFAULT_ALLOWED_DOMAINS = [
  'bbc.co.uk', 'bbc.com', 'nytimes.com', 'theguardian.com', 'reuters.com', 'apnews.com', 'npr.org',
  'washingtonpost.com', 'wsj.com', 'theatlantic.com', 'cnn.com', 'nbcnews.com', 'cbsnews.com',
  'abcnews.go.com', 'news.sky.com', 'aljazeera.com', 'time.com', 'bloomberg.com',
  'rollingstone.com', 'billboard.com', 'variety.com', 'hollywoodreporter.com', 'pitchfork.com', 'nme.com',
  'latimes.com', 'chicagotribune.com', 'usatoday.com'
]

const STRONG_KEYWORDS = [
  'arrest', 'arrested', 'charge', 'charged', 'convict', 'convicted', 'lawsuit', 'indicted', 'sentence', 'sentenced',
  'assault', 'rape', 'domestic violence', 'sexual assault', 'sexual misconduct', 'sexual harassment', 'misconduct',
  'battery', 'felony', 'misdemeanor', 'restraining order', 'probation', 'plea deal', 'court', 'trial'
]

const GENERIC_KEYWORDS = [
  'scandal', 'controversy', 'allegation', 'allegations', 'accusation', 'accusations', 'ban', 'backlash'
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

function matchesKeywords(title?: string, description?: string): boolean {
  const text = `${title || ''} ${description || ''}`.toLowerCase()
  const hasStrong = STRONG_KEYWORDS.some(k => text.includes(k))
  const hasGeneric = GENERIC_KEYWORDS.some(k => text.includes(k))
  return hasStrong || hasGeneric
}

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

export async function getNewsSnippets(artistName: string, apiKey: string): Promise<{ title: string; description: string; url: string }[]> {
  if (!apiKey) return []
  const allowed = parseAllowedDomains()
  // Focus query on scandals with stronger terms for better precision
  const query = `${artistName} (arrested OR charged OR convicted OR lawsuit OR scandal OR controversy OR allegations)`
  const url = `https://newsapi.org/v2/everything?q=${encodeURIComponent(query)}&language=en&sortBy=relevancy&pageSize=50&apiKey=${apiKey}`
  const res = await fetch(url)
  const data = (await res.json()) as NewsApiResponse
  if (!data.articles) return []

  const unique = new Map<string, { title: string; description: string; url: string }>()
  for (const a of data.articles) {
    if (!a?.url) continue
    const host = hostname(a.url)
    if (!host || !allowed.some(d => host.endsWith(d))) continue
    if (!matchesKeywords(a.title, a.description)) continue
    if (NEGATIVE_TITLE_PATTERNS.some(r => r.test(a.title || ''))) continue
    unique.set(a.url, { title: a.title, description: a.description, url: a.url })
    if (unique.size >= 10) break
  }

  const arr = Array.from(unique.values()).map(a => ({ ...a, description: a.description || '' }))
  // extra clustering to collapse near-duplicates across outlets
  const clustered = dedupeGeneric(arr, artistName)
  return clustered.map(a => ({ title: a.title, description: a.description || '', url: a.url }))
}
