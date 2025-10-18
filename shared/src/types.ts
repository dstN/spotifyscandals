// API Request/Response Types
export interface AnalyzePlaylistRequest {
  playlistUrl: string
}

export interface AnalyzePlaylistResponse {
  artists: ArtistWithScandals[]
}

// Domain Types
export interface ArtistWithScandals {
  name: string
  scandals: string[]
  imageUrl?: string
  genres?: string[]
}

export interface Scandal {
  title: string
  description: string
  source: string
  date?: string
  url?: string
}

export interface Artist {
  id: string
  name: string
  imageUrl?: string
  genres?: string[]
}

export interface Track {
  id: string
  name: string
  artists: Artist[]
  albumName?: string
}

export interface Playlist {
  id: string
  name: string
  description?: string
  platform: 'spotify' | 'youtube'
  tracks: Track[]
}

// Error Types
export interface ApiError {
  error: string
  message?: string
  statusCode?: number
}
