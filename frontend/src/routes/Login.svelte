<script>
  import { login } from '../lib/api.js'
  import { showToast } from '../lib/stores.js'

  let username = $state('')
  let password = $state('')
  let loading = $state(false)

  async function handleLogin(e) {
    e.preventDefault()
    if (!username || !password) return
    
    loading = true
    try {
      await login(username, password)
      showToast('success', 'Logged in successfully')
      
      // Force a hard reload to /admin to ensure state propagates cleanly
      window.location.hash = '#/admin'
    } catch (err) {
      showToast('error', err.message || 'Invalid credentials')
    } finally {
      loading = false
      password = '' // Clear password on failure
    }
  }
</script>

<div class="flex min-h-screen items-center justify-center p-4">
  <div class="glass w-full max-w-md p-8">
    
    <div class="mb-8 text-center">
      <h1 class="text-2xl font-bold tracking-tight text-text-primary">Admin Access</h1>
      <p class="mt-2 text-sm text-text-secondary">Enter credentials to manage artists and scandals.</p>
    </div>

    <form onsubmit={handleLogin} class="space-y-5">
      <div>
        <label for="username" class="mb-1 block text-sm font-medium text-text-secondary">Username</label>
        <input
          type="text"
          id="username"
          bind:value={username}
          class="input-glass"
          placeholder="admin"
          disabled={loading}
          required
        />
      </div>

      <div>
        <label for="password" class="mb-1 block text-sm font-medium text-text-secondary">Password</label>
        <input
          type="password"
          id="password"
          bind:value={password}
          class="input-glass"
          placeholder="••••••••"
          disabled={loading}
          required
        />
      </div>

      <button
        type="submit"
        class="btn-primary mt-6 w-full py-3 text-base flex justify-center items-center"
        disabled={loading}
      >
        {#if loading}
          <div class="spinner border-2 bg-transparent w-5 h-5 !border-t-black"></div>
        {:else}
          Sign In
        {/if}
      </button>
    </form>
    
    <div class="mt-8 text-center">
      <a href="#/" class="text-sm font-medium text-text-tertiary transition-colors hover:text-text-primary">
        &larr; Back to Public View
      </a>
    </div>

  </div>
</div>
