<script>
  import { onMount } from 'svelte'
  import { fetchPendingCommunitySources, approveCommunitySource, rejectCommunitySource } from '../lib/api.js'
  import { showToast } from '../lib/stores.js'

  let { artistName } = $props()
  
  let sources = $state([])
  let loading = $state(true)

  async function loadData() {
    loading = true
    try {
      const allSources = await fetchPendingCommunitySources()
      sources = allSources.filter(s => s.artist_name === artistName)
    } catch (e) {
      showToast('error', `Failed to load sources: ${e.message}`)
    } finally {
      loading = false
    }
  }

  onMount(loadData)

  async function handleApprove(source) {
    try {
      await approveCommunitySource(source.id)
      sources = sources.filter(s => s.id !== source.id)
      showToast('success', 'Source approved and added to scandal')
      
      if (sources.length === 0) {
        history.pushState({}, '', '/admin/community'); window.dispatchEvent(new PopStateEvent('popstate'))
      }
    } catch (e) {
      showToast('error', e.message)
    }
  }

  async function handleReject(source) {
    if (!confirm('Are you sure you want to reject this source? This cannot be undone.')) return
    
    try {
      await rejectCommunitySource(source.id)
      sources = sources.filter(s => s.id !== source.id)
      showToast('success', 'Source rejected and deleted.')
      
      if (sources.length === 0) {
        history.pushState({}, '', '/admin/community'); window.dispatchEvent(new PopStateEvent('popstate'))
      }
    } catch (e) {
      showToast('error', e.message)
    }
  }

  function formatDate(dateStr) {
    if (!dateStr) return 'Unknown'
    return new Date(dateStr).toLocaleString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit'
    })
  }

  function formatSourceLabel(url) {
    if (!url) return ''
    try {
      const parsed = new URL(url)
      return parsed.hostname.replace('www.', '')
    } catch {
      return url
    }
  }
</script>

<div class="fade-in space-y-6">
  <!-- Header -->
  <div class="flex items-center gap-4">
    <a href="/admin/community" class="flex h-10 w-10 items-center justify-center rounded-xl bg-glass text-text-secondary transition-colors hover:bg-glass-hover hover:text-text-primary no-underline" aria-label="Back to community inbox">
      <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
      </svg>
    </a>
    {#if sources.length > 0 && sources[0].artist_image_url}
      <div class="h-12 w-12 flex-shrink-0 overflow-hidden rounded-2xl bg-bg-tertiary">
        <img
          src={sources[0].artist_image_url}
          alt={artistName}
          class="h-full w-full object-cover"
        />
      </div>
    {/if}
    <div>
      <h1 class="text-3xl font-semibold tracking-tight text-text-primary flex items-center gap-3">
        <span>{artistName}</span>
        {#if sources.length > 0}
          <span class="badge badge-warning text-xs mt-1">{sources.length} Pending</span>
        {/if}
      </h1>
      <p class="mt-1 text-sm text-text-secondary">
        Community Source Submissions
      </p>
    </div>
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-20">
      <div class="spinner"></div>
    </div>
  {:else if sources.length === 0}
    <div class="glass py-16 text-center mt-8">
      <p class="text-lg text-text-secondary">No pending source submissions for this artist.</p>
      <a href="/admin/community" class="mt-4 btn-outline inline-block text-sm no-underline">Return to Inbox</a>
    </div>
  {:else}
    <div class="grid grid-cols-1 gap-4 xl:grid-cols-2 content-start">
      {#each sources as source (source.id)}
        <div class="glass p-6">
          <!-- Header row -->
          <div class="flex items-start justify-between gap-4">
            <div class="flex-1">
              <h3 class="text-lg font-semibold text-text-primary">{source.scandal_title || 'Untitled Scandal'}</h3>
              <div class="mt-1 flex items-center gap-3">
                <span class="badge badge-warning">
                  ⏳ Pending Review
                </span>
              </div>
              <p class="mt-1 text-xs text-text-tertiary">
                Submitted by {source.spotify_user_id.substring(0, 16)}... on {formatDate(source.created_at)}
              </p>
            </div>
          </div>
          
          <!-- Scandal Description -->
          <p class="mt-4 leading-relaxed text-text-secondary whitespace-pre-wrap">
            {source.scandal_description || 'No description available.'}
          </p>
          
          <!-- Existing Sources -->
          {#if source.existing_sources && source.existing_sources.length > 0}
            <div class="mt-4 space-y-2">
              <p class="text-xs font-medium uppercase tracking-wider text-text-tertiary">
                Current Sources
              </p>
              {#each source.existing_sources as existingSrc}
                <div class="flex flex-col sm:flex-row items-start sm:items-center gap-2">
                  <a href={existingSrc.source_url} target="_blank" rel="noopener noreferrer" class="group/link flex flex-1 w-full items-center gap-2 rounded-xl border border-glass-border px-4 py-2.5 text-sm text-text-secondary no-underline transition-all hover:border-glass-border-hover hover:bg-glass hover:text-text-primary overflow-hidden">
                    <span class="text-text-tertiary transition-colors group-hover/link:text-text-secondary flex-shrink-0">↗</span>
                    <span class="truncate">{existingSrc.source_title || formatSourceLabel(existingSrc.source_url)}</span>
                  </a>
                </div>
              {/each}
            </div>
          {/if}

          <!-- Proposed Source (highlighted) -->
          <div class="mt-4 space-y-2">
            <p class="text-xs font-medium uppercase tracking-wider text-spotify">
              Proposed New Source
            </p>
            <a href={source.source_url} target="_blank" rel="noopener noreferrer" class="group/link flex flex-1 w-full items-center gap-2 rounded-xl border border-spotify/30 bg-spotify/5 px-4 py-2.5 text-sm text-text-primary no-underline transition-all hover:border-spotify hover:bg-spotify/10 overflow-hidden">
              <span class="text-spotify flex-shrink-0">↗</span>
              <span class="truncate">{formatSourceLabel(source.source_url)}</span>
            </a>
          </div>

          <!-- Actions -->
          <div class="mt-4 flex gap-2 border-t border-glass-border pt-4">
            <button 
              class="btn-outline px-4 py-2 text-xs border-success text-success"
              onclick={() => handleApprove(source)}
            >
              ✓ Approve Source
            </button>
            <button 
              class="btn-outline border-danger px-4 py-2 text-xs text-danger"
              onclick={() => handleReject(source)}
            >
              Reject
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
