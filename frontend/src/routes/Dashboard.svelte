<script>
  import { onMount } from 'svelte'
  import { fetchStats } from '../lib/api.js'

  let stats = $state(null)
  let loading = $state(true)

  onMount(async () => {
    try {
      stats = await fetchStats()
    } catch (e) {
      console.error('Failed to load stats:', e)
      // Show placeholder stats if backend is unreachable
      stats = {
        total_artists: 0,
        approved_artists: 0,
        pending_artists: 0,
        total_scandals: 0,
        verified_scandals: 0,
        unverified_scandals: 0,
      }
    } finally {
      loading = false
    }
  })

  const cards = $derived(
    stats
      ? [
          {
            label: 'Total Artists',
            value: stats.total_artists,
            icon: '◉',
            color: 'text-accent',
            bg: 'bg-accent-glow',
          },
          {
            label: 'Approved',
            value: stats.approved_artists,
            icon: '✓',
            color: 'text-success',
            bg: 'bg-success-glow',
          },
          {
            label: 'Pending Review',
            value: stats.pending_artists,
            icon: '⏳',
            color: 'text-warning',
            bg: 'bg-warning-glow',
          },
          {
            label: 'Total Scandals',
            value: stats.total_scandals,
            icon: '⚡',
            color: 'text-danger',
            bg: 'bg-danger-glow',
          },
          {
            label: 'Verified',
            value: stats.verified_scandals,
            icon: '✓',
            color: 'text-success',
            bg: 'bg-success-glow',
          },
          {
            label: 'Unverified',
            value: stats.unverified_scandals,
            icon: '?',
            color: 'text-warning',
            bg: 'bg-warning-glow',
          },
        ]
      : []
  )
</script>

<div class="fade-in space-y-8">
  <!-- Header -->
  <div>
    <h1 class="text-3xl font-semibold tracking-tight text-text-primary">Dashboard</h1>
    <p class="mt-1 text-sm text-text-secondary">
      Overview of tracked artists and discovered scandals
    </p>
  </div>

  <!-- Stats Grid -->
  {#if loading}
    <div class="flex items-center justify-center py-20">
      <div class="spinner"></div>
    </div>
  {:else}
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each cards as card, i}
        <div
          class="glass group cursor-default p-6"
          style="animation-delay: {i * 60}ms"
        >
          <div class="flex items-center justify-between">
            <div>
              <p class="text-xs font-medium uppercase tracking-wider text-text-tertiary">
                {card.label}
              </p>
              <p class="mt-2 text-3xl font-bold {card.color}">
                {card.value}
              </p>
            </div>
            <div
              class="{card.bg} flex h-12 w-12 items-center justify-center rounded-2xl text-xl transition-transform duration-300 group-hover:scale-110"
            >
              {card.icon}
            </div>
          </div>
        </div>
      {/each}
    </div>

  {/if}
</div>
