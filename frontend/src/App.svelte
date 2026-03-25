<script>
  import { toast, authToken } from './lib/stores.js'
  import { logout, fetchPendingCount } from './lib/api.js'

  // Admin pages
  import Dashboard from './routes/Dashboard.svelte'
  import Artists from './routes/Artists.svelte'
  import Scandals from './routes/Scandals.svelte'
  import Submit from './routes/Submit.svelte'
  import Login from './routes/Login.svelte'
  import ArtistScandalsAdmin from './routes/ArtistScandalsAdmin.svelte'
  import CommunityAdmin from './routes/CommunityAdmin.svelte'
  import CommunityArtistAdmin from './routes/CommunityArtistAdmin.svelte'
  import CommunitySourcesAdmin from './routes/CommunitySourcesAdmin.svelte'

  // Public pages
  import Home from './routes/public/Home.svelte'
  import ArtistScandals from './routes/public/ArtistScandals.svelte'
  import AuthCallback from './routes/public/AuthCallback.svelte'
  import NotFound from './routes/NotFound.svelte'

  const navItems = [
    { path: '/admin', label: 'Dashboard', icon: '◈' },
    { path: '/admin/artists', label: 'Artists', icon: '◉' },
    { path: '/admin/scandals', label: 'Scandals', icon: '⚡' },
    { path: '/admin/community', label: 'Community', icon: '👥' },
  ]

  let pendingCount = $state(0)

  async function loadPendingCount() {
    try {
      const data = await fetchPendingCount()
      pendingCount = data.total || 0
    } catch {
      pendingCount = 0
    }
  }

  // Path-based router using History API
  let currentPath = $state(window.location.pathname)
  let isMobileMenuOpen = $state(false)

  function handlePopState() {
    currentPath = window.location.pathname
  }

  function navigate(path) {
    history.pushState({}, '', path)
    currentPath = path
    isMobileMenuOpen = false
  }

  function handleGlobalClick(e) {
    const anchor = e.target.closest('a')
    if (!anchor) return
    const href = anchor.getAttribute('href')
    if (!href || href.startsWith('http') || href.startsWith('mailto:') || anchor.target === '_blank') return
    if (href.startsWith('/')) {
      e.preventDefault()
      navigate(href)
    }
  }

  function handleLogout() {
    logout()
    navigate('/admin/login')
  }

  let isAdminRoute = $derived(currentPath.startsWith('/admin'))

  // Load pending community count when on admin routes
  $effect(() => {
    if (isAdminRoute && $authToken) {
      loadPendingCount()
    }
  })

  // Protect admin routes (redirect to login if no token)
  $effect(() => {
    if (isAdminRoute && currentPath !== '/admin/login' && !$authToken) {
      navigate('/admin/login')
    }
    // If logged in and trying to access login page, redirect to admin dashboard
    if (currentPath === '/admin/login' && $authToken) {
      navigate('/admin')
    }
  })
</script>

