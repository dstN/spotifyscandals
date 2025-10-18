import fetch from 'node-fetch'

type WikiSearchResponse = { query?: { search?: { title: string }[] } }
type WikiPageResponse = { 
  query?: { 
    pages?: Record<string, { 
      extract?: string
      revisions?: { slots?: { main?: { '*'?: string } } }[]
      categories?: { title: string }[] 
    }> 
  } 
}

export interface WikiScandal {
  text: string
  url: string
  pageTitle: string
  citations?: string[] // Primary source URLs from Wikipedia references
  section?: string
}

export async function getWikipediaScandals(artistName: string): Promise<WikiScandal[]> {
  // Wikipedia API: Search for artist page (English only)
  const searchUrl = `https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=${encodeURIComponent(artistName)}&format=json`
  const searchRes = await fetch(searchUrl)
  const searchData = (await searchRes.json()) as WikiSearchResponse
  const pageTitle = searchData.query?.search?.[0]?.title
  if (!pageTitle) return []

  // Validate: Check if the page title is similar to the artist name
  const titleLower = pageTitle.toLowerCase()
  const artistLower = artistName.toLowerCase()
  const similarity = titleLower.includes(artistLower) || artistLower.includes(titleLower)
  if (!similarity) {
    console.log(`    [Wikipedia] Page title "${pageTitle}" doesn't match artist "${artistName}" - skipping`)
    return []
  }

  // Get page content, wikitext (for refs), and categories
  const pageUrl = `https://en.wikipedia.org/w/api.php?action=query&prop=extracts|revisions|categories&explaintext=true&rvprop=content&rvslots=main&titles=${encodeURIComponent(pageTitle)}&format=json`
  const pageRes = await fetch(pageUrl)
  const pageData = (await pageRes.json()) as WikiPageResponse
  const pages = pageData.query?.pages || {}
  const first = Object.values(pages)[0]
  const extract = first?.extract
  const wikitext = first?.revisions?.[0]?.slots?.main?.['*'] || ''
  const categories = first?.categories || []
  
  if (!extract) return []

  // Validate: Check if the page is about music/musicians
  const musicCategories = ['music', 'musician', 'band', 'singer', 'artist', 'album', 'song', 'record']
  const hasMusic = categories.some(cat => 
    musicCategories.some(keyword => cat.title.toLowerCase().includes(keyword))
  )
  
  if (!hasMusic) {
    console.log(`    [Wikipedia] Page "${pageTitle}" is not about music - skipping`)
    return []
  }

  // Build Wikipedia page URL
  const wikiUrl = `https://en.wikipedia.org/wiki/${encodeURIComponent(pageTitle.replace(/ /g, '_'))}`

  // Helper: slug for section anchor
  const sectionAnchor = (title: string) => `#${encodeURIComponent(title.trim().replace(/\s+/g, '_'))}`

  // Extract references/citations from wikitext
  // Format: <ref>URL</ref> or <ref name="...">URL</ref> or {{cite web|url=URL}}
  const extractCitations = (text: string): string[] => {
    const citations: string[] = []
    
    // Match <ref>...</ref> tags
    const refMatches = text.match(/<ref[^>]*>([\s\S]*?)<\/ref>/gi) || []
    for (const ref of refMatches) {
      // Extract URLs from ref content
      const urlMatches = ref.match(/https?:\/\/[^\s<>\]]+/gi) || []
      citations.push(...urlMatches)
    }
    
    // Match {{cite web|url=...}} templates
    const citeMatches = text.match(/\{\{cite[^}]*\|url\s*=\s*([^\s|}\]]+)/gi) || []
    for (const cite of citeMatches) {
      const urlMatch = cite.match(/url\s*=\s*([^\s|}\]]+)/)
      if (urlMatch) citations.push(urlMatch[1])
    }
    
    // Clean up URLs (remove trailing punctuation)
    return [...new Set(citations)]
      .map(url => url.replace(/[,;.!?)\]]+$/, ''))
      .filter(url => url.startsWith('http'))
      .slice(0, 3) // Max 3 per scandal
  }

  // Search for scandal-related sections in wikitext directly
  const scandalKeywords = [
    'scandal', 'controversy', 'lawsuit', 'allegation', 'affair', 'criticism', 'convicted', 
    'court', 'trial', 'abuse', 'drugs', 'arrested', 'detention', 'police', 'crime', 
    'criminal', 'charged', 'indicted', 'sentenced', 'guilty', 'assault', 'rape', 
    'sexual', 'misconduct', 'accusation', 'domestic violence', 'harassment', 'fraud'
  ]

  const strongKeywords = [
    'arrested', 'charged', 'convicted', 'pleaded guilty', 'pled guilty', 'lawsuit', 'indicted', 'sentenced',
    'assault', 'rape', 'domestic violence', 'sexual assault', 'sexual misconduct', 'sexual harassment', 'misconduct',
    'battery', 'felony', 'misdemeanor', 'restraining order', 'probation', 'plea deal', 'court', 'trial'
  ]

  const negativeNoise = [
    'King of R&B', 'Billboard', 'chart', 'album', 'single', 'tour', 'award', 'Grammy', 'Hot 100', 'sales',
    'record', 'best-selling', 'top 40', 'RIAA', 'stream', 'concert', 'ticket', 'box office'
  ]

  // Parse sections from wikitext: == Section ==
  const sectionHeaderRegex = /^={2,6}\s*(.*?)\s*={2,6}\s*$/gm
  const sectionMatches = [...wikitext.matchAll(sectionHeaderRegex)]
  type Sec = { title: string; content: string }
  const sections: Sec[] = []
  if (sectionMatches.length > 0) {
    for (let i = 0; i < sectionMatches.length; i++) {
      const m = sectionMatches[i]
      const title = m[1].trim()
      const start = m.index! + m[0].length
      const end = i + 1 < sectionMatches.length ? sectionMatches[i + 1].index! : wikitext.length
      const content = wikitext.slice(start, end)
      sections.push({ title, content })
    }
  } else {
    sections.push({ title: 'Overview', content: wikitext })
  }

  // Relevant sections by title
  const relevantSectionTitle = (t: string) => [
    /controvers(y|ies)/i,
    /legal\s+issues?/i,
    /allegations?/i,
    /accusations?/i,
    /arrests?/i,
    /charges?/i,
    /convictions?/i,
    /lawsuits?/i,
    /domestic\s+violence/i,
    /sexual\s+(misconduct|assault|harassment)/i,
    /criticism/i,
  ].some(r => r.test(t))
  
  // Parse wikitext for scandal sentences with their refs
  const scandalMatches: Array<{ text: string; citations: string[]; section?: string }> = []

  const candidateSections = sections.filter(s => relevantSectionTitle(s.title) || strongKeywords.some(k => s.content.toLowerCase().includes(k)))

  for (const sec of candidateSections) {
    // Split content into sentences (rough approach)
    const rawSentences = sec.content.replace(/\n+/g, ' ').split(/(?<=[.!?])\s+/)
    for (const sentence of rawSentences) {
      const lower = sentence.toLowerCase()
      const hasStrong = strongKeywords.some(k => lower.includes(k))
      const hasScandal = hasStrong || scandalKeywords.some(k => lower.includes(k))
      const hasNoise = negativeNoise.some(n => sentence.includes(n))

      if (!hasScandal || hasNoise) continue

      const cleaned = sentence
        .replace(/<ref[^>]*>[\s\S]*?<\/ref>/gi, '')
        .replace(/\[\[([^\]|]+)(\|[^\]]+)?\]\]/g, '$1')
        .replace(/'{2,}/g, '')
        .replace(/\{\{[^}]+\}\}/g, '')
        .trim()

      if (cleaned.length < 40) continue

      // Require citations from the sentence; if none, try nearby context
      let citations = extractCitations(sentence)
      if (citations.length === 0) {
        // try up to 300 chars following
        const idx = sec.content.indexOf(sentence)
        if (idx > -1) {
          const context = sec.content.slice(idx, Math.min(sec.content.length, idx + sentence.length + 300))
          citations = extractCitations(context)
        }
      }

      // Prefer sentences that actually have citations
      if (citations.length === 0 && !hasStrong) continue

      scandalMatches.push({ text: cleaned, citations, section: sec.title })
      if (scandalMatches.length >= 5) break
    }
    if (scandalMatches.length >= 5) break
  }
  
  // If no wikitext scandals found, use plain text extract as fallback
  if (scandalMatches.length === 0) {
    const scandalSentences = extract
      .split(/\n|\. /)
      .filter(s => scandalKeywords.some(k => s.toLowerCase().includes(k.toLowerCase())))
      .slice(0, 5)
    
    return scandalSentences.map(text => ({
      text,
      url: `${wikiUrl}#Controversies`,
      pageTitle,
      citations: undefined,
      section: 'Controversies'
    }))
  }
  
  // Return scandals with real citations
  return scandalMatches.map(({ text, citations, section }) => {
    const primaryUrl = citations.length > 0 
      ? citations[0] 
      : `${wikiUrl}${section ? sectionAnchor(section) : '#Controversies'}`
    
    return {
      text,
      url: primaryUrl,
      pageTitle,
      citations: citations.length > 0 ? citations : undefined,
      section
    }
  })
}
