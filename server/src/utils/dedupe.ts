export type Article = { title: string; description?: string; url: string }

const DOMAIN_PRIORITY: Record<string, number> = {
  'reuters.com': 100,
  'apnews.com': 95,
  'bbc.com': 90,
  'bbc.co.uk': 90,
  'nytimes.com': 90,
  'theguardian.com': 85,
  'washingtonpost.com': 85,
  'wsj.com': 85,
  'bloomberg.com': 80,
  'npr.org': 80,
  'cnn.com': 70,
  'abcnews.go.com': 70,
  'cbsnews.com': 70,
  'nbcnews.com': 70,
  'rollingstone.com': 70,
  'billboard.com': 65,
  'variety.com': 65,
  'hollywoodreporter.com': 65,
  'latimes.com': 65,
  'usatoday.com': 60,
  'vox.com': 55,
  'people.com': 55,
}

function hostname(u: string): string | null {
  try {
    return new URL(u).hostname.replace(/^www\./, '').toLowerCase()
  } catch {
    return null
  }
}

function normalizeTitle(t?: string): string {
  return (t || '')
    .toLowerCase()
    .replace(/&#x27;|&apos;/g, "'")
    .replace(/&amp;/g, '&')
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function tokens(t: string, artistName?: string): Set<string> {
  const stop = new Set([
    'the','a','an','and','or','of','in','to','for','on','with','by','at','from','case','set','date','trial','news','ap','uk','us','usa','today','update','report','breaking'
  ])
  const artistTokens = (artistName || '')
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
  artistTokens.forEach(t => stop.add(t))

  const arr = normalizeTitle(t)
    .split(' ')
    .filter(w => w.length >= 3 && !stop.has(w))
  return new Set(arr)
}

function jaccard(a: Set<string>, b: Set<string>): number {
  const inter = new Set([...a].filter(x => b.has(x)))
  const union = new Set([...a, ...b])
  return union.size === 0 ? 0 : inter.size / union.size
}

export function dedupeArticles(input: Article[], artistName?: string): Article[] {
  const clusters: { rep: Article; repTokens: Set<string>; items: Article[] }[] = []
  const THRESH = 0.55

  for (const art of input) {
    const tok = tokens(art.title, artistName)
    let placed = false
    for (const c of clusters) {
      const sim = jaccard(tok, c.repTokens)
      if (sim >= THRESH) {
        c.items.push(art)
        placed = true
        break
      }
    }
    if (!placed) clusters.push({ rep: art, repTokens: tok, items: [art] })
  }

  const pickBest = (items: Article[]): Article => {
    let best = items[0]
    let bestScore = -1
    for (const it of items) {
      const host = hostname(it.url) || ''
      const score = (DOMAIN_PRIORITY[host] || 10) + Math.max(0, 50 - normalizeTitle(it.title).length)
      if (score > bestScore) {
        best = it
        bestScore = score
      }
    }
    return best
  }

  const out: Article[] = clusters.map(c => pickBest(c.items))
  // keep output small and relevant
  return out.slice(0, 5)
}

export function dedupeGeneric<T extends Article>(input: T[], artistName?: string): T[] {
  const clusters: { rep: T; repTokens: Set<string>; items: T[] }[] = []
  const THRESH = 0.55
  for (const it of input) {
    const tok = tokens(it.title, artistName)
    let placed = false
    for (const c of clusters) {
      const sim = jaccard(tok, c.repTokens)
      if (sim >= THRESH) {
        c.items.push(it)
        placed = true
        break
      }
    }
    if (!placed) clusters.push({ rep: it, repTokens: tok, items: [it] })
  }
  const pickBest = (items: T[]): T => {
    let best = items[0]
    let bestScore = -1
    for (const it of items) {
      const host = hostname(it.url) || ''
      const score = (DOMAIN_PRIORITY[host] || 10) + Math.max(0, 50 - normalizeTitle(it.title).length)
      if (score > bestScore) {
        best = it
        bestScore = score
      }
    }
    return best
  }
  return clusters.map(c => pickBest(c.items)).slice(0, 5)
}

function qualityScore<T extends Article>(it: T): number {
  const host = hostname(it.url) || ''
  return (DOMAIN_PRIORITY[host] || 10) + Math.max(0, 50 - normalizeTitle(it.title).length)
}

export function clusterArticlesWithAlternatives<T extends Article>(input: T[], artistName?: string, maxAlternatives = 4): Array<{ primary: T; alternatives: T[] }> {
  const clusters: { repTokens: Set<string>; items: T[] }[] = []
  const THRESH = 0.55
  for (const it of input) {
    const tok = tokens(it.title, artistName)
    let placed = false
    for (const c of clusters) {
      const sim = jaccard(tok, c.repTokens)
      if (sim >= THRESH) {
        c.items.push(it)
        placed = true
        break
      }
    }
    if (!placed) clusters.push({ repTokens: tok, items: [it] })
  }
  return clusters.map(c => {
    const sorted = [...c.items].sort((a, b) => qualityScore(b) - qualityScore(a))
    const primary = sorted[0]
    const alternatives = sorted.slice(1, 1 + maxAlternatives)
    return { primary, alternatives }
  })
}