<svelte:window onpopstate={handlePopState} />

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="flex min-h-screen bg-bg-primary" onclick={handleGlobalClick}>
  <!-- ═══ Background Pattern ═══ -->
  <div class="bg-decorations" aria-hidden="true">
    <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <pattern id="scattered-s" x="0" y="0" width="400" height="400" patternUnits="userSpaceOnUse">
          <g font-family="Inter, -apple-system, sans-serif" font-weight="700" fill="var(--color-spotify)">
            <!-- Original large ones -->
            <text x="40" y="60" font-size="32" transform="rotate(-15 40 60)" fill-opacity="0.08">S</text>
            <text x="200" y="90" font-size="54" transform="rotate(22 200 90)" fill-opacity="0.12">S</text>
            <text x="340" y="50" font-size="28" transform="rotate(-8 340 50)" fill-opacity="0.06">S</text>
            <text x="80" y="240" font-size="64" transform="rotate(12 80 240)" fill-opacity="0.10">S</text>
            <text x="240" y="320" font-size="36" transform="rotate(-20 240 320)" fill-opacity="0.07">S</text>
            <text x="350" y="240" font-size="48" transform="rotate(18 350 240)" fill-opacity="0.09">S</text>
            <text x="160" y="380" font-size="40" transform="rotate(-10 160 380)" fill-opacity="0.14">S</text>
            
            <!-- New smaller ones with varying opacities -->
            <text x="120" y="30" font-size="16" transform="rotate(45 120 30)" fill-opacity="0.18">S</text>
            <text x="280" y="20" font-size="14" transform="rotate(-30 280 20)" fill-opacity="0.04">S</text>
            <text x="380" y="140" font-size="18" transform="rotate(15 380 140)" fill-opacity="0.15">S</text>
            <text x="20" y="150" font-size="20" transform="rotate(-45 20 150)" fill-opacity="0.05">S</text>
            <text x="140" y="170" font-size="24" transform="rotate(35 140 170)" fill-opacity="0.11">S</text>
            <text x="280" y="180" font-size="16" transform="rotate(-15 280 180)" fill-opacity="0.16">S</text>
            <text x="25" y="350" font-size="18" transform="rotate(25 25 350)" fill-opacity="0.08">S</text>
            <text x="100" y="320" font-size="14" transform="rotate(-55 100 320)" fill-opacity="0.19">S</text>
            <text x="200" y="250" font-size="22" transform="rotate(5 200 250)" fill-opacity="0.03">S</text>
            <text x="300" y="380" font-size="16" transform="rotate(40 300 380)" fill-opacity="0.13">S</text>
            <text x="380" y="330" font-size="20" transform="rotate(-25 380 330)" fill-opacity="0.06">S</text>
          </g>
        </pattern>
      </defs>
      <rect x="0" y="0" width="100%" height="100%" fill="url(#scattered-s)" />
    </svg>
  </div>

  {#if isAdminRoute}
    {#if currentPath === '/admin/login'}
      <main class="relative z-10 mx-auto w-full flex-1 px-4 sm:px-6 lg:px-8 flex min-h-screen items-center justify-center">
        <Login />
      </main>
    {:else}
      <!-- ═══ Mobile Header (Visible only on small screens) ═══ -->
      <div class="fixed left-0 right-0 top-0 z-40 flex items-center justify-between border-b border-glass-border bg-bg-secondary/80 px-4 py-3 backdrop-blur-xl lg:hidden">
        <div class="flex items-center gap-2">
          <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-spotify text-sm font-bold text-black shadow-lg shadow-spotify-glow">S</div>
          <h1 class="text-sm font-semibold text-text-primary">Admin</h1>
        </div>
        <button onclick={() => isMobileMenuOpen = !isMobileMenuOpen} class="p-2 text-text-secondary hover:text-text-primary">
          <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            {#if isMobileMenuOpen}
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            {:else}
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
            {/if}
          </svg>
        </button>
      </div>

      <!-- ═══ Mobile Menu Overlay ═══ -->
      {#if isMobileMenuOpen}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden" onclick={() => isMobileMenuOpen = false}></div>
      {/if}

      <!-- ═══ Admin Sidebar Layout ═══ -->
      <aside class="fixed left-0 top-0 z-50 flex h-screen w-64 flex-col border-r border-glass-border bg-bg-secondary/95 backdrop-blur-3xl transition-transform duration-300 lg:translate-x-0 {isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}">
        <!-- Logo -->
        <div class="flex items-center gap-3 px-6 py-6">
          <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-spotify text-lg font-bold text-black shadow-lg shadow-spotify-glow">S</div>
          <div>
            <h1 class="text-sm font-semibold text-text-primary">Admin Panel</h1>
            <p class="text-xs text-text-tertiary">Spotify Scandals</p>
          </div>
        </div>

        <!-- Nav Links -->
        <nav class="mt-4 flex-1 space-y-1 px-3">
          {#each navItems as item}
            <button
              onclick={() => navigate(item.path)}
              class="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-left text-sm font-medium transition-all duration-200
                {currentPath === item.path || (currentPath === '/admin' && item.path === '/admin')
                  ? 'bg-glass text-text-primary shadow-sm'
                  : 'text-text-secondary hover:bg-glass hover:text-text-primary'}"
            >
              <span class="text-base">{item.icon}</span>
              {item.label}
              {#if item.path === '/admin/community' && pendingCount > 0}
                <span class="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-danger px-1.5 text-[10px] font-bold text-white">{pendingCount}</span>
              {/if}
            </button>
          {/each}
        </nav>

        <!-- Footer / Logout -->
        <div class="border-t border-glass-border p-4 flex flex-col gap-2">
          <button onclick={handleLogout} class="btn-outline w-full py-2 text-xs text-text-secondary hover:text-danger hover:border-danger hover:bg-danger-glow">
            Logout
          </button>
          <p class="text-[10px] text-text-tertiary text-center mt-2">v2.0.0 · Auth Enabled</p>
        </div>
      </aside>

      <!-- Admin Content Area -->
      <main class="relative z-10 w-full flex-1 p-4 pt-20 lg:ml-64 lg:p-8 lg:pt-8 min-w-0">
        {#if currentPath === '/admin'}
          <Dashboard />
        {:else if currentPath === '/admin/artists'}
          <Artists />
        {:else if currentPath.startsWith('/admin/scandals/') && currentPath.length > '/admin/scandals/'.length}
          <ArtistScandalsAdmin artistId={parseInt(currentPath.split('/')[3])} />
        {:else if currentPath === '/admin/scandals'}
          <Scandals />
        {:else if currentPath.startsWith('/admin/community/sources/')}
          <CommunitySourcesAdmin artistName={decodeURIComponent(currentPath.split('/').slice(4).join('/'))} />
        {:else if currentPath.startsWith('/admin/community/') && currentPath.length > '/admin/community/'.length}
          <CommunityArtistAdmin artistId={parseInt(currentPath.split('/')[3])} />
        {:else if currentPath === '/admin/community'}
          <CommunityAdmin />
        {:else}
          <Dashboard />
        {/if}
      </main>
    {/if}
  {:else}
    <!-- ═══ Public Layout (No Sidebar) ═══ -->
    <main class="relative z-10 mx-auto w-full flex-1 px-4 sm:px-6 lg:px-8">
      {#if currentPath.startsWith('/auth/')}
        <AuthCallback />
      {:else if currentPath.startsWith('/artist/')}
        <ArtistScandals params={{ id: currentPath.split('/')[2] }} />
      {:else if currentPath === '/submit'}
        <!-- Reuse Submit component for public so they can add playlists -->
        <Submit />
      {:else if currentPath === '/'}
        <Home />
      {:else}
        <NotFound />
      {/if}
    </main>
  {/if}

  <!-- ═══ Toast ═══ -->
  {#if $toast}
    <div class="fade-in fixed bottom-6 right-6 z-[100] rounded-2xl border border-glass-border px-5 py-3 text-sm font-medium backdrop-blur-xl
      {$toast.type === 'success' ? 'bg-success-glow text-success' : ''}
      {$toast.type === 'error' ? 'bg-danger-glow text-danger' : ''}
      {$toast.type === 'info' ? 'bg-glass text-text-primary' : ''}"
    >
      {$toast.message}
    </div>
  {/if}
</div>
