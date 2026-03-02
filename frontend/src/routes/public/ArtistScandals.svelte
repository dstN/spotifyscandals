<script>
  import { onMount } from 'svelte'
  import { fetchArtist, fetchScandals, submitScandalVote, submitCommunityScandal, reportScandalSource } from '../../lib/api.js'
  import { showToast, spotifyUser, publicToken } from '../../lib/stores.js'

  let { params } = $props()
  
  let artist = $state(null)
  let scandals = $state([])
  let loading = $state(true)
  let expandedScandal = $state(null)

  async function loadData() {
    loading = true
    try {
      const artistId = parseInt(params.id, 10)
      artist = await fetchArtist(artistId)
      // Only fetch verified scandals for the public view
      scandals = await fetchScandals({ artist_id: artistId, verified: true })
    } catch (e) {
      showToast('error', `Failed to load artist: ${e.message}`)
    } finally {
      loading = false
    }
  }

  onMount(() => {
    loadData()
  })

  function formatDate(dateStr) {
    if (!dateStr) return 'Unknown'
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  function getSeverityColor(score, isPercentage = false) {
    // If percentage (Safety Score), 100 is green, 0 is red.
    // If not percentage (Scandal 1-10), 1 is green, 10 is red.
    let normalized = isPercentage ? (100 - score) / 100 : (score - 1) / 9;
    
    // Gradient from Green -> Yellow -> Orange -> Red
    if (normalized < 0.25) return 'text-green-500';
    if (normalized < 0.5) return 'text-yellow-400';
    if (normalized < 0.75) return 'text-orange-500';
    return 'text-red-500';
  }

  let votingState = $state({}); // Track loading state for each scandal vote
  let voteValues = $state({}); // Track slider values live while dragging

  async function handleVote(scandalId, voteValue) {
    if (!voteValue || voteValue < 1 || voteValue > 10) return;
    
    votingState[scandalId] = true;
    try {
      const response = await submitScandalVote(scandalId, voteValue);
      showToast('success', 'Vote recorded successfully');
      
      // Update local state to reflect the new vote and average
      const sIndex = scandals.findIndex(s => s.id === scandalId);
      if (sIndex !== -1) {
        scandals[sIndex] = {
          ...scandals[sIndex],
          user_vote: response.user_vote,
          average_vote: response.average_vote,
          vote_count: response.vote_count
        };
      }
      
      // We should ideally reload the artist to get the updated safety score
      // or calculate it locally. For simplicity, we'll reload.
      artist = await fetchArtist(parseInt(params.id, 10));
      
    } catch (e) {
      if (e.message.includes('401')) {
        showToast('error', 'Please login with Spotify to vote');
      } else {
        showToast('error', `Failed to submit vote: ${e.message}`);
      }
    } finally {
      votingState[scandalId] = false;
    }
  }

  function handlePublicLogout() {
    publicToken.set(null);
    showToast('info', 'Logged out of Spotify');
  }

  let showCommunityPopup = $state(false)
  let communityTitle = $state("")
  let communityDesc = $state("")
  let communitySources = $state([""])
  let isSubmittingCommunity = $state(false)

  async function handleCommunitySubmit() {
    isSubmittingCommunity = true
    try {
      const validSources = communitySources.filter(s => s.trim() !== "")
      const joinedSources = validSources.join("\n")
      await submitCommunityScandal(artist.id, communityTitle, communityDesc, joinedSources)
      showToast('success', 'Thanks for the tip! Sent to admins for review.')
      showCommunityPopup = false
      communityTitle = ""
      communityDesc = ""
      communitySources = [""]
    } catch (e) {
      if (e.message.includes('429')) {
        showToast('error', 'Rate limit exceeded. Try again later.')
      } else {
        showToast('error', `Failed to submit: ${e.message}`)
      }
    } finally {
      isSubmittingCommunity = false
    }
  }
</script>

<div class="mx-auto max-w-3xl pt-8 pb-20 relative">
  <!-- Public Auth Header -->
  <div class="absolute top-4 right-0 flex items-center gap-4 z-20">
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

  <div class="mb-8 pt-6">
    <a href="#/" class="text-sm font-medium text-text-tertiary transition-colors hover:text-text-primary">
      &larr; Back to Search
    </a>
  </div>

  {#if loading}
    <div class="flex py-20 justify-center">
      <div class="spinner w-8 h-8"></div>
    </div>
  {:else if !artist}
    <div class="glass py-16 text-center">
      <p class="text-xl text-text-secondary">Artist not found</p>
    </div>
  {:else}
    <!-- Artist Header -->
    <div class="glass mb-8 flex flex-col items-center gap-6 p-8 sm:flex-row sm:items-start text-center sm:text-left relative overflow-hidden">
      <!-- Background blur of the artist cover -->
      <div 
        class="absolute inset-0 opacity-10 bg-cover bg-center blur-2xl transform scale-110"
        style="background-image: url('{artist.image_url}')"
      ></div>
      
      <img
        src={artist.image_url || 'https://misc.scdn.co/liked-songs/liked-songs-300.png'}
        alt="{artist.name} cover"
        class="h-32 w-32 shrink-0 rounded-full object-cover shadow-2xl relative z-10"
      />
      <div class="relative z-10 flex-1">
        <h1 class="text-4xl font-bold tracking-tight text-text-primary mb-2">
          {artist.name}
        </h1>
        <div class="flex flex-col gap-3 items-center sm:items-start text-left">
          <a
            href={`https://open.spotify.com/artist/${artist.spotify_id}`}
            target="_blank"
            rel="noopener noreferrer"
            class="btn-spotify flex items-center justify-center gap-2 no-underline py-1.5 px-4 text-xs shadow-none w-max"
          >
            <svg class="h-4 w-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg>
            Open in Spotify
          </a>
          
          <div class="flex flex-wrap justify-center sm:justify-start items-center gap-3">
            <span class="text-xs font-medium text-text-tertiary">
              {scandals.length} verified scandal{scandals.length === 1 ? '' : 's'}
            </span>
            <div class="h-3 w-px bg-glass-border"></div>
            <button 
              onclick={() => showCommunityPopup = true}
              class="text-xs font-medium text-text-tertiary transition-colors hover:text-spotify cursor-pointer"
            >
              Did we miss a scandal?
            </button>
          </div>
        </div>
      </div>
      
      <!-- Safety Score Meter (Moved to Right) -->
      {#if artist.safety_score !== null && artist.safety_score !== undefined}
        <div class="relative z-10 flex flex-col items-center sm:items-end mt-6 sm:mt-0 p-4 bg-bg-primary/50 sm:bg-transparent rounded-2xl border sm:border-0 border-glass-border">
          <span class="text-[10px] font-bold uppercase tracking-widest text-text-tertiary mb-1">Safety Score</span>
          <div class="flex items-baseline gap-2">
            <span class={`text-3xl font-black ${getSeverityColor(artist.safety_score, true)}`}>
              {Math.round(artist.safety_score)}%
            </span>
            <span class="text-sm text-text-secondary font-medium uppercase">Safe to listen</span>
          </div>
          <p class="text-[10px] text-text-tertiary mt-1 sm:text-right">Based on aggregated severity votes</p>
        </div>
      {/if}
    </div>

    <!-- Scandals List -->
    {#if scandals.length === 0}
      <div class="glass py-12 text-center">
        <p class="text-lg text-text-secondary">No verified scandals found for this artist.</p>
        <p class="mt-2 text-sm text-text-tertiary">Clean record... for now.</p>
      </div>
    {:else}
      <div class="space-y-4">
        {#each scandals as scandal (scandal.id)}
          <div class="glass overflow-hidden transition-all duration-300">
            <!-- Accordion Header -->
            <button 
              onclick={() => expandedScandal = expandedScandal === scandal.id ? null : scandal.id}
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
                    class="h-5 w-5 transition-transform duration-300 {expandedScandal === scandal.id ? 'rotate-180 text-spotify shadow-spotify-glow' : ''}" 
                    fill="none" 
                    viewBox="0 0 24 24" 
                    stroke="currentColor" 
                    stroke-width="2"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </div>
            </button>
            
            <!-- Accordion Content -->
            {#if expandedScandal === scandal.id}
              <div class="p-6 sm:p-8 pt-0 border-t border-glass-border/30 mt-2">
                <p class="text-text-secondary leading-relaxed mb-8 text-lg">
                  {scandal.description}
                </p>

                <!-- Full Width Voting Area -->
                <div class="mb-8 bg-bg-secondary/60 p-6 rounded-2xl border border-glass-border relative overflow-hidden shadow-inner">
                  <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-green-500 via-orange-500 to-red-500 opacity-20"></div>
                  
                  {#if $spotifyUser}
                    <div class="w-full flex flex-col gap-4">
                      <div class="flex justify-between items-end text-sm uppercase font-bold text-text-tertiary mb-1">
                        <span class="text-green-500 tracking-wider">Mild</span>
                        
                        <div class="flex flex-col items-center justify-end">
                          <span class="text-[10px] text-text-tertiary mb-1">Severity Rating</span>
                          <span class={`text-3xl font-black leading-none ${getSeverityColor(voteValues[scandal.id] || scandal.user_vote || 5)}`}>
                            {voteValues[scandal.id] || scandal.user_vote || 5}
                          </span>
                        </div>
                        
                        <span class="text-red-500 tracking-wider">Cancel</span>
                      </div>
                      
                      <input 
                        type="range" 
                        min="1" 
                        max="10" 
                        step="1" 
                        value={voteValues[scandal.id] || scandal.user_vote || 5} 
                        disabled={votingState[scandal.id]}
                        oninput={(e) => { voteValues[scandal.id] = parseInt(e.target.value); }}
                        onchange={(e) => handleVote(scandal.id, parseInt(e.target.value))}
                        class="w-full h-3 bg-glass-border rounded-lg appearance-none cursor-pointer accent-text-primary"
                      />
                      
                      <div class="flex justify-between items-center mt-2">
                        {#if scandal.user_vote}
                          <span class="text-sm text-accent font-medium bg-accent/10 px-3 py-1 rounded-full">Your vote: {scandal.user_vote}</span>
                        {:else}
                          <span class="text-sm text-text-tertiary font-medium">Slide to cast your vote</span>
                        {/if}
                        {#if votingState[scandal.id]}
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
                              {source.source_url.includes('vertexaisearch') ? 'Google Search Grounding Result' : source.source_url}
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
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>

<!-- Community Scandal Popup -->
{#if showCommunityPopup}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 px-4 backdrop-blur-sm" onclick={() => showCommunityPopup = false}>
    <div 
      class="glass relative w-full max-w-lg rounded-2xl p-6 sm:p-8 overflow-hidden" 
      onclick={(e) => e.stopPropagation()}
    >
      <button 
        class="absolute right-4 top-4 text-text-tertiary hover:text-text-primary"
        onclick={() => showCommunityPopup = false}
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
        <form class="space-y-4" onsubmit={(e) => { e.preventDefault(); handleCommunitySubmit(); }}>
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
            disabled={isSubmittingCommunity}
            class="btn-spotify w-full mt-4 flex justify-center items-center gap-2"
          >
            {#if isSubmittingCommunity}
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
{/if}
