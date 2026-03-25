<script>
  import { onMount } from 'svelte'
  import { fetchArtistCommunityScandals, verifyCommunityScandal, rejectCommunityScandal } from '../lib/api.js'
  import { showToast } from '../lib/stores.js'

  let { artistId } = $props()
  
  let submissions = $state([])
  let loading = $state(true)
  let reviewingId = $state(null)
  let reviewState = $state({ title: '', description: '', sources: [''] })
  let isSubmitting = $state(false)

  async function loadData() {
    loading = true
    try {
      submissions = await fetchArtistCommunityScandals(artistId)
    } catch (e) {
      showToast('error', `Failed to load submissions: ${e.message}`)
    } finally {
      loading = false
    }
  }

  onMount(() => {
    loadData()
  })

  function startReview(sub) {
    reviewingId = sub.id
    // Parse the multiple URLs we joined with \n earlier, if they exist
    let urls = ['']
    if (sub.source_url) {
      urls = sub.source_url.split('\n').map(s => s.trim()).filter(s => s)
      if (urls.length === 0) urls = ['']
    }
    
    reviewState = {
      title: sub.title,
      description: sub.description,
      sources: urls
    }
  }

  function cancelReview() {
    reviewingId = null
    reviewState = { title: '', description: '', sources: [''] }
  }

  async function handleVerify(sub) {
    isSubmitting = true
    try {
      const validSources = reviewState.sources.filter(s => s.trim() !== '')
      
      const payload = {
        title: reviewState.title,
        description: reviewState.description,
        source_urls: validSources
      }
      
      await verifyCommunityScandal(sub.id, payload)
      showToast('success', 'Submission verified and published as a Scandal!')
      
      // Remove it from the local list
      submissions = submissions.filter(s => s.id !== sub.id)
      cancelReview()
      
      // If no more submissions, kick them back to the summary screen
      if (submissions.length === 0) {
        window.location.hash = '#/admin/community'
      }
    } catch (e) {
      showToast('error', `Failed to verify: ${e.message}`)
    } finally {
      isSubmitting = false
    }
  }

  async function handleReject(sub) {
    if (!confirm('Are you sure you want to delete this community submission? This cannot be undone.')) return
    
    try {
      await rejectCommunityScandal(sub.id)
      showToast('success', 'Submission rejected and deleted.')
      submissions = submissions.filter(s => s.id !== sub.id)
      
      if (submissions.length === 0) {
        window.location.hash = '#/admin/community'
      }
    } catch (e) {
      showToast('error', `Failed to reject: ${e.message}`)
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
  <!-- Header Route Binding -->
  <div class="flex items-center gap-4">
    <a href="#/admin/community" class="flex h-10 w-10 items-center justify-center rounded-xl bg-glass text-text-secondary transition-colors hover:bg-glass-hover hover:text-text-primary no-underline" aria-label="Back to community inbox">
      <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
      </svg>
    </a>
    <div>
      <h1 class="text-3xl font-semibold tracking-tight text-text-primary flex items-center gap-3">
        {#if submissions.length > 0}
          <span>{submissions[0].artist.name}</span>
          <span class="badge badge-warning text-xs mt-1">{submissions.length} Pending</span>
        {:else}
          <span>Reviewing Artist</span>
        {/if}
      </h1>
      <p class="mt-1 text-sm text-text-secondary">
        Community Submissions Feed
      </p>
    </div>
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-20">
      <div class="spinner"></div>
    </div>
  {:else if submissions.length === 0}
    <div class="glass py-16 text-center mt-8">
      <p class="text-lg text-text-secondary">No pending submissions for this artist.</p>
      <a href="#/admin/community" class="mt-4 btn-outline inline-block text-sm no-underline">Return to Inbox</a>
    </div>
  {:else}
    <div class="grid grid-cols-1 gap-4 xl:grid-cols-2 content-start">
      {#each submissions as sub (sub.id)}
        <div class="glass p-6 {reviewingId === sub.id ? 'ring-2 ring-spotify shadow-spotify-glow' : ''}">
          
          {#if reviewingId !== sub.id}
            <!-- READ-ONLY VIEW -->
            <!-- Header row -->
            <div class="flex items-start justify-between gap-4">
              <div class="flex-1">
                <h3 class="text-lg font-semibold text-text-primary">{sub.title}</h3>
                <div class="mt-1 flex items-center gap-3">
                  <span class="badge badge-warning">
                    ⏳ Unverified
                  </span>
                </div>
                <p class="mt-1 text-xs text-text-tertiary">
                  Submitted by {sub.spotify_user_id.substring(0, 16)}... on {formatDate(sub.created_at)}
                </p>
              </div>
            </div>
            
            <!-- Description -->
            <p class="mt-4 leading-relaxed text-text-secondary whitespace-pre-wrap">
              {sub.description}
            </p>
            
            <!-- Sources -->
            {#if sub.source_url}
              <div class="mt-4 space-y-2">
                <p class="text-xs font-medium uppercase tracking-wider text-text-tertiary">
                  Sources
                </p>
                {#each sub.source_url.split('\n') as url}
                  {#if url.trim()}
                    <div class="flex flex-col sm:flex-row items-start sm:items-center gap-2 group/source">
                      <a href={url.trim()} target="_blank" rel="noopener noreferrer" class="group/link flex flex-1 w-full items-center gap-2 rounded-xl border border-glass-border px-4 py-2.5 text-sm text-text-secondary no-underline transition-all hover:border-glass-border-hover hover:bg-glass hover:text-text-primary overflow-hidden">
                        <span class="text-text-tertiary transition-colors group-hover/link:text-text-secondary flex-shrink-0">↗</span>
                        <span class="truncate">{formatSourceLabel(url.trim())}</span>
                      </a>
                    </div>
                  {/if}
                {/each}
              </div>
            {/if}

            <!-- Actions -->
            <div class="mt-4 flex gap-2 border-t border-glass-border pt-4">
              <button 
                class="btn-outline px-4 py-2 text-xs border-success text-success"
                onclick={() => startReview(sub)}
              >
                ✓ Review & Verify
              </button>
              <button 
                class="btn-outline border-danger px-4 py-2 text-xs text-danger"
                onclick={() => handleReject(sub)}
              >
                Reject
              </button>
            </div>
            
          {:else}
            <!-- EDIT / VERIFY VIEW -->
            <div class="flex items-start justify-between gap-4 mb-4">
              <div class="flex-1">
                <h3 class="text-lg font-semibold text-spotify flex items-center gap-2">
                  <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                  Edit Verification
                </h3>
                <p class="mt-1 text-xs text-text-tertiary">
                   Refine the generated submission before pushing it live.
                </p>
              </div>
            </div>
              
            <div class="space-y-4">
              <div>
                <label for="review-title" class="block text-xs font-medium text-text-tertiary uppercase tracking-wider mb-1">Title</label>
                <input id="review-title" type="text" bind:value={reviewState.title} class="input-glass w-full" />
              </div>
              
              <div>
                <label for="review-description" class="block text-xs font-medium text-text-tertiary uppercase tracking-wider mb-1">Description</label>
                <textarea id="review-description" bind:value={reviewState.description} rows="5" class="input-glass w-full resize-none leading-relaxed"></textarea>
              </div>
              
              <div>
                <div class="flex items-center justify-between mb-2">
                  <label for="review-source-0" class="block text-xs font-medium text-text-tertiary uppercase tracking-wider">Source URLs</label>
                  <button type="button" onclick={() => reviewState.sources.push('')} class="text-xs font-medium text-text-secondary hover:text-text-primary transition-colors cursor-pointer">
                    + Add Source
                  </button>
                </div>
                
                <div class="space-y-2">
                  {#each reviewState.sources as source, idx}
                    <div class="flex gap-2">
                      <input id="review-source-{idx}" type="url" bind:value={reviewState.sources[idx]} class="input-glass flex-1" placeholder="https://..." />
                      {#if reviewState.sources.length > 1}
                        <button type="button" onclick={() => reviewState.sources.splice(idx, 1)} class="flex items-center gap-2 px-3 rounded-xl border border-glass-border text-text-tertiary hover:border-danger hover:bg-danger-glow hover:text-danger cursor-pointer flex-shrink-0 transition-colors" aria-label="Remove source">
                          <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                        </button>
                      {/if}
                    </div>
                  {/each}
                </div>
              </div>
            </div>
            
            <div class="mt-6 flex gap-2 border-t border-glass-border pt-4">
              <button 
                onclick={cancelReview} 
                disabled={isSubmitting} 
                class="btn-outline px-4 py-2 text-xs"
              >
                Cancel
              </button>
              <button 
                onclick={() => handleVerify(sub)} 
                disabled={isSubmitting} 
                class="btn-spotify px-4 py-2 text-xs flex items-center gap-2"
              >
                {#if isSubmitting}
                  <div class="spinner w-3 h-3 border-black border-t-transparent"></div>
                  Publishing...
                {:else}
                  Publish Verified Scandal
                {/if}
              </button>
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>
