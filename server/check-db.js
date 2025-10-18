// Quick DB check script
const { PrismaClient } = require('@prisma/client')
const prisma = new PrismaClient()

async function checkDB() {
  try {
    // Check Artists
    const artists = await prisma.artist.findMany({
      include: {
        scandals: true
      }
    })
    
    console.log('\n=== ARTISTS IN DATABASE ===')
    console.log(`Total: ${artists.length}\n`)
    
    for (const artist of artists) {
      console.log(`📍 ${artist.name}`)
      console.log(`   Scandals: ${artist.scandals.length}`)
      console.log(`   Created: ${artist.createdAt}`)
      artist.scandals.forEach((s, i) => {
        console.log(`   ${i+1}. ${s.title}`)
        console.log(`      Source: ${s.sourceName} - ${s.sourceUrl}`)
      })
      console.log('')
    }
    
    // Check Cache
    const cache = await prisma.cacheEntry.findMany()
    console.log(`\n=== CACHE ENTRIES ===`)
    console.log(`Total: ${cache.length}`)
    cache.forEach(c => {
      const expiresIn = c.expiresAt ? Math.ceil((c.expiresAt - new Date()) / (1000 * 60 * 60 * 24)) : 'N/A'
      console.log(`- ${c.artistName} (expires in ${expiresIn} days)`)
    })
    
  } catch (error) {
    console.error('Error:', error)
  } finally {
    await prisma.$disconnect()
  }
}

checkDB()
