'use client'

import { useState, useEffect } from 'react'
import { fetchSongs, fetchImages } from '@/services/api'

type Tab = 'songs' | 'images'

export default function LibraryTabs() {
  const [activeTab, setActiveTab] = useState<Tab>('songs')
  const [songs, setSongs] = useState<any[]>([])
  const [images, setImages] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadLibrary()
  }, [activeTab])

  const loadLibrary = async () => {
    setLoading(true)
    try {
      if (activeTab === 'songs') {
        const data = await fetchSongs()
        setSongs(data)
      } else {
        const data = await fetchImages()
        setImages(data)
      }
    } catch (error) {
      console.error('Failed to load library:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatFileSize = (bytes: number | undefined) => {
    if (!bytes) return 'N/A'
    const mb = bytes / (1024 * 1024)
    return `${mb.toFixed(2)} MB`
  }

  return (
    <div className="card">
      <div className="flex space-x-4 border-b border-dark-border mb-6">
        <button
          onClick={() => setActiveTab('songs')}
          className={`pb-3 px-4 font-semibold transition-colors ${
            activeTab === 'songs'
              ? 'text-white border-b-2 border-blue-500'
              : 'text-dark-text-muted hover:text-dark-text'
          }`}
        >
          Songs ({songs.length})
        </button>
        <button
          onClick={() => setActiveTab('images')}
          className={`pb-3 px-4 font-semibold transition-colors ${
            activeTab === 'images'
              ? 'text-white border-b-2 border-blue-500'
              : 'text-dark-text-muted hover:text-dark-text'
          }`}
        >
          Images ({images.length})
        </button>
      </div>

      {loading ? (
        <div className="text-dark-text-muted text-center py-8">Loading...</div>
      ) : (
        <div className="overflow-x-auto">
          {activeTab === 'songs' ? (
            <table className="w-full">
              <thead>
                <tr className="border-b border-dark-border">
                  <th className="text-left py-2 text-dark-text-muted">Filename</th>
                  <th className="text-left py-2 text-dark-text-muted">Size</th>
                  <th className="text-left py-2 text-dark-text-muted">Discovered</th>
                </tr>
              </thead>
              <tbody>
                {songs.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="text-center py-8 text-dark-text-muted">
                      No songs found in library
                    </td>
                  </tr>
                ) : (
                  songs.map((song) => (
                    <tr key={song.id} className="border-b border-dark-border/50 hover:bg-dark-border/20">
                      <td className="py-2 font-mono text-sm">{song.filename}</td>
                      <td className="py-2 text-dark-text-muted">{formatFileSize(song.file_size_bytes)}</td>
                      <td className="py-2 text-dark-text-muted text-sm">
                        {song.discovered_at ? new Date(song.discovered_at).toLocaleDateString() : 'N/A'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-dark-border">
                  <th className="text-left py-2 text-dark-text-muted">Filename</th>
                  <th className="text-left py-2 text-dark-text-muted">Dimensions</th>
                  <th className="text-left py-2 text-dark-text-muted">Size</th>
                  <th className="text-left py-2 text-dark-text-muted">Discovered</th>
                </tr>
              </thead>
              <tbody>
                {images.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="text-center py-8 text-dark-text-muted">
                      No images found in library
                    </td>
                  </tr>
                ) : (
                  images.map((image) => (
                    <tr key={image.id} className="border-b border-dark-border/50 hover:bg-dark-border/20">
                      <td className="py-2 font-mono text-sm">{image.filename}</td>
                      <td className="py-2 text-dark-text-muted">
                        {image.width && image.height ? `${image.width}×${image.height}` : 'N/A'}
                      </td>
                      <td className="py-2 text-dark-text-muted">{formatFileSize(image.file_size_bytes)}</td>
                      <td className="py-2 text-dark-text-muted text-sm">
                        {image.discovered_at ? new Date(image.discovered_at).toLocaleDateString() : 'N/A'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

