<script>
  import { onMount } from 'svelte'
  import { fetchArtists } from '../../lib/api.js'
  import { showToast, spotifyUser, publicToken, spotifyAccessToken, playlistFilterIds } from '../../lib/stores.js'

  let artists = $state([])
  let loading = $state(true)
  let searchQuery = $state('')
  let showSearch = $state(false)
  let userTopArtists = $state([])
  let filterIds = $state(null)
  let showTopOnly = $state(false)

  // Subscribe to playlist filter
  const unsubFilter = playlistFilterIds.subscribe(v => filterIds = v)

  // ── Sorting ──
  let sortBy = $state('scandals') // 'scandals', 'name', 'severity', 'newest'
  let sortDesc = $state(true)

  // Filter: playlist filter > top artists filter > all
  let filteredArtists = $derived.by(() => {
    if (filterIds) return artists.filter(a => filterIds.includes(a.id))
    if (showTopOnly && userTopArtists.length > 0) return userTopArtists
    return artists
  })

  let sortedArtists = $derived.by(() => {
    return [...filteredArtists].sort((a, b) => {
      let valA, valB;
      if (sortBy === 'name') {
        valA = a.name.toLowerCase();
        valB = b.name.toLowerCase();
      } else if (sortBy === 'scandals') {
        valA = a.scandal_count || 0;
        valB = b.scandal_count || 0;
      } else if (sortBy === 'severity') {
        // Assuming lower safety_score means higher severity/scandal level.
        // Nulls get pushed to the end using a high default value.
        valA = sortDesc ? (a.safety_score !== null ? -a.safety_score : -999) : (a.safety_score !== null ? a.safety_score : 999);
        valB = sortDesc ? (b.safety_score !== null ? -b.safety_score : -999) : (b.safety_score !== null ? b.safety_score : 999);
      } else if (sortBy === 'newest') {
        valA = new Date(a.created_at).getTime();
        valB = new Date(b.created_at).getTime();
      }
      
      if (valA < valB) return sortDesc ? 1 : -1;
      if (valA > valB) return sortDesc ? -1 : 1;
      return 0;
    });
  })

  // ── Pagination ──
  let currentPage = $state(1)
  let perPage = $state(24)

  let totalPages = $derived(Math.max(1, Math.ceil(sortedArtists.length / perPage)))
  let paginatedArtists = $derived(sortedArtists.slice((currentPage - 1) * perPage, currentPage * perPage))

  // Visible page buttons (max 7 around current)
  let visiblePages = $derived.by(() => {
    const pages = []
    const maxVisible = 7
    let start = Math.max(1, currentPage - Math.floor(maxVisible / 2))
    let end = Math.min(totalPages, start + maxVisible - 1)
    if (end - start + 1 < maxVisible) {
      start = Math.max(1, end - maxVisible + 1)
    }
    for (let i = start; i <= end; i++) pages.push(i)
    return pages
  })

  function goToPage(page) {
    currentPage = Math.max(1, Math.min(page, totalPages))
    // Scroll to top of the page smoothly
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function handlePerPageChange(e) {
    perPage = parseInt(e.target.value)
    currentPage = 1 // Reset to first page
  }

  function handleSortChange() {
    currentPage = 1
  }

  function toggleSortOrder() {
    sortDesc = !sortDesc
    currentPage = 1
  }

  async function loadArtists() {
    loading = true
    try {
      artists = await fetchArtists({ approved: true, search: searchQuery || null })
      currentPage = 1 // Reset to page 1 on new data
    } catch (e) {
      showToast('error', `Failed to load artists: ${e.message}`)
    } finally {
      loading = false
    }
  }

  function handlePublicLogout() {
    publicToken.set(null);
    spotifyAccessToken.set(null);
    showToast('info', 'Logged out of Spotify');
  }

  async function loadTopArtists() {
    let token
    const unsub = spotifyAccessToken.subscribe(v => token = v)
    unsub()
    if (!token) return
    try {
      const resp = await fetch('https://api.spotify.com/v1/me/top/artists?limit=50', {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (resp.status === 401) {
        spotifyAccessToken.set(null)
        return
      }
      if (!resp.ok) return
      const data = await resp.json()
      const topSpotifyIds = data.items.map(a => a.id)
      // Intersect with our DB artists, preserving Spotify rank order
      const dbMap = new Map(artists.map(a => [a.spotify_id, a]))
      userTopArtists = topSpotifyIds
        .filter(id => dbMap.has(id))
        .map(id => dbMap.get(id))
    } catch {
      // Silently ignore — non-critical feature
    }
  }

  function clearFilter() {
    playlistFilterIds.set(null)
  }

  onMount(async () => {
    // If we have a playlist filter, force show the search/grid view
    if (filterIds) showSearch = true
    await loadArtists()
    await loadTopArtists()
    // Auto-show top artists when logged in
    if (userTopArtists.length > 0 && !filterIds) {
      showTopOnly = true
      showSearch = true
    }
    return () => unsubFilter()
  })

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

  <!-- Filter banners -->
  {#if filterIds}
    <div class="glass flex items-center justify-between px-5 py-3 mb-6 border border-spotify/20">
      <p class="text-sm text-text-secondary">
        Showing <span class="font-bold text-spotify">{filteredArtists.length}</span> artists from your playlist
      </p>
      <button onclick={clearFilter} class="text-sm font-medium text-text-tertiary hover:text-white transition-colors cursor-pointer">
        Show all artists
      </button>
    </div>
  {:else if showTopOnly && userTopArtists.length > 0}
    <div class="glass flex items-center justify-between px-5 py-3 mb-6 border border-spotify/20">
      <p class="text-sm text-text-secondary">
        <span class="text-spotify">♫</span> Showing your <span class="font-bold text-spotify">{userTopArtists.length}</span> top artists
      </p>
      <button onclick={() => showTopOnly = false} class="text-sm font-medium text-text-tertiary hover:text-white transition-colors cursor-pointer">
        Show all artists
      </button>
    </div>
  {:else if !showTopOnly && userTopArtists.length > 0}
    <div class="glass flex items-center justify-between px-5 py-3 mb-6 border border-glass-border">
      <p class="text-sm text-text-secondary">
        Showing all <span class="font-bold text-text-primary">{artists.length}</span> tracked artists
      </p>
      <button onclick={() => showTopOnly = true} class="text-sm font-medium text-spotify hover:text-white transition-colors cursor-pointer">
        ♫ Show my top artists
      </button>
    </div>
  {/if}

  <!-- Landing View for Logged Out Users -->
  {#if !$spotifyUser && !showSearch && !filterIds}
    <div class="fade-in max-w-lg mx-auto mt-16 text-center space-y-6">
      <div class="glass p-8 flex flex-col items-center gap-6">
        <h2 class="text-2xl font-bold text-text-primary">Help us uncover the truth</h2>
        <p class="text-text-secondary">
          Track the artists you listen to and we'll automatically scan them for controversies.
        </p>
        
        <div class="flex flex-col sm:flex-row gap-4 w-full">
          <a href="/submit" class="btn-spotify flex-1 text-center no-underline py-3">
            Submit a Playlist
          </a>
          <button 
            class="btn-outline flex-1 py-3 bg-glass"
            onclick={() => showSearch = true}
          >
            Or search the database?
          </button>
        </div>
      </div>
    </div>
  {:else}
    <div class="fade-in">
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
        <!-- Count & Sorting Controls -->
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4 px-1">
          <p class="text-sm text-text-tertiary">
            Showing {(currentPage - 1) * perPage + 1}–{Math.min(currentPage * perPage, sortedArtists.length)} of {sortedArtists.length} artists
          </p>

          <div class="flex items-center gap-3">
            <div class="flex items-center gap-2">
              <label for="sortBy" class="text-sm text-text-tertiary whitespace-nowrap">Sort by:</label>
              <select
                id="sortBy"
                bind:value={sortBy}
                onchange={handleSortChange}
                class="pagination-select"
              >
                <option value="scandals">Scandal Count</option>
                <option value="severity">Severity (Vote)</option>
                <option value="newest">Recently Added</option>
                <option value="name">Name (A-Z)</option>
              </select>
            </div>
            
            <button
              onclick={toggleSortOrder}
              class="pagination-select flex items-center justify-center !px-3 font-bold text-accent"
              title={sortDesc ? 'Descending' : 'Ascending'}
            >
              {sortDesc ? '↓' : '↑'}
            </button>
          </div>
        </div>

        <div class="artist-grid grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {#each paginatedArtists as artist (artist.id)}
            <a 
              href="/artist/{artist.id}" 
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

        <!-- Pagination Controls -->
        {#if totalPages > 1 || artists.length > 24}
          <div class="mt-10 flex flex-col sm:flex-row items-center justify-between gap-4 pb-4">
            <!-- Page Navigation -->
            <div class="flex items-center gap-1.5">
              <button
                onclick={() => goToPage(1)}
                disabled={currentPage === 1}
                class="pagination-btn"
                title="First page"
              >
                ««
              </button>
              <button
                onclick={() => goToPage(currentPage - 1)}
                disabled={currentPage === 1}
                class="pagination-btn"
                title="Previous page"
              >
                ‹
              </button>

              {#each visiblePages as page}
                <button
                  onclick={() => goToPage(page)}
                  class="pagination-btn {page === currentPage ? 'pagination-btn-active' : ''}"
                >
                  {page}
                </button>
              {/each}

              <button
                onclick={() => goToPage(currentPage + 1)}
                disabled={currentPage === totalPages}
                class="pagination-btn"
                title="Next page"
              >
                ›
              </button>
              <button
                onclick={() => goToPage(totalPages)}
                disabled={currentPage === totalPages}
                class="pagination-btn"
                title="Last page"
              >
                »»
              </button>
            </div>

            <!-- Per-Page Selector -->
            <div class="flex items-center gap-2">
              <label for="perPage" class="text-sm text-text-tertiary whitespace-nowrap">Show:</label>
              <select
                id="perPage"
                value={perPage}
                onchange={handlePerPageChange}
                class="pagination-select"
              >
                <option value={24}>24</option>
                <option value={48}>48</option>
                <option value={100}>100</option>
                <option value={250}>250</option>
              </select>
            </div>
          </div>
        {/if}
      {/if}
      
      <!-- Submit Call to Action for Search View -->
      <div class="mt-20 text-center pb-10">
        <p class="text-text-secondary mb-4">Want to track a different artist?</p>
        <a href="/submit" class="btn-spotify inline-block flex items-center justify-center mx-auto no-underline shadow-none w-fit">Submit a Playlist</a>
      </div>
    </div>
  {/if}
</div>

<style>
  .pagination-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 2.25rem;
    height: 2.25rem;
    padding: 0 0.5rem;
    border-radius: 0.75rem;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.04);
    color: rgba(255, 255, 255, 0.5);
    font-size: 0.8125rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    backdrop-filter: blur(8px);
  }
  .pagination-btn:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.15);
    color: rgba(255, 255, 255, 0.9);
    transform: translateY(-1px);
  }
  .pagination-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }
  .pagination-btn-active {
    background: var(--color-accent-glow) !important;
    border-color: var(--color-accent) !important;
    color: var(--color-accent) !important;
    box-shadow: 0 0 12px var(--color-accent-glow);
  }
  .pagination-select {
    appearance: none;
    padding: 0.375rem 2rem 0.375rem 0.75rem;
    border-radius: 0.75rem;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.04) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23888' d='M3 4.5L6 8l3-3.5H3z'/%3E%3C/svg%3E") no-repeat right 0.6rem center;
    color: rgba(255, 255, 255, 0.7);
    font-size: 0.8125rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    backdrop-filter: blur(8px);
  }
  .pagination-select:hover {
    background-color: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.15);
  }
  .pagination-select:focus {
    outline: none;
    border-color: var(--color-accent);
    box-shadow: 0 0 0 2px var(--color-accent-glow);
  }
  .pagination-select option {
    background: #1a1a1a;
    color: #fff;
  }
</style>
