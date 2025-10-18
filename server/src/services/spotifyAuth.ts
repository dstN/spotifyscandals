import fetch from 'node-fetch'

type TokenBundle = {
  accessToken: string
  refreshToken?: string
  expiresAt: number // epoch ms
}

let tokenStore: TokenBundle | null = null

export function getSpotifyAuthUrl(clientId: string, redirectUri: string, scopes: string[], state: string) {
  const params = new URLSearchParams({
    client_id: clientId,
    response_type: 'code',
    redirect_uri: redirectUri,
    scope: scopes.join(' '),
    state,
  })
  return `https://accounts.spotify.com/authorize?${params.toString()}`
}

export async function exchangeCodeForToken(code: string, clientId: string, clientSecret: string, redirectUri: string) {
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    code,
    redirect_uri: redirectUri,
  })
  const res = await fetch('https://accounts.spotify.com/api/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'Authorization': 'Basic ' + Buffer.from(`${clientId}:${clientSecret}`).toString('base64'),
    },
    body,
  })
  const data: any = await res.json()
  if (!res.ok) {
    throw new Error(`Spotify token exchange failed: ${res.status} ${res.statusText} ${JSON.stringify(data)}`)
  }
  const now = Date.now()
  const bundle: TokenBundle = {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    expiresAt: now + (data.expires_in ? data.expires_in * 1000 : 3600 * 1000),
  }
  tokenStore = bundle
  return bundle
}

export async function refreshAccessToken(clientId: string, clientSecret: string) {
  if (!tokenStore?.refreshToken) throw new Error('No refresh token available')
  const body = new URLSearchParams({
    grant_type: 'refresh_token',
    refresh_token: tokenStore.refreshToken,
  })
  const res = await fetch('https://accounts.spotify.com/api/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'Authorization': 'Basic ' + Buffer.from(`${clientId}:${clientSecret}`).toString('base64'),
    },
    body,
  })
  const data: any = await res.json()
  if (!res.ok) {
    throw new Error(`Spotify token refresh failed: ${res.status} ${res.statusText} ${JSON.stringify(data)}`)
  }
  const now = Date.now()
  tokenStore = {
    accessToken: data.access_token,
    refreshToken: data.refresh_token || tokenStore.refreshToken,
    expiresAt: now + (data.expires_in ? data.expires_in * 1000 : 3600 * 1000),
  }
  return tokenStore
}

export function setTokens(bundle: TokenBundle) {
  tokenStore = bundle
}

export async function getValidAccessToken(clientId: string, clientSecret: string): Promise<string | null> {
  if (!tokenStore) return null
  const now = Date.now()
  const bufferMs = 60_000
  if (tokenStore.expiresAt - now <= bufferMs) {
    try {
      await refreshAccessToken(clientId, clientSecret)
    } catch (e) {
      return null
    }
  }
  return tokenStore.accessToken
}

export function getTokenStatus() {
  if (!tokenStore) return { connected: false }
  return {
    connected: true,
    expiresAt: tokenStore.expiresAt,
    expiresInSec: Math.max(0, Math.floor((tokenStore.expiresAt - Date.now()) / 1000)),
    hasRefreshToken: Boolean(tokenStore.refreshToken),
  }
}
