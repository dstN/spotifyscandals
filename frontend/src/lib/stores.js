/**
 * Svelte stores for shared application state.
 */

import { writable } from 'svelte/store'

/** Current navigation route */
export const currentRoute = writable('/')

/** Toast notification state */
export const toast = writable(null)

/**
 * Show a toast notification.
 * @param {'success'|'error'|'info'} type
 * @param {string} message
 * @param {number} duration - ms
 */
export function showToast(type, message, duration = 3000) {
  toast.set({ type, message })
  setTimeout(() => toast.set(null), duration)
}

/**
 * Admin Authentication Token
 * Initialize from localStorage if available
 */
const storedToken = typeof window !== 'undefined' ? localStorage.getItem('admin_token') : null
export const authToken = writable(storedToken)

// Auto-sync admin token to localStorage
if (typeof window !== 'undefined') {
  authToken.subscribe((token) => {
    if (token) {
      localStorage.setItem('admin_token', token)
    } else {
      localStorage.removeItem('admin_token')
    }
  })
}

/**
 * Public User Token (from Spotify OAuth)
 * Initialize from localStorage if available
 */
const storedPublicToken =
  typeof window !== 'undefined' ? localStorage.getItem('public_token') : null
export const publicToken = writable(storedPublicToken)

// Auto-sync public token to localStorage
if (typeof window !== 'undefined') {
  publicToken.subscribe((token) => {
    if (token) {
      localStorage.setItem('public_token', token)
    } else {
      localStorage.removeItem('public_token')
    }
  })
}

/**
 * Derived store for the public user's Spotify ID
 * Parses the JWT to extract the subject if the token exists.
 */
import { derived } from 'svelte/store'

export const spotifyUser = derived(publicToken, ($token) => {
  if (!$token) return null
  try {
    const base64Url = $token.split('.')[1]
    const base64 = base64Url.replace(/-/g, '+').replace(/_/, '/')
    const payload = JSON.parse(window.atob(base64))

    return {
      id: payload.sub,
      name: payload.name || payload.sub,
      image: payload.image || null,
    }
  } catch (e) {
    return null
  }
})
