import fetch from 'node-fetch'

export async function getSpotifyAccessToken(clientId: string, clientSecret: string): Promise<string> {
  const response = await fetch('https://accounts.spotify.com/api/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'Authorization': 'Basic ' + Buffer.from(`${clientId}:${clientSecret}`).toString('base64'),
    },
    body: 'grant_type=client_credentials',
  })
  const data: any = await response.json()
  return data.access_token
}

export async function getSpotifyPlaylistTracks(playlistId: string, accessToken: string): Promise<any[]> {
  const url = `https://api.spotify.com/v1/playlists/${playlistId}/tracks`
  console.log('Spotify API request URL:', url)
  console.log('Spotify API access token (first 20 chars):', accessToken?.slice(0, 20))
  const response = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${accessToken}`,
    },
  })
  const data: any = await response.json()
  // Logging entfernt: Full Spotify playlist API response
  return data.items || []
}
