<script>
  import { onMount } from 'svelte'
  import { fetchArtists, approveArtist, deleteArtist, scanForScandals } from '../lib/api.js'
  import { showToast } from '../lib/stores.js'

  let artists = $state([])
  let loading = $state(true)
  let searchQuery = $state('')
  let filterApproved = $state(null) // null = all, true = approved, false = pending
  let scanning = $state(false)

  async function loadArtists() {
    loading = true
    try {
      artists = await fetchArtists({
        approved: filterApproved,
        search: searchQuery || undefined,
      })
    } catch (e) {
      showToast('error', `Failed to load artists: ${e.message}`)
    } finally {
      loading = false
    }
  }

  onMount(loadArtists)

  async function toggleApproval(artist) {
    try {
      const result = await approveArtist(artist.id)
      artist.approved = result.approved
      showToast('success', `${artist.name} ${result.approved ? 'approved' : 'unapproved'}`)
      // Refresh list to reflect count changes
      artists = [...artists]
    } catch (e) {
      showToast('error', e.message)
    }
  }

  async function removeArtist(artist) {
    if (!confirm(`Delete ${artist.name}? This will also delete all their scandals.`)) return
    try {
      await deleteArtist(artist.id)
      artists = artists.filter((a) => a.id !== artist.id)
      showToast('success', `${artist.name} deleted`)
    } catch (e) {
      showToast('error', e.message)
    }
  }

  async function scanApproved() {
    scanning = true
    try {
      const result = await scanForScandals()
      showToast('success', result.message || 'Scan initiated in background.')
    } catch (e) {
      showToast('error', `Scan failed: ${e.message}`)
    } finally {
      scanning = false
    }
  }

  function applyFilter(value) {
    filterApproved = value
    loadArtists()
  }

  function handleSearch() {
    loadArtists()
  }
</script>

<div class="fade-in space-y-6">
  <!-- Header -->
  <div class="flex flex-wrap items-center justify-between gap-4">
    <div>
      <h1 class="text-3xl font-semibold tracking-tight text-text-primary">Artists</h1>
      <p class="mt-1 text-sm text-text-secondary">
        Manage and approve artists for scandal scanning
      </p>
    </div>
    <button
      class="btn-primary inline-flex items-center gap-2"
      onclick={scanApproved}
      disabled={scanning}
    >
      {#if scanning}
        <div class="spinner"></div>
        Scanning…
      {:else}
        ⚡ Scan Approved Artists
      {/if}
    </button>
  </div>

  <!-- Filters -->
  <div class="flex flex-wrap items-center gap-3">
    <!-- Search -->
    <div class="flex-1">
      <input
        type="text"
        class="input-glass"
        placeholder="Search artists…"
        bind:value={searchQuery}
        onkeydown={(e) => e.key === 'Enter' && handleSearch()}
      />
    </div>

    <!-- Status Filter -->
    <div class="flex gap-1 rounded-xl border border-glass-border p-1">
      <button
        class="rounded-lg px-3 py-1.5 text-xs font-medium transition-all
          {filterApproved === null ? 'bg-glass text-text-primary' : 'text-text-secondary hover:text-text-primary'}"
        onclick={() => applyFilter(null)}
      >
        All
      </button>
      <button
        class="rounded-lg px-3 py-1.5 text-xs font-medium transition-all
          {filterApproved === true ? 'bg-success-glow text-success' : 'text-text-secondary hover:text-text-primary'}"
        onclick={() => applyFilter(true)}
      >
        Approved
      </button>
      <button
        class="rounded-lg px-3 py-1.5 text-xs font-medium transition-all
          {filterApproved === false ? 'bg-warning-glow text-warning' : 'text-text-secondary hover:text-text-primary'}"
        onclick={() => applyFilter(false)}
      >
        Pending
      </button>
    </div>
  </div>

  <!-- Artist List -->
  {#if loading}
    <div class="flex items-center justify-center py-20">
      <div class="spinner"></div>
    </div>
  {:else if artists.length === 0}
    <div class="glass py-16 text-center">
      <p class="text-lg text-text-secondary">No artists found</p>
      <p class="mt-2 text-sm text-text-tertiary">Submit a Spotify playlist to get started</p>
      <a href="#/submit" class="btn-spotify mt-4 inline-block no-underline">♫ Submit Playlist</a>
    </div>
  {:else}
    <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
      {#each artists as artist (artist.id)}
        <div class="glass group flex gap-4 p-5">
          <!-- Artist Image -->
          <div class="h-14 w-14 flex-shrink-0 overflow-hidden rounded-2xl bg-bg-tertiary">
            {#if artist.image_url}
              <img
                src={artist.image_url}
                alt={artist.name}
                class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-110"
              />
            {:else}
              <div class="flex h-full w-full items-center justify-center text-xl text-text-tertiary">
                ◉
              </div>
            {/if}
          </div>

          <!-- Info -->
          <div class="flex-1">
            <div class="flex items-start justify-between">
              <div>
                <h3 class="font-semibold text-text-primary">{artist.name}</h3>
                <p class="mt-0.5 text-xs text-text-tertiary">
                  {artist.scandal_count} scandal{artist.scandal_count !== 1 ? 's' : ''}
                </p>
              </div>
              <span class="badge {artist.approved ? 'badge-success' : 'badge-warning'}">
                {artist.approved ? 'Approved' : 'Pending'}
              </span>
            </div>

            <!-- Actions -->
            <div class="mt-3 flex gap-2">
              <button
                class="btn-outline px-3 py-1.5 text-xs {artist.approved ? 'border-warning text-warning' : 'border-success text-success'}"
                onclick={() => toggleApproval(artist)}
              >
                {artist.approved ? '✗ Unapprove' : '✓ Approve'}
              </button>
              <button
                class="btn-outline border-danger px-3 py-1.5 text-xs text-danger"
                onclick={() => removeArtist(artist)}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
