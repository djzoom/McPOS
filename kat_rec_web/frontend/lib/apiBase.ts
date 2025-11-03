/**
 * API Base URL Shim
 * 
 * For static exports (desktop app), API base can be injected via window globals.
 * Falls back to environment variables or defaults.
 */

// Extend Window interface for injected globals
declare global {
  interface Window {
    __API_BASE__?: string
    __WS_BASE__?: string
  }
}

/**
 * Get API base URL from window globals (desktop app), env var, or default
 */
export function getApiBase(): string {
  // Desktop app injection
  if (typeof window !== 'undefined' && window.__API_BASE__) {
    return window.__API_BASE__
  }
  
  // Environment variable
  if (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL
  }
  
  // Default
  return 'http://localhost:8000'
}

/**
 * Get WebSocket base URL from window globals (desktop app), env var, or default
 */
export function getWsBase(): string {
  // Desktop app injection
  if (typeof window !== 'undefined' && window.__WS_BASE__) {
    return window.__WS_BASE__
  }
  
  // Derive from API base (replace http with ws)
  const apiBase = getApiBase()
  return apiBase.replace(/^http/, 'ws')
}

