<script>
  import { onMount } from 'svelte'
  import { fetchArtists } from '../../lib/api.js'
  import { showToast, spotifyUser, publicToken } from '../../lib/stores.js'

  let artists = $state([])
  let loading = $state(true)
  let searchQuery = $state('')

  async function loadArtists() {
    loading = true
    try {
      // Only fetch approved artists for the public view
      artists = await fetchArtists({ approved: true, search: searchQuery || null })
    } catch (e) {
      showToast('error', `Failed to load artists: ${e.message}`)
    } finally {
      loading = false
    }
  }

  function handlePublicLogout() {
    publicToken.set(null);
    showToast('info', 'Logged out of Spotify');
  }

  onMount(loadArtists)

  let searchTimeout
  function handleSearchInput() {
    clearTimeout(searchTimeout)
    searchTimeout = setTimeout(() => {
      loadArtists()
    }, 300)
  }
</script>

<div class="mx-auto max-w-4xl pt-12 relative">
  <!-- Public Auth Header -->
  <div class="absolute top-4 right-0 flex items-center gap-4">
    {#if $spotifyUser}
      <div class="flex items-center gap-3 bg-glass px-4 py-2 flex items-center justify-center h-10 rounded-full border border-glass-border">
        {#if $spotifyUser.image}
          <img src={$spotifyUser.image} alt="Profile" class="h-6 w-6 rounded-full object-cover" />
        {:else}
          <div class="h-6 w-6 rounded-full bg-spotify flex items-center justify-center text-black font-bold text-xs">S</div>
        {/if}
        <span class="text-sm font-medium text-text-primary">{$spotifyUser.name}</span>
        <button onclick={handlePublicLogout} class="text-xs text-text-tertiary hover:text-white transition-colors cursor-pointer ml-2">Logout</button>
      </div>
    {:else}
      <a href="/api/public/auth/spotify/login" class="btn-spotify flex items-center justify-center gap-2 no-underline shadow-none py-2 h-10">
        <div class="h-5 w-5 rounded-full bg-black/20 flex items-center justify-center text-black font-bold text-[10px]">S</div>
        <span>Login to Vote</span>
      </a>
    {/if}
  </div>

  <div class="mb-12 mt-8 text-center">
    <h1 class="text-3xl font-bold tracking-tight text-text-primary sm:text-5xl">
      Spotify <span class="text-accent">Scandals</span>
    </h1>
    <p class="mt-4 text-lg text-text-secondary">
      Discover the controversies behind the music. Search for an artist to view verified scandals.
    </p>
  </div>

  <!-- Search Bar -->
  <div class="mx-auto mb-10 max-w-xl relative">
    <input
      type="text"
      placeholder="Search for an artist..."
      bind:value={searchQuery}
      oninput={handleSearchInput}
      class="input-glass w-full !pl-14 py-4 text-lg rounded-2xl shadow-xl border-t border-glass-border/50"
    />
    <svg class="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-text-tertiary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  </div>

  {#if loading}
    <div class="flex py-20 justify-center">
      <div class="spinner w-8 h-8"></div>
    </div>
  {:else if artists.length === 0}
    <div class="glass py-16 text-center">
      <p class="text-xl text-text-secondary">No artists found</p>
      {#if !searchQuery}
        <p class="mt-2 text-text-tertiary">Check back later or submit a playlist to trigger a scan.</p>
      {/if}
    </div>
  {:else}
    <div class="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
      {#each artists as artist (artist.id)}
        <a 
          href="#/artist/{artist.id}" 
          class="glass group/card relative flex items-center gap-4 p-4 transition-all hover:-translate-y-1 block no-underline"
        >
          <img
            src={artist.image_url || 'https://misc.scdn.co/liked-songs/liked-songs-300.png'}
            alt="{artist.name} cover"
            class="h-16 w-16 rounded-full object-cover ring-2 ring-glass-border group-hover/card:ring-accent transition-colors"
          />
          <div class="min-w-0 flex-1">
            <h3 class="truncate text-lg font-bold text-text-primary group-hover/card:text-accent transition-colors">
              {artist.name}
            </h3>
            <p class="mt-1 text-sm text-text-secondary">
              {artist.scandal_count} scandal{artist.scandal_count === 1 ? '' : 's'}
            </p>
          </div>
          <div class="absolute right-4 top-1/2 -translate-y-1/2 text-text-tertiary opacity-0 transition-opacity group-hover/card:opacity-100">
            &rarr;
          </div>
        </a>
      {/each}
    </div>
  {/if}

  <!-- Submit Call to Action -->
  <div class="mt-20 text-center pb-10">
    <p class="text-text-secondary mb-4">Want to track a different artist?</p>
    <a href="#/submit" class="btn-spotify inline-block flex items-center justify-center mx-auto no-underline shadow-none w-fit">Submit a Playlist</a>
  </div>
</div>
