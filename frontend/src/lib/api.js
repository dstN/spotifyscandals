/**
 * API client for the Skandal Tracker backend.
 * All requests are proxied through Vite → FastAPI during development.
 */

import { get } from 'svelte/store'
import { authToken, publicToken } from './stores.js'

const BASE = '/api'

/**
 * Generic fetch wrapper with JSON parsing, error handling, and JWT injection.
 */
async function request(path, options = {}) {
  const url = `${BASE}${path}`

  // Attach admin token or public token if we have one
  const adminToken = get(authToken)
  const userToken = get(publicToken)

  const headers = { 'Content-Type': 'application/json', ...options.headers }

  const isVoteEndpoint = path.includes('/vote')
  const isPublicCommunitySubmit = path.includes('/artists/') && path.includes('/community-scandals')

  if ((isVoteEndpoint || isPublicCommunitySubmit) && userToken) {
    // These public endpoints strictly require a public user token
    headers['Authorization'] = `Bearer ${userToken}`
  } else if (adminToken) {
    // All other authenticated endpoints (admin panel) use the admin token
    headers['Authorization'] = `Bearer ${adminToken}`
  } else if (userToken) {
    // Fallback if no admin token but we are making a request (though other endpoints don't need it)
    headers['Authorization'] = `Bearer ${userToken}`
  }

  const config = {
    ...options,
    headers,
  }

  const response = await fetch(url, config)

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

// ═══════════════════════════════════════════
//  Dashboard
// ═══════════════════════════════════════════

export function fetchStats() {
  return request('/scandals/stats')
}

// ═══════════════════════════════════════════
//  Playlists
// ═══════════════════════════════════════════

export function submitPlaylist(playlistUrl) {
  return request('/playlists/submit', {
    method: 'POST',
    body: JSON.stringify({ playlist_url: playlistUrl }),
  })
}

// ═══════════════════════════════════════════
//  Artists
// ═══════════════════════════════════════════

export function fetchArtists({ approved, search } = {}) {
  const params = new URLSearchParams()
  if (approved !== undefined && approved !== null) params.set('approved', approved)
  if (search) params.set('search', search)
  const qs = params.toString()
  return request(`/artists${qs ? `?${qs}` : ''}`)
}

export function fetchArtist(id) {
  return request(`/artists/${id}`)
}

export function approveArtist(id) {
  return request(`/artists/${id}/approve`, { method: 'PATCH' })
}

export function deleteArtist(id) {
  return request(`/artists/${id}`, { method: 'DELETE' })
}

export function submitCommunityScandal(artistId, title, description, source_url) {
  return request(`/artists/${artistId}/community-scandals`, {
    method: 'POST',
    body: JSON.stringify({ title, description, source_url }),
  })
}

// ═══════════════════════════════════════════
//  Scandals
// ═══════════════════════════════════════════

export function fetchScandals({ verified, artist_id } = {}) {
  const params = new URLSearchParams()
  if (verified !== undefined && verified !== null) params.set('verified', verified)
  if (artist_id) params.set('artist_id', artist_id)
  const qs = params.toString()
  return request(`/scandals${qs ? `?${qs}` : ''}`)
}

export function scanForScandals(artistIds = []) {
  return request('/scandals/scan', {
    method: 'POST',
    body: JSON.stringify({ artist_ids: artistIds }),
  })
}

export function verifyScandal(id) {
  return request(`/scandals/${id}/verify`, { method: 'PATCH' })
}

export function deleteScandal(id) {
  return request(`/scandals/${id}`, { method: 'DELETE' })
}

export function deleteScandalSource(scandalId, sourceId) {
  return request(`/scandals/${scandalId}/sources/${sourceId}`, { method: 'DELETE' })
}

export function submitScandalVote(id, vote) {
  return request(`/scandals/${id}/vote`, {
    method: 'POST',
    body: JSON.stringify({ vote }),
  })
}

// ═══════════════════════════════════════════
//  Community Submissions Admin endpoints
// ═══════════════════════════════════════════

export async function fetchPendingCommunityScandals() {
  return request('/community-scandals')
}

export async function fetchArtistCommunityScandals(artistId) {
  return request(`/community-scandals/artist/${artistId}`)
}

export async function verifyCommunityScandal(submissionId, data) {
  return request(`/community-scandals/${submissionId}/verify`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function rejectCommunityScandal(submissionId) {
  return request(`/community-scandals/${submissionId}`, {
    method: 'DELETE',
  })
}

// ═══════════════════════════════════════════
//  Auth
// ═══════════════════════════════════════════

export async function login(username, password) {
  const data = await request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })

  // Save token to store (which syncs to localStorage)
  authToken.set(data.access_token)
  return data
}

export function logout() {
  authToken.set(null)
}
