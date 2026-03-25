<script>
  import { submitCommunityScandal } from './api.js'
  import { showToast, spotifyUser } from './stores.js'

  let { artistId, onClose } = $props()

  let communityTitle = $state("")
  let communityDesc = $state("")
  let communitySources = $state([""])
  let isSubmitting = $state(false)

  async function handleSubmit() {
    isSubmitting = true
    try {
      const validSources = communitySources.filter(s => s.trim() !== "")
      const joinedSources = validSources.join("\n")
      await submitCommunityScandal(artistId, communityTitle, communityDesc, joinedSources)
      showToast('success', 'Thanks for the tip! Sent to admins for review.')
      onClose()
    } catch (e) {
      if (e.message.includes('429')) {
        showToast('error', 'Rate limit exceeded. Try again later.')
      } else {
        showToast('error', `Failed to submit: ${e.message}`)
      }
    } finally {
      isSubmitting = false
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 px-4 backdrop-blur-sm" onclick={onClose}>
  <div 
    class="glass relative w-full max-w-lg rounded-2xl p-6 sm:p-8 overflow-hidden" 
    onclick={(e) => e.stopPropagation()}
  >
    <button 
      class="absolute right-4 top-4 text-text-tertiary hover:text-text-primary"
      onclick={onClose}
      aria-label="Close popup"
    >
      <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>
    
    <h2 class="text-xl font-bold text-text-primary mb-2">Submit a Scandal</h2>
    <p class="text-sm text-text-secondary mb-6">Know something we missed? Submit it below for review.</p>
    
    {#if !$spotifyUser}
      <div class="flex flex-col items-center justify-center py-6 text-center border border-glass-border rounded-xl bg-bg-secondary/50">
        <p class="text-sm text-text-secondary mb-4">To prevent spam, you must be logged into Spotify to submit.</p>
        <a href="/api/public/auth/spotify/login" class="btn-spotify flex items-center justify-center gap-2 no-underline">
          <div class="h-5 w-5 rounded-full bg-black/20 flex items-center justify-center text-black font-bold text-[10px]">S</div>
          <span>Login with Spotify</span>
        </a>
      </div>
    {:else}
      <form class="space-y-4" onsubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
        <div>
          <label for="community-title" class="mb-1 block text-xs font-medium text-text-tertiary uppercase tracking-wider">Title</label>
          <input 
            id="community-title"
            type="text" 
            bind:value={communityTitle} 
            required 
            maxlength="100"
            class="w-full rounded-xl border border-glass-border bg-bg-secondary/50 px-4 py-2.5 text-sm text-text-primary focus:border-glass-border-hover focus:outline-none"
            placeholder="e.g. Controversial Interview"
          />
        </div>
        <div>
          <label for="community-desc" class="mb-1 block text-xs font-medium text-text-tertiary uppercase tracking-wider">Description</label>
          <textarea 
            id="community-desc"
            bind:value={communityDesc} 
            required 
            maxlength="500"
            rows="4"
            class="w-full rounded-xl border border-glass-border bg-bg-secondary/50 px-4 py-2.5 text-sm text-text-primary focus:border-glass-border-hover focus:outline-none resize-none"
            placeholder="Provide a brief summary of the scandal..."
          ></textarea>
        </div>
        <div>
          <div class="flex items-center justify-between mb-1">
            <label for="community-source-0" class="block text-xs font-medium text-text-tertiary uppercase tracking-wider">Source URLs (Optional)</label>
            <button 
              type="button" 
              onclick={() => communitySources.push('')} 
              class="text-xs text-text-tertiary hover:text-text-primary transition-colors flex items-center gap-1 cursor-pointer"
            >
              <svg class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
              Add another source
            </button>
          </div>
          
          <div class="space-y-2">
            {#each communitySources as source, index}
              <div class="flex gap-2">
                <input 
                  id="community-source-{index}"
                  type="url" 
                  bind:value={communitySources[index]} 
                  class="w-full rounded-xl border border-glass-border bg-bg-secondary/50 px-4 py-2.5 text-sm text-text-primary focus:border-glass-border-hover focus:outline-none"
                  placeholder="https://..."
                />
                {#if communitySources.length > 1}
                  <button 
                    type="button" 
                    onclick={() => communitySources.splice(index, 1)} 
                    class="shrink-0 flex items-center justify-center w-10 border border-glass-border rounded-xl text-text-tertiary hover:border-danger hover:text-danger hover:bg-danger-glow transition-all cursor-pointer"
                    aria-label="Remove source"
                  >
                    <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                  </button>
                {/if}
              </div>
            {/each}
          </div>
        </div>
        
        <button 
          type="submit" 
          disabled={isSubmitting}
          class="btn-spotify w-full mt-4 flex justify-center items-center gap-2"
        >
          {#if isSubmitting}
            <span class="spinner w-4 h-4 border-black border-t-transparent"></span>
            Submitting...
          {:else}
            Submit for Review
          {/if}
        </button>
      </form>
    {/if}
  </div>
</div>
