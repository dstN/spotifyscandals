<script>
  import { onMount } from 'svelte'
  import { fetchScandals, verifyScandal, deleteScandal } from '../lib/api.js'
  import { showToast } from '../lib/stores.js'

  let scandals = $state([])
  let loading = $state(true)
  let filterVerified = $state(null) // null = all, true = verified, false = unverified

  // Group scandals by artist
  let groupedScandals = $derived.by(() => {
    const groups = {}
    for (const scandal of scandals) {
      if (!groups[scandal.artist_id]) {
        groups[scandal.artist_id] = {
          id: scandal.artist_id,
          name: scandal.artist_name,
          image_url: scandal.artist_image_url,
          scandals: []
        }
      }
      groups[scandal.artist_id].scandals.push(scandal)
    }
    return Object.values(groups).sort((a, b) => a.name.localeCompare(b.name))
  })

  async function loadScandals() {
    loading = true
    try {
      scandals = await fetchScandals({ verified: filterVerified })
    } catch (e) {
      showToast('error', `Failed to load scandals: ${e.message}`)
    } finally {
      loading = false
    }
  }

  onMount(loadScandals)

  async function toggleVerification(scandal) {
    try {
      const result = await verifyScandal(scandal.id)
      scandal.verified = result.verified
      scandals = [...scandals]
      showToast('success', result.verified ? 'Scandal verified' : 'Verification removed')
    } catch (e) {
      showToast('error', e.message)
    }
  }

  async function removeScandal(scandal) {
    if (!confirm('Delete this scandal?')) return
    try {
      await deleteScandal(scandal.id)
      scandals = scandals.filter((s) => s.id !== scandal.id)
      showToast('success', 'Scandal deleted')
    } catch (e) {
      showToast('error', e.message)
    }
  }

  function applyFilter(value) {
    filterVerified = value
    loadScandals()
  }

  function formatDate(dateStr) {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }
</script>

<div class="fade-in space-y-6">
  <!-- Header -->
  <div>
    <h1 class="text-3xl font-semibold tracking-tight text-text-primary">Scandals</h1>
    <p class="mt-1 text-sm text-text-secondary">
      Review AI-detected scandals and verify sources
    </p>
  </div>

  <!-- Filters -->
  <div class="flex gap-1 rounded-xl border border-glass-border p-1 w-fit">
    <button
      class="rounded-lg px-3 py-1.5 text-xs font-medium transition-all
        {filterVerified === null ? 'bg-glass text-text-primary' : 'text-text-secondary hover:text-text-primary'}"
      onclick={() => applyFilter(null)}
    >
      All
    </button>
    <button
      class="rounded-lg px-3 py-1.5 text-xs font-medium transition-all
        {filterVerified === false ? 'bg-warning-glow text-warning' : 'text-text-secondary hover:text-text-primary'}"
      onclick={() => applyFilter(false)}
    >
      Unverified
    </button>
    <button
      class="rounded-lg px-3 py-1.5 text-xs font-medium transition-all
        {filterVerified === true ? 'bg-success-glow text-success' : 'text-text-secondary hover:text-text-primary'}"
      onclick={() => applyFilter(true)}
    >
      Verified
    </button>
  </div>

  <!-- Artist Grouped List -->
  {#if loading}
    <div class="flex items-center justify-center py-20">
      <div class="spinner"></div>
    </div>
  {:else if groupedScandals.length === 0}
    <div class="glass py-16 text-center">
      <p class="text-lg text-text-secondary">No scandals found</p>
      <p class="mt-2 text-sm text-text-tertiary">
        Approve artists and run a scan to discover scandals
      </p>
    </div>
  {:else}
    <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
      {#each groupedScandals as group (group.id)}
        <div class="glass group flex gap-4 p-5">
          <!-- Artist Header (Click to navigate to subroute) -->
          <a
            href="#/admin/scandals/{group.id}"
            class="flex items-center gap-4 w-full h-full text-left no-underline"
          >
            <!-- Artist Image -->
            <div class="h-14 w-14 flex-shrink-0 overflow-hidden rounded-2xl bg-bg-tertiary">
              {#if group.image_url}
                <img
                  src={group.image_url}
                  alt={group.name}
                  class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-110"
                />
              {:else}
                <div class="flex h-full w-full items-center justify-center text-xl text-text-tertiary">
                  ◉
                </div>
              {/if}
            </div>

            <!-- Info & Navigation indicator -->
            <div class="flex-1 flex items-center justify-between">
              <div>
                <h3 class="font-semibold text-text-primary leading-tight">{group.name}</h3>
                <p class="mt-0.5 text-xs text-text-tertiary">
                  {group.scandals.length} scandal{group.scandals.length !== 1 ? 's' : ''} detected
                </p>
              </div>
              <div class="flex items-center justify-center w-8 h-8 rounded-full bg-glass transition-colors duration-300 group-hover:bg-glass-hover text-text-secondary">
                <svg class="w-5 h-5 transition-transform group-hover:translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </div>
          </a>
        </div>
      {/each}
    </div>
  {/if}
</div>
