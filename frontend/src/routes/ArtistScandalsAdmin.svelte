<script>
  import { onMount } from 'svelte'
  import { fetchArtist, verifyScandal, verifyScandalSource, deleteScandal, deleteScandalSource, addSourceToScandal } from '../lib/api.js'
  import { showToast } from '../lib/stores.js'

  let { artistId } = $props()

  let scandals = $state([])
  let communityScandals = $state([])
  let artistName = $state('')
  let loading = $state(true)

  let addSourceScandalId = $state(null)
  let addSourceUrl = $state("")
  let isAddingSource = $state(false)

  async function handleAddSource(scandalId) {
    if (!addSourceUrl.trim()) return
    isAddingSource = true
    try {
      const newSource = await addSourceToScandal(scandalId, addSourceUrl.trim())
      const scandal = scandals.find(s => s.id === scandalId)
      if (scandal) {
        scandal.sources = [...(scandal.sources || []), newSource]
        scandals = [...scandals]
      }
      showToast('success', 'Source added')
      addSourceScandalId = null
      addSourceUrl = ""
    } catch (e) {
      showToast('error', `Failed to add source: ${e.message}`)
    } finally {
      isAddingSource = false
    }
  }

  async function loadScandals() {
    loading = true
    try {
      const artist = await fetchArtist(artistId)
      artistName = artist.name
      scandals = artist.scandals
      communityScandals = artist.community_scandals || []
    } catch (e) {
      showToast('error', `Failed to load scandals: ${e.message}`)
    } finally {
      loading = false
    }
  }

  // Reload when artistId prop changes
  $effect(() => {
    if (artistId) {
      loadScandals()
    }
  })

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

  async function toggleSourceVerification(scandal, source) {
    try {
      const result = await verifyScandalSource(scandal.id, source.id)
      source.is_verified = result.is_verified
      scandals = [...scandals] // Trigger reactivity
      showToast('success', result.is_verified ? 'Source manually verified' : 'Source unverified')
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

  async function removeSource(scandal, source) {
    if (!confirm('Remove this source?')) return
    try {
      await deleteScandalSource(scandal.id, source.id)
      scandal.sources = scandal.sources.filter(s => s.id !== source.id)
      scandals = [...scandals] // Trigger reactivity
      showToast('success', 'Source removed')
    } catch (e) {
      showToast('error', e.message)
    }
  }

  function formatDate(dateStr) {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  function formatSourceLabel(url) {
    try {
      const parsed = new URL(url)
      // vertexaisearch redirect URLs embed the real source domain in their path
      // e.g. https://vertexaisearch.cloud.google.com/grounding-api-redirect/...
      // The actual site title is not in the URL itself, so extract a clean label
      if (parsed.hostname.includes('vertexaisearch')) {
        // Try to extract source domain from query params or path segments
        const params = parsed.searchParams
        const via = params.get('via') || params.get('source') || params.get('url')
        if (via) {
          try { return new URL(via).hostname.replace('www.', '') } catch {}
        }
        // Fall back to stripping the long hash and showing a clean label
        const parts = parsed.pathname.split('/')
        // Last meaningful segment may hint at source
        return '🔗 Grounded Source'
      }
      return parsed.hostname.replace('www.', '')
    } catch {
      return url
    }
  }

  function goBack() {
    history.pushState({}, '', '/admin/scandals'); window.dispatchEvent(new PopStateEvent('popstate'))
  }
</script>

<div class="fade-in space-y-6">
  <!-- Header -->
  <div class="flex items-center gap-4">
    <button 
      onclick={goBack} 
      class="flex h-10 w-10 items-center justify-center rounded-xl bg-glass text-text-secondary transition-colors hover:bg-glass-hover hover:text-text-primary"
      aria-label="Go back"
    >
      <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
      </svg>
    </button>
    <div>
      <h1 class="text-3xl font-semibold tracking-tight text-text-primary">{artistName} Scandals</h1>
      <p class="mt-1 text-sm text-text-secondary">
        Review specific AI-detected scandals
      </p>
    </div>
  </div>

  <!-- Scandal List -->
  {#if loading}
    <div class="flex items-center justify-center py-20">
      <div class="spinner"></div>
    </div>
  {:else if scandals.length === 0}
    <div class="glass py-16 text-center">
      <p class="text-lg text-text-secondary">No scandals found for this artist</p>
    </div>
  {:else}
    <div class="grid grid-cols-1 gap-4 xl:grid-cols-2 content-start">
      {#each scandals as scandal (scandal.id)}
        <div class="glass p-6">
          <!-- Header row -->
          <div class="flex items-start justify-between gap-4">
            <div class="flex-1">
              {#if scandal.title}
                <h3 class="text-lg font-semibold text-text-primary">{scandal.title}</h3>
              {/if}
              <div class="mt-1 flex items-center gap-3">
                <span class="badge {scandal.verified ? 'badge-success' : 'badge-warning'}">
                  {scandal.verified ? '✓ Verified' : '⏳ Unverified'}
                </span>
              </div>
              <p class="mt-1 text-xs text-text-tertiary">
                Detected: {formatDate(scandal.date_detected)}
              </p>
            </div>
          </div>

          <!-- Description -->
          <p class="mt-4 leading-relaxed text-text-secondary">
            {scandal.description}
          </p>

          <!-- Sources -->
          {#if scandal.sources && scandal.sources.length > 0}
            <div class="mt-4 space-y-2">
              <p class="text-xs font-medium uppercase tracking-wider text-text-tertiary">
                Sources
              </p>
              {#each scandal.sources as source}
                <div class="flex flex-col sm:flex-row items-start sm:items-center gap-2 group/source">
                  <a
                    href={source.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="group/link flex flex-1 w-full items-center gap-2 rounded-xl border px-4 py-2.5 text-sm no-underline transition-all overflow-hidden
                      {source.is_reported ? 'border-danger/50 bg-danger-glow/30 text-danger' : 
                       (!source.is_verified ? 'border-warning/30 bg-warning/5 text-text-tertiary hover:border-warning/50 hover:bg-warning/10' : 
                       'border-glass-border text-text-secondary hover:border-glass-border-hover hover:bg-glass hover:text-text-primary')}"
                  >
                    <span class="{source.is_reported ? 'text-danger' : 'text-text-tertiary'} transition-colors group-hover/link:text-text-secondary flex-shrink-0 mt-0.5">
                      ↗
                    </span>
                    <span class="break-all">
                      {source.source_title || formatSourceLabel(source.source_url)}
                      {#if source.is_reported}
                        <span class="ml-2 font-bold uppercase text-[10px] text-danger bg-danger/10 px-1.5 py-0.5 rounded">Reported</span>
                      {:else if !source.is_verified}
                        <span class="ml-2 font-bold uppercase text-[10px] text-warning bg-warning/10 border border-warning/20 px-1.5 py-0.5 rounded">Unverified</span>
                      {/if}
                    </span>
                  </a>
                  <button
                    class="flex items-center justify-center w-10 h-10 rounded-xl border border-glass-border text-lg transition-all hover:bg-glass flex-shrink-0 cursor-pointer"
                    title={source.is_verified ? 'Unverify Source' : 'Verify Source manually'}
                    onclick={() => toggleSourceVerification(scandal, source)}
                  >
                    {#if source.is_reported}
                      ⚠️
                    {:else if source.is_verified}
                      <span title="Verified by Gemini">✅</span>
                    {:else}
                      <span title="Unverified Source" class="opacity-50 grayscale hover:grayscale-0 transition-all">❓</span>
                    {/if}
                  </button>
                  <button
                    class="flex items-center gap-2 px-3 py-2.5 rounded-xl border border-glass-border text-xs font-medium text-text-tertiary transition-all hover:border-danger hover:bg-danger-glow hover:text-danger flex-shrink-0"
                    title="Remove incorrect source"
                    onclick={() => removeSource(scandal, source)}
                  >
                    <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    <span class="sm:hidden">Remove Source</span>
                  </button>
                </div>
              {/each}
            </div>
          {:else}
            <div class="mt-4 rounded-xl border border-dashed border-glass-border p-4 text-center">
              <p class="text-sm text-text-tertiary italic">No sources added to this scandal yet.</p>
            </div>
          {/if}

          <!-- Admin: Add Source -->
          <div class="mt-3">
            {#if addSourceScandalId === scandal.id}
              <form class="flex gap-2" onsubmit={(e) => { e.preventDefault(); handleAddSource(scandal.id); }}>
                <input
                  type="url"
                  bind:value={addSourceUrl}
                  required
                  placeholder="https://..."
                  class="flex-1 rounded-xl border border-glass-border bg-bg-secondary/50 px-4 py-2 text-sm text-text-primary focus:border-glass-border-hover focus:outline-none"
                />
                <button type="submit" disabled={isAddingSource} class="btn-spotify px-4 py-2 text-xs shrink-0">
                  {isAddingSource ? 'Adding...' : 'Add'}
                </button>
                <button type="button" onclick={() => { addSourceScandalId = null; addSourceUrl = "" }} class="px-3 py-2 rounded-xl border border-glass-border text-xs text-text-tertiary hover:text-text-primary transition-colors cursor-pointer shrink-0">
                  Cancel
                </button>
              </form>
            {:else}
              <button
                onclick={() => addSourceScandalId = scandal.id}
                class="text-xs font-medium text-text-tertiary hover:text-spotify transition-colors cursor-pointer"
              >
                + Add Source
              </button>
            {/if}
          </div>

          <!-- Actions -->
          <div class="mt-4 flex gap-2 border-t border-glass-border pt-4">
            <button
              class="btn-outline px-4 py-2 text-xs {scandal.verified ? 'border-warning text-warning' : 'border-success text-success'}"
              onclick={() => toggleVerification(scandal)}
            >
              {scandal.verified ? '✗ Unverify' : '✓ Verify Scandal'}
            </button>
            <button
              class="btn-outline border-danger px-4 py-2 text-xs text-danger"
              onclick={() => removeScandal(scandal)}
            >
              Delete
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
