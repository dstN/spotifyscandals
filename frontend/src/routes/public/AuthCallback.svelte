<script>
  import { onMount } from 'svelte'
  import { publicToken, showToast } from '../../lib/stores.js'

  let error = $state(null)
  
  onMount(() => {
    // URL format: /#/auth/callback?token=... or /#/auth/error?message=...
    const hash = window.location.hash.slice(1) // "/auth/callback?token=xyz"
    const [path, queryString] = hash.split('?')
    const params = new URLSearchParams(queryString || '')

    if (path === '/auth/error') {
      error = params.get('message') || 'Unknown authentication error'
      showToast('error', `Login failed: ${error}`)
      setTimeout(() => {
        window.location.hash = '#/'
      }, 3000)
    } else if (path === '/auth/callback') {
      const token = params.get('token')
      if (token) {
        publicToken.set(token)
        showToast('success', 'Logged in with Spotify!')
        window.location.hash = '#/'
      } else {
        error = 'No token received from Spotify'
        showToast('error', error)
        setTimeout(() => {
          window.location.hash = '#/'
        }, 3000)
      }
    }
  })
</script>

<div class="flex min-h-screen items-center justify-center p-4">
  <div class="glass w-full max-w-sm p-8 text-center fade-in">
    <div class="mb-6 flex justify-center">
      <div class="flex h-16 w-16 items-center justify-center rounded-2xl bg-spotify text-2xl font-bold text-black shadow-lg shadow-spotify-glow">S</div>
    </div>
    
    {#if error}
      <h2 class="text-xl font-bold text-text-primary mb-2">Login Failed</h2>
      <p class="text-text-secondary text-sm">{error}</p>
      <div class="mt-6 flex justify-center">
        <a href="#/" class="btn-primary" onclick={(e) => { e.preventDefault(); window.location.hash = '#/'; }}>Return Home</a>
      </div>
    {:else}
      <h2 class="text-xl font-bold text-text-primary mb-2">Authenticating</h2>
      <p class="text-text-secondary text-sm">Finishing Spotify connection...</p>
      <div class="mt-8 flex justify-center">
        <div class="spinner"></div>
      </div>
    {/if}
  </div>
</div>
