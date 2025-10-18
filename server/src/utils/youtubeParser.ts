export function parseYouTubePlaylistId(url: string): string | null {
  // Supported: https://www.youtube.com/playlist?list={id}
  const match = url.match(/[?&]list=([a-zA-Z0-9_-]+)/)
  return match ? match[1] : null
}
