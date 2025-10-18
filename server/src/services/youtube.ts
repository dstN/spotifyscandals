export async function getYouTubePlaylistItems(playlistId: string, apiKey: string): Promise<any[]> {
  // Mock: Return example items
  return [
    {
      track: {
        artists: [
          { name: 'YouTube Artist 1' },
          { name: 'YouTube Artist 2' }
        ]
      }
    }
  ]
}
