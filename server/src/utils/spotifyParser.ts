export function parseSpotifyPlaylistId(url: string): string | null {
  // Supported: https://open.spotify.com/playlist/{id}
  const match = url.match(/spotify\.com\/playlist\/([a-zA-Z0-9_-]+)/)
  return match ? match[1] : null
}
