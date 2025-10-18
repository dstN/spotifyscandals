<template>
  <div class="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-black text-white">
    <header class="container mx-auto px-4 py-8">
      <h1 class="text-5xl font-bold text-center mb-2">
        🎵 Spotify Scandals
      </h1>
      <p class="text-center text-gray-300 text-lg">
        Entdecke die dunkle Seite deiner Lieblingskünstler
      </p>
    </header>

    <main class="container mx-auto px-4 py-8">
      <div class="max-w-2xl mx-auto">
        <div class="bg-white/10 backdrop-blur-lg rounded-2xl p-8 shadow-2xl">
          <h2 class="text-2xl font-semibold mb-4">Playlist analysieren</h2>
          
          <div class="space-y-4">
            <div>
              <label for="playlistUrl" class="block text-sm font-medium mb-2">
                Playlist-URL (Spotify oder YouTube)
              </label>
              <input
                id="playlistUrl"
                v-model="playlistUrl"
                type="text"
                placeholder="https://open.spotify.com/playlist/..."
                class="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/20 focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500/50 transition"
              />
            </div>

            <button
              @click="analyzePlaylist"
              :disabled="!playlistUrl || isLoading"
              class="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 disabled:from-gray-600 disabled:to-gray-700 disabled:cursor-not-allowed px-6 py-3 rounded-lg font-semibold transition shadow-lg"
            >
              {{ isLoading ? 'Analysiere...' : 'Playlist analysieren' }}
            </button>
          </div>

          <div v-if="error" class="mt-4 p-4 bg-red-500/20 border border-red-500/50 rounded-lg">
            <p class="text-red-200">{{ error }}</p>
          </div>

          <div v-if="results.length > 0" class="mt-8">
            <h3 class="text-xl font-semibold mb-4">Ergebnisse:</h3>
            <div class="space-y-4">
              <div
                v-for="artist in results"
                :key="artist.name"
                class="bg-white/5 rounded-lg p-4 border border-white/10"
              >
                <h4 class="font-semibold text-lg mb-2">{{ artist.name }}</h4>
                <div v-if="artist.scandals.length > 0" class="space-y-2">
                  <p
                    v-for="(scandal, idx) in artist.scandals"
                    :key="idx"
                    class="text-sm text-gray-300"
                  >
                    ⚠️ {{ scandal }}
                  </p>
                </div>
                <p v-else class="text-sm text-gray-400 italic">
                  Keine bekannten Skandale gefunden
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <footer class="container mx-auto px-4 py-8 text-center text-gray-400">
      <p>© 2025 Spotify Scandals · Powered by Vue 3, TypeScript & Tailwind CSS</p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const playlistUrl = ref('')
const isLoading = ref(false)
const error = ref('')
const results = ref<Array<{ name: string; scandals: string[] }>>([])

async function analyzePlaylist() {
  if (!playlistUrl.value) return

  isLoading.value = true
  error.value = ''
  results.value = []

  try {
    const response = await fetch('/api/analyze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ playlistUrl: playlistUrl.value }),
    })

    if (!response.ok) {
      throw new Error('Fehler beim Analysieren der Playlist')
    }

    const data = await response.json()
    results.value = data.artists
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Ein unbekannter Fehler ist aufgetreten'
  } finally {
    isLoading.value = false
  }
}
</script>
