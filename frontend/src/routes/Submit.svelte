<script>
  import { submitPlaylist } from '../lib/api.js'
  import { showToast } from '../lib/stores.js'

  let playlistUrl = $state('')
  let submitting = $state(false)
  let result = $state(null)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!playlistUrl.trim()) return

    submitting = true
    result = null

    try {
      result = await submitPlaylist(playlistUrl.trim())
      showToast('success', `Added ${result.artists_added} artists from "${result.playlist_name}"`)
    } catch (e) {
      showToast('error', `Failed: ${e.message}`)
    } finally {
      submitting = false
    }
  }
</script>

<div class="fade-in mx-auto max-w-2xl space-y-8 pt-12 pb-20 relative">
  <!-- Back Button -->
  <div class="mb-4">
    <a href="/" class="text-sm font-medium text-text-tertiary transition-colors hover:text-text-primary no-underline">
      &larr; Back to Search
    </a>
  </div>
  
  <!-- Header -->
  <div class="text-center">
    <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-3xl bg-spotify text-3xl font-bold text-black shadow-lg shadow-spotify-glow">
      ♫
    </div>
    <h1 class="text-3xl font-semibold tracking-tight text-text-primary">Submit Playlist</h1>
    <p class="mt-2 text-sm text-text-secondary">
      Paste a Spotify playlist URL to extract and track artists
    </p>
  </div>

  <!-- Form -->
  <form onsubmit={handleSubmit} class="glass space-y-5 p-8">
    <div>
      <label for="playlist-url" class="mb-2 block text-sm font-medium text-text-secondary">
        Spotify Playlist URL
      </label>
      <input
        id="playlist-url"
        type="text"
        class="input-glass"
        placeholder="https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        bind:value={playlistUrl}
        disabled={submitting}
      />
      <p class="mt-2 text-xs text-text-tertiary">
        Supports full URLs, Spotify URIs, or raw playlist IDs
      </p>
    </div>

    <button
      type="submit"
      class="btn-spotify w-full py-3 text-base font-semibold"
      disabled={submitting || !playlistUrl.trim()}
    >
      {#if submitting}
        <span class="inline-flex items-center gap-2">
          <div class="spinner"></div>
          Extracting Artists…
        </span>
      {:else}
        Extract Artists
      {/if}
    </button>
  </form>

  <!-- Result Card -->
  {#if result}
    <div class="glass fade-in space-y-4 p-6">
      <h2 class="text-lg font-semibold text-text-primary">
        ✓ Extraction Complete
      </h2>

      <div class="grid grid-cols-3 gap-4">
        <div class="rounded-2xl bg-bg-tertiary p-4 text-center">
          <p class="text-2xl font-bold text-spotify">{result.artists_added}</p>
          <p class="mt-1 text-xs text-text-tertiary">Artists Added</p>
        </div>
        <div class="rounded-2xl bg-bg-tertiary p-4 text-center">
          <p class="text-2xl font-bold text-text-secondary">{result.artists_skipped}</p>
          <p class="mt-1 text-xs text-text-tertiary">Already Existed</p>
        </div>
        <div class="rounded-2xl bg-bg-tertiary p-4 text-center">
          <p class="text-2xl font-bold text-accent">
            {result.artists_added + result.artists_skipped}
          </p>
          <p class="mt-1 text-xs text-text-tertiary">Total in Playlist</p>
        </div>
      </div>

      <div class="flex gap-3">
        <a href="/artists" class="btn-spotify inline-block flex-1 text-center no-underline py-2">
          Review Artists →
        </a>
        <button
          class="btn-outline flex-1"
          onclick={() => { result = null; playlistUrl = '' }}
        >
          Submit Another
        </button>
      </div>

      <!-- Artist Grid -->
      {#if result.artists && result.artists.length > 0}
        <div class="pt-2">
          <h3 class="mb-3 text-sm font-semibold text-text-secondary">Artists in this Playlist</h3>
          <div class="grid gap-3 sm:grid-cols-2">
            {#each result.artists as artist (artist.id)}
              <a 
                href="/artist/{artist.id}" 
                class="glass group/card relative flex items-center gap-3 p-3 transition-all hover:-translate-y-1 block no-underline"
              >
                <img
                  src={artist.image_url || 'https://misc.scdn.co/liked-songs/liked-songs-300.png'}
                  alt="{artist.name} cover"
                  class="h-12 w-12 rounded-full object-cover ring-2 ring-glass-border group-hover/card:ring-accent transition-colors"
                />
                <div class="min-w-0 flex-1">
                  <h4 class="truncate text-sm font-bold text-text-primary group-hover/card:text-accent transition-colors">
                    {artist.name}
                  </h4>
                  {#if artist.scandal_count > 0}
                    <p class="text-xs text-text-secondary">
                      {artist.scandal_count} scandal{artist.scandal_count === 1 ? '' : 's'}
                    </p>
                  {/if}
                </div>
              </a>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  {/if}

  <!-- Instructions -->
  <div class="glass p-6">
    <h3 class="mb-3 text-sm font-semibold text-text-primary">How it works</h3>
    <ol class="space-y-2 text-sm text-text-secondary">
      <li class="flex gap-3">
        <span class="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-glass text-xs font-semibold text-accent">1</span>
        <span>Paste a Spotify playlist URL above</span>
      </li>
      <li class="flex gap-3">
        <span class="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-glass text-xs font-semibold text-accent">2</span>
        <span>We extract all unique artists and store them</span>
      </li>
      <li class="flex gap-3">
        <span class="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-glass text-xs font-semibold text-accent">3</span>
        <span>Review and approve artists for AI scandal scanning</span>
      </li>
      <li class="flex gap-3">
        <span class="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-glass text-xs font-semibold text-accent">4</span>
        <span>Google Gemini analyzes approved artists for controversies</span>
      </li>
      <li class="flex gap-3">
        <span class="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-glass text-xs font-semibold text-accent">5</span>
        <span>Verify each scandal and review source links</span>
      </li>
    </ol>
  </div>
</div>
