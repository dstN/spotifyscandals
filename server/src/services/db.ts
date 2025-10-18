import { PrismaClient } from '@prisma/client'

export const prisma = new PrismaClient()

// Default cache TTL in days (configurable via env)
const DEFAULT_CACHE_TTL_DAYS = parseInt(process.env.CACHE_TTL_DAYS || '14', 10)

export async function getCachedArtist(name: string, ignoreExpired = false) {
  try {
  const cache: any = await prisma.cacheEntry.findUnique({ where: { artistName: name } })
    
    if (!cache) return null
    
    // Check if cache is expired
  if (!ignoreExpired && cache.expiresAt && cache.expiresAt < new Date()) {
      console.log(`  ⏰ Cache expired for ${name} (age: ${Math.floor((Date.now() - cache.expiresAt.getTime()) / (1000 * 60 * 60 * 24))} days old)`)
      return null // Treat as cache miss
    }
    
    return cache
  } catch {
    return null
  }
}

export async function setCachedArtist(name: string, payload: unknown, ttlDays = DEFAULT_CACHE_TTL_DAYS) {
  try {
    const expiresAt = new Date()
    expiresAt.setDate(expiresAt.getDate() + ttlDays)
    
    const args: any = {
      where: { artistName: name },
      update: { 
        payload: payload as any,
        expiresAt,
      },
      create: { 
        artistName: name, 
        payload: payload as any,
        expiresAt,
      },
    }
    return await prisma.cacheEntry.upsert(args)
  } catch {
    return null
  }
}

export async function flushCache() {
  try {
    const result = await prisma.cacheEntry.deleteMany({})
    return { success: true, count: result.count }
  } catch (error) {
    return { success: false, error: String(error) }
  }
}

export async function deleteCachedArtist(name: string) {
  try {
    await prisma.cacheEntry.delete({ where: { artistName: name } })
    return { success: true }
  } catch (error) {
    return { success: false, error: String(error) }
  }
}

export async function getCacheStats() {
  try {
    const total = await prisma.cacheEntry.count()
    const entries = await prisma.cacheEntry.findMany({
      select: {
        artistName: true,
        createdAt: true,
        updatedAt: true,
      },
      orderBy: { updatedAt: 'desc' },
      take: 10,
    })
    return { success: true, total, recentEntries: entries }
  } catch (error) {
    return { success: false, error: String(error) }
  }
}

// Save artist with scandals to main database
export async function saveArtistWithScandals(artistData: {
  name: string
  imageUrl?: string
  genres?: string[]
  scandals: Array<{
    title: string
    description?: string
    sourceUrl: string
    sourceName?: string
    date?: Date
    altSources?: Array<{ title: string; url: string; source?: string }>
  }>
}) {
  try {
    // Create or update artist
    const artist = await prisma.artist.upsert({
      where: { name: artistData.name },
      update: {
        imageUrl: artistData.imageUrl,
        genres: artistData.genres || [],
      },
      create: {
        name: artistData.name,
        imageUrl: artistData.imageUrl,
        genres: artistData.genres || [],
      },
    })

    // Save scandals (only new ones, skip duplicates by sourceUrl)
    const savedScandals = []
  for (const scandal of artistData.scandals) {
      // Check if scandal already exists for this artist
      const existing = await prisma.scandal.findFirst({
        where: {
          artistId: artist.id,
          sourceUrl: scandal.sourceUrl,
        },
      })

      if (!existing) {
        const saved = await prisma.scandal.create({
          data: {
            artistId: artist.id,
            title: scandal.title,
            description: scandal.description,
            sourceUrl: scandal.sourceUrl,
            sourceName: scandal.sourceName,
            date: scandal.date,
            altSources: (scandal.altSources || []) as any,
          },
        })
        savedScandals.push(saved)
      }
    }

    return {
      success: true,
      artist,
      scandalsAdded: savedScandals.length,
      scandalsTotal: artistData.scandals.length,
    }
  } catch (error) {
    console.error('Error saving artist with scandals:', error)
    return { success: false, error: String(error) }
  }
}

// Transfer all cached data to main database and optionally flush cache
export async function transferCacheToDatabase(flushAfter = false) {
  try {
    const cacheEntries = await prisma.cacheEntry.findMany()
    let transferred = 0
    let errors = 0

    for (const entry of cacheEntries) {
      try {
        const data = entry.payload as any
        if (data && data.scandals && Array.isArray(data.scandals)) {
          const result = await saveArtistWithScandals({
            name: entry.artistName,
            imageUrl: data.imageUrl,
            genres: data.genres,
            scandals: data.scandals.map((s: any) => ({
              title: s.title || 'Scandal',
              description: s.description,
              sourceUrl: s.url || s.sourceUrl,
              sourceName: s.source || s.sourceName,
              date: s.date ? new Date(s.date) : undefined,
            })),
          })
          if (result.success) {
            transferred++
          } else {
            errors++
          }
        }
      } catch (err) {
        console.error(`Error transferring ${entry.artistName}:`, err)
        errors++
      }
    }

    // Optionally flush cache after transfer
    if (flushAfter && transferred > 0) {
      await prisma.cacheEntry.deleteMany({})
    }

    return {
      success: true,
      total: cacheEntries.length,
      transferred,
      errors,
      cacheFlushed: flushAfter,
    }
  } catch (error) {
    return { success: false, error: String(error) }
  }
}
