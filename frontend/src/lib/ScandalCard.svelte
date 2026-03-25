<script>
  import { submitScandalVote, reportScandalSource, submitCommunitySource } from './api.js'
  import { showToast, spotifyUser } from './stores.js'

  let { scandal, expanded = false, onToggle, onVoteComplete } = $props()

  let votingLoading = $state(false)
  let voteOverride = $state(null)
  let voteValue = $derived(voteOverride ?? scandal.user_vote ?? 5)

  let sourceSubmitActive = $state(false)
  let sourceSubmitUrl = $state("")
  let isSubmittingSource = $state(false)

  function formatDate(dateStr) {
    if (!dateStr) return 'Unknown'
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  function getSeverityColor(score) {
    let normalized = (score - 1) / 9
    if (normalized < 0.25) return 'text-green-500'
    if (normalized < 0.5) return 'text-yellow-400'
    if (normalized < 0.75) return 'text-orange-500'
    return 'text-red-500'
  }

  function formatSourceLabel(url) {
    if (!url) return ''
    try {
      const parsed = new URL(url)
      if (parsed.hostname.includes('vertexaisearch')) return '🔗 Grounded Source'
      return parsed.hostname.replace('www.', '')
    } catch {
      return url
    }
  }

  async function handleVote(newValue) {
    if (newValue == null || newValue < 0 || newValue > 10) return
    votingLoading = true
    try {
      const response = await submitScandalVote(scandal.id, newValue)
      showToast('success', 'Vote recorded successfully')
      scandal.user_vote = response.user_vote
      scandal.average_vote = response.average_vote
      scandal.vote_count = response.vote_count
      onVoteComplete?.()
    } catch (e) {
      if (e.message.includes('401')) {
        showToast('error', 'Please login with Spotify to vote')
      } else {
        showToast('error', `Failed to submit vote: ${e.message}`)
      }
    } finally {
      votingLoading = false
    }
  }

  async function handleSourceSubmit() {
    if (!sourceSubmitUrl.trim()) return
    isSubmittingSource = true
    try {
      await submitCommunitySource(scandal.id, sourceSubmitUrl.trim())
      showToast('success', 'Source submitted for review. Thanks!')
      sourceSubmitActive = false
      sourceSubmitUrl = ""
    } catch (e) {
      if (e.message.includes('401')) {
        showToast('error', 'Please login with Spotify to submit sources')
      } else {
        showToast('error', `Failed to submit source: ${e.message}`)
      }
    } finally {
      isSubmittingSource = false
    }
  }
</script>

<div class="glass overflow-hidden transition-all duration-300">
  <!-- Accordion Header -->
  <button 
    onclick={onToggle}
    class="group relative w-full flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 p-6 sm:p-8 text-left transition-all duration-300"
  >
    <div class="flex-1 w-full">
      <h3 class="text-2xl font-semibold text-text-primary mb-2 pr-4 transition-colors group-hover:text-spotify">
        {scandal.title || 'Untitled Scandal'}
      </h3>
      <p class="text-sm text-text-tertiary mb-2">
        Discovered: {formatDate(scandal.date_detected)}
      </p>
      {#if scandal.is_community}
        <span class="badge bg-glass text-[10px] text-text-tertiary border border-glass-border px-2 py-0.5 w-max">
          👥 Community Tip
        </span>
      {/if}
    </div>
    
    <div class="flex flex-col w-full sm:w-auto mt-4 sm:mt-0 items-start sm:items-end gap-1">
      <div class="flex items-center justify-between sm:justify-end gap-6 w-full sm:w-auto">
        <span class="flex flex-col items-start sm:items-end">
          <span class="text-[10px] font-bold uppercase tracking-widest text-text-tertiary mb-1">Average Severity</span>
          {#if scandal.average_vote !== null}
            <span class="flex items-baseline gap-1">
              <span class={`text-4xl font-black transition-transform group-hover:scale-105 ${getSeverityColor(scandal.average_vote)}`}>
                {scandal.average_vote.toFixed(1)}
              </span>
              <span class="text-text-secondary text-sm">/10</span>
            </span>
          {:else}
            <span class="text-xs font-medium text-text-secondary bg-bg-primary px-3 py-1.5 rounded-lg mt-1 border border-glass-border">No votes yet</span>
          {/if}
        </span>
        
        <!-- Animated Chevron -->
        <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-bg-primary/50 border border-glass-border text-text-tertiary transition-all duration-300 group-hover:bg-glass-hover group-hover:text-white group-hover:border-glass-border-hover">
          <svg 
            class="h-5 w-5 transition-transform duration-300 {expanded ? 'rotate-180 text-spotify shadow-spotify-glow' : ''}" 
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor" 
            stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
    </div>
  </button>
  
  <!-- Accordion Content -->
  {#if expanded}
    <div class="p-6 sm:p-8 pt-0 border-t border-glass-border/30 mt-2">
      <p class="text-text-secondary leading-relaxed mb-8 text-lg">
        {scandal.description}
      </p>

      <!-- Voting Area -->
      <div class="mb-8 bg-bg-secondary/60 p-6 rounded-2xl border border-glass-border relative overflow-hidden shadow-inner">
        <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-green-500 via-orange-500 to-red-500 opacity-20"></div>
        
        {#if $spotifyUser}
          <div class="w-full flex flex-col gap-4">
            <div class="flex justify-between items-end text-sm uppercase font-bold text-text-tertiary mb-1">
              <span class="text-green-500 tracking-wider">Mild</span>
              
              <div class="flex flex-col items-center justify-end">
                <span class="text-[10px] text-text-tertiary mb-1">Severity Rating</span>
                <span class={`text-3xl font-black leading-none ${getSeverityColor(voteValue)}`}>
                  {voteValue}
                </span>
              </div>
              
              <span class="text-red-500 tracking-wider">Cancel</span>
            </div>
            
            <input 
              type="range" 
              min="0" 
              max="10" 
              step="1" 
              value={voteValue}
              disabled={votingLoading}
              oninput={(e) => { voteOverride = parseInt(e.target.value); }}
              onchange={(e) => handleVote(parseInt(e.target.value))}
              class="w-full h-3 bg-glass-border rounded-lg appearance-none cursor-pointer accent-text-primary"
            />
            
            <div class="flex justify-between items-center mt-2">
              {#if scandal.user_vote != null}
                <span class="text-sm text-accent font-medium bg-accent/10 px-3 py-1 rounded-full">Your vote: {scandal.user_vote}</span>
              {:else}
                <span class="text-sm text-text-tertiary font-medium">Slide to cast your vote</span>
              {/if}
              {#if votingLoading}
                <div class="flex items-center gap-2">
                  <span class="spinner w-4 h-4"></span>
                  <span class="text-xs text-text-tertiary">Saving...</span>
                </div>
              {/if}
            </div>
          </div>
        {:else}
          <div class="flex flex-col items-center justify-center py-4 text-center">
            <p class="text-lg font-medium text-text-primary mb-1">Have an opinion on this?</p>
            <p class="text-sm text-text-secondary mb-4">Login via Spotify to grade the severity of this scandal.</p>
            <a href="/api/public/auth/spotify/login" class="btn-spotify flex items-center justify-center gap-2 no-underline shadow-none">
              <div class="h-5 w-5 rounded-full bg-black/20 flex items-center justify-center text-black font-bold text-[10px]">S</div>
              <span>Login to Vote</span>
            </a>
          </div>
        {/if}
      </div>

      {#if scandal.sources && scandal.sources.filter(s => s.is_verified).length > 0}
        <div class="space-y-3">
          <h4 class="text-xs font-bold uppercase tracking-widest text-text-tertiary">
            Sources & References
          </h4>
          <div class="flex flex-col gap-2">
            {#each scandal.sources.filter(s => s.is_verified) as source}
              <div class="flex items-center gap-2 group/source">
                <a
                  href={source.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  class="group/link flex items-start gap-3 rounded-xl border border-glass-border px-4 py-3 text-sm text-text-secondary no-underline transition-all hover:border-glass-border-hover hover:bg-glass hover:text-text-primary flex-1 min-w-0"
                >
                  <span class="text-text-tertiary transition-colors group-hover/link:text-text-secondary mt-0.5 shrink-0">↗</span>
                  <span class="break-all pr-4 flex-1">
                    {source.source_title || formatSourceLabel(source.source_url)}
                  </span>
                </a>
                {#if !source.is_reported}
                  <button
                    class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-glass-border text-text-tertiary transition-all hover:border-danger hover:bg-danger-glow hover:text-danger cursor-pointer"
                    title="Report as wrong source"
                    onclick={async () => {
                      try {
                        await reportScandalSource(scandal.id, source.id)
                        source.is_reported = true
                        showToast('success', 'Source reported. Thanks for helping!')
                      } catch (e) {
                        showToast('error', `Report failed: ${e.message}`)
                      }
                    }}
                  >
                    <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  </button>
                {:else}
                  <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-danger-glow text-danger border border-danger/30" title="Source reported">
                    <svg class="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                    </svg>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Submit a Source -->
      <div class="mt-4 pt-4 border-t border-glass-border/30">
        {#if sourceSubmitActive}
          {#if $spotifyUser}
            <form class="flex gap-2" onsubmit={(e) => { e.preventDefault(); handleSourceSubmit(); }}>
              <input
                type="url"
                bind:value={sourceSubmitUrl}
                required
                placeholder="https://..."
                class="flex-1 rounded-xl border border-glass-border bg-bg-secondary/50 px-4 py-2 text-sm text-text-primary focus:border-glass-border-hover focus:outline-none"
              />
              <button type="submit" disabled={isSubmittingSource} class="btn-spotify px-4 py-2 text-xs shrink-0">
                {isSubmittingSource ? 'Sending...' : 'Submit'}
              </button>
              <button type="button" onclick={() => { sourceSubmitActive = false; sourceSubmitUrl = "" }} class="px-3 py-2 rounded-xl border border-glass-border text-xs text-text-tertiary hover:text-text-primary transition-colors cursor-pointer shrink-0">
                Cancel
              </button>
            </form>
          {:else}
            <div class="flex items-center gap-3">
              <p class="text-sm text-text-secondary">Login to submit a source.</p>
              <a href="/api/public/auth/spotify/login" class="btn-spotify text-xs px-3 py-1.5 no-underline flex items-center gap-1">
                <span>Login</span>
              </a>
            </div>
          {/if}
        {:else}
          <button
            onclick={() => sourceSubmitActive = true}
            class="text-xs font-medium text-text-tertiary hover:text-spotify transition-colors cursor-pointer"
          >
            + Submit a source for this scandal
          </button>
        {/if}
      </div>
    </div>
  {/if}
</div>
