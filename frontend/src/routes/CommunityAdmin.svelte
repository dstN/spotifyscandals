<script>
  import { onMount } from 'svelte'
  import { fetchPendingCommunityScandals, fetchPendingCommunitySources } from '../lib/api.js'
  import { showToast } from '../lib/stores.js'

  let submissions = $state([])
  let pendingSources = $state([])
  let loading = $state(true)

  // We want to group submissions by artist so we can show cards per artist
  let artistGroups = $derived.by(() => {
    const groups = {}
    for (const sub of submissions) {
      if (!groups[sub.artist.id]) {
        groups[sub.artist.id] = {
          artist: sub.artist,
          count: 0,
          latest: sub.created_at
        }
      }
      groups[sub.artist.id].count++
      if (new Date(sub.created_at) > new Date(groups[sub.artist.id].latest)) {
        groups[sub.artist.id].latest = sub.created_at
      }
    }
    return Object.values(groups).sort((a, b) => new Date(b.latest) - new Date(a.latest))
  })

  // Group pending sources by artist (same pattern as scandal submissions)
  let sourceArtistGroups = $derived.by(() => {
    const groups = {}
    for (const src of pendingSources) {
      const key = src.artist_name || 'Unknown'
      if (!groups[key]) {
        groups[key] = {
          artist_name: src.artist_name,
          artist_image_url: src.artist_image_url,
          scandal_id: src.scandal_id,
          count: 0,
          latest: src.created_at
        }
      }
      groups[key].count++
      if (new Date(src.created_at) > new Date(groups[key].latest)) {
        groups[key].latest = src.created_at
      }
    }
    return Object.values(groups).sort((a, b) => new Date(b.latest) - new Date(a.latest))
  })

  async function loadData() {
    loading = true
    try {
      const [scandals, sources] = await Promise.all([
        fetchPendingCommunityScandals(),
        fetchPendingCommunitySources(),
      ])
      submissions = scandals
      pendingSources = sources
    } catch (e) {
      showToast('error', `Failed to load submissions: ${e.message}`)
    } finally {
      loading = false
    }
  }

  onMount(loadData)

  function formatDate(dateStr) {
    if (!dateStr) return 'Unknown'
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }
</script>

<div class="fade-in space-y-6">
  <!-- Header -->
  <div class="flex flex-wrap items-center justify-between gap-4">
    <div>
      <h1 class="text-3xl font-semibold tracking-tight text-text-primary">Community Submissions</h1>
      <p class="mt-1 text-sm text-text-secondary">
        Verify and publish user-submitted scandals and sources.
      </p>
    </div>
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-20">
      <div class="spinner"></div>
    </div>
  {:else}
    <!-- Pending Scandals -->
    {#if artistGroups.length === 0 && sourceArtistGroups.length === 0}
      <div class="glass py-16 text-center">
        <p class="text-lg text-text-secondary">Inbox Zero</p>
        <p class="mt-2 text-sm text-text-tertiary">There are no pending community submissions to review.</p>
      </div>
    {/if}

    {#if artistGroups.length > 0}
      <div>
        <h2 class="text-xl font-semibold tracking-tight text-text-primary mb-3">Pending Scandals</h2>
        <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {#each artistGroups as group}
            <a 
              href="/admin/community/{group.artist.id}" 
              class="glass group flex gap-4 p-5 no-underline transition-all hover:border-glass-border-hover hover:bg-glass-hover"
            >
              <!-- Artist Image -->
              <div class="h-14 w-14 flex-shrink-0 overflow-hidden rounded-2xl bg-bg-tertiary">
                {#if group.artist.image_url}
                  <img
                    src={group.artist.image_url}
                    alt={group.artist.name}
                    class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-110"
                  />
                {:else}
                  <div class="flex h-full w-full items-center justify-center text-xl text-text-tertiary">
                    ◉
                  </div>
                {/if}
              </div>
              <!-- Info -->
              <div class="flex-1 flex flex-col justify-between">
                <div class="flex items-start justify-between gap-2">
                  <div>
                    <h3 class="font-semibold text-text-primary truncate">{group.artist.name}</h3>
                    <p class="mt-0.5 text-xs text-text-tertiary">
                      Last: {formatDate(group.latest)}
                    </p>
                  </div>
                  <span class="badge badge-warning whitespace-nowrap">
                    {group.count} Pending
                  </span>
                </div>
              </div>
            </a>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Pending Sources (same card layout as scandals) -->
    {#if sourceArtistGroups.length > 0}
      <div>
        <h2 class="text-xl font-semibold tracking-tight text-text-primary mb-3">Pending Sources</h2>
        <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {#each sourceArtistGroups as group}
            <a 
              href="/admin/community/sources/{encodeURIComponent(group.artist_name)}" 
              class="glass group flex gap-4 p-5 no-underline transition-all hover:border-glass-border-hover hover:bg-glass-hover"
            >
              <div class="h-14 w-14 flex-shrink-0 overflow-hidden rounded-2xl bg-bg-tertiary">
                {#if group.artist_image_url}
                  <img
                    src={group.artist_image_url}
                    alt={group.artist_name}
                    class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-110"
                  />
                {:else}
                  <div class="flex h-full w-full items-center justify-center text-xl text-text-tertiary">
                    ◉
                  </div>
                {/if}
              </div>
              <div class="flex-1 flex flex-col justify-between">
                <div class="flex items-start justify-between gap-2">
                  <div>
                    <h3 class="font-semibold text-text-primary truncate">{group.artist_name}</h3>
                    <p class="mt-0.5 text-xs text-text-tertiary">
                      Last: {formatDate(group.latest)}
                    </p>
                  </div>
                  <span class="badge badge-warning whitespace-nowrap">
                    {group.count} Pending
                  </span>
                </div>
              </div>
            </a>
          {/each}
        </div>
      </div>
    {/if}
  {/if}
</div>
