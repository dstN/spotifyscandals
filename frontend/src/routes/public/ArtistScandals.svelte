<script>
  import { onMount } from 'svelte'
  import { fetchArtist, fetchScandals } from '../../lib/api.js'
  import { showToast, spotifyUser, publicToken } from '../../lib/stores.js'
  import ScandalCard from '../../lib/ScandalCard.svelte'
  import CommunitySubmitPopup from '../../lib/CommunitySubmitPopup.svelte'

  let { params } = $props()
  
  let artist = $state(null)
  let scandals = $state([])
  let loading = $state(true)
  let expandedScandal = $state(null)
  let showCommunityPopup = $state(false)

  async function loadData() {
    loading = true
    try {
      const artistId = parseInt(params.id, 10)
      artist = await fetchArtist(artistId)
      scandals = await fetchScandals({ artist_id: artistId, verified: true })
    } catch (e) {
      showToast('error', `Failed to load artist: ${e.message}`)
    } finally {
      loading = false
    }
  }

  onMount(() => {
    loadData()
  })

  function getSeverityColor(score, isPercentage = false) {
    let normalized = isPercentage ? (100 - score) / 100 : (score - 1) / 9;
    if (normalized < 0.25) return 'text-green-500';
    if (normalized < 0.5) return 'text-yellow-400';
    if (normalized < 0.75) return 'text-orange-500';
    return 'text-red-500';
  }

  function handlePublicLogout() {
    publicToken.set(null);
    showToast('info', 'Logged out of Spotify');
  }

  async function reloadArtist() {
    artist = await fetchArtist(parseInt(params.id, 10))
  }
</script>

<div class="mx-auto max-w-3xl pt-8 pb-20 relative">
  <!-- Public Auth Header -->
  <div class="absolute top-4 right-0 flex items-center gap-4 z-20">
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

  <div class="mb-8 pt-6">
    <a href="/" class="text-sm font-medium text-text-tertiary transition-colors hover:text-text-primary">
      &larr; Back to Search
    </a>
  </div>

  {#if loading}
    <div class="flex py-20 justify-center">
      <div class="spinner w-8 h-8"></div>
    </div>
  {:else if !artist}
    <div class="glass py-16 text-center">
      <p class="text-xl text-text-secondary">Artist not found</p>
    </div>
  {:else}
    <!-- Artist Header -->
    <div class="glass mb-8 flex flex-col items-center gap-6 p-8 sm:flex-row sm:items-start text-center sm:text-left relative overflow-hidden">
      <!-- Background blur of the artist cover -->
      <div 
        class="absolute inset-0 opacity-10 bg-cover bg-center blur-2xl transform scale-110"
        style="background-image: url('{artist.image_url}')"
      ></div>
      
      <img
        src={artist.image_url || 'https://misc.scdn.co/liked-songs/liked-songs-300.png'}
        alt="{artist.name} cover"
        class="h-32 w-32 shrink-0 rounded-full object-cover shadow-2xl relative z-10"
      />
      <div class="relative z-10 flex-1">
        <h1 class="text-4xl font-bold tracking-tight text-text-primary mb-2">
          {artist.name}
        </h1>
        <div class="flex flex-col gap-3 items-center sm:items-start text-left">
          <a
            href={`https://open.spotify.com/artist/${artist.spotify_id}`}
            target="_blank"
            rel="noopener noreferrer"
            class="btn-spotify flex items-center justify-center gap-2 no-underline py-1.5 px-4 text-xs shadow-none w-max"
          >
            <svg class="h-4 w-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg>
            Open in Spotify
          </a>
          
          <div class="flex flex-wrap justify-center sm:justify-start items-center gap-3">
            <span class="text-xs font-medium text-text-tertiary">
              {scandals.length} verified scandal{scandals.length === 1 ? '' : 's'}
            </span>
            <div class="h-3 w-px bg-glass-border"></div>
            <button 
              onclick={() => showCommunityPopup = true}
              class="text-xs font-medium text-text-tertiary transition-colors hover:text-spotify cursor-pointer"
            >
              Did we miss a scandal?
            </button>
          </div>
        </div>
      </div>
      
      <!-- Safety Score Meter (Moved to Right) -->
      {#if artist.safety_score !== null && artist.safety_score !== undefined}
        <div class="relative z-10 flex flex-col items-center sm:items-end mt-6 sm:mt-0 p-4 bg-bg-primary/50 sm:bg-transparent rounded-2xl border sm:border-0 border-glass-border">
          <span class="text-[10px] font-bold uppercase tracking-widest text-text-tertiary mb-1">Safety Score</span>
          <div class="flex items-baseline gap-2">
            <span class={`text-3xl font-black ${getSeverityColor(artist.safety_score, true)}`}>
              {Math.round(artist.safety_score)}%
            </span>
            <span class="text-sm text-text-secondary font-medium uppercase">Safe to listen</span>
          </div>
          <p class="text-[10px] text-text-tertiary mt-1 sm:text-right">Based on aggregated severity votes</p>
        </div>
      {/if}
    </div>

    <!-- Scandals List -->
    {#if scandals.length === 0}
      <div class="glass py-12 text-center">
        <p class="text-lg text-text-secondary">No verified scandals found for this artist.</p>
        <p class="mt-2 text-sm text-text-tertiary">Clean record... for now.</p>
      </div>
    {:else}
      <div class="space-y-4">
        {#each scandals as scandal (scandal.id)}
          <ScandalCard 
            {scandal}
            expanded={expandedScandal === scandal.id}
            onToggle={() => expandedScandal = expandedScandal === scandal.id ? null : scandal.id}
            onVoteComplete={reloadArtist}
          />
        {/each}
      </div>
    {/if}
  {/if}
</div>

<!-- Community Scandal Popup -->
{#if showCommunityPopup && artist}
  <CommunitySubmitPopup 
    artistId={artist.id} 
    onClose={() => showCommunityPopup = false} 
  />
{/if}
