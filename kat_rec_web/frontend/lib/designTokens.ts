/**
 * Design Tokens & Visual System
 * 
 * Unified color palette, status mappings, and visual design tokens
 * for the Schedule Board system.
 */

// Unified status type (SSOT for Schedule Board)
export type ScheduleEventStatus =
  | 'draft'
  | 'planned'
  | 'rendering'
  | 'ready'
  | 'uploaded'
  | 'verified'
  | 'failed'

// Asset completeness levels
export type AssetCompleteness = 'complete' | 'partial' | 'missing'

// Status color palette (HSL for easy manipulation)
export interface StatusColor {
  base: string // HSL or hex
  hover: string
  border: string
  text: string
  opacity: {
    bg: number // 0-1
    border: number
  }
}

// Status color definitions
export const statusColors: Record<ScheduleEventStatus, StatusColor> = {
  draft: {
    base: 'hsl(220, 20%, 25%)', // Muted slate
    hover: 'hsl(220, 20%, 30%)',
    border: 'hsl(220, 15%, 35%)',
    text: 'hsl(220, 10%, 70%)',
    opacity: { bg: 0.3, border: 0.4 },
  },
  planned: {
    base: 'hsl(217, 70%, 50%)', // Blue
    hover: 'hsl(217, 70%, 55%)',
    border: 'hsl(217, 60%, 45%)',
    text: 'hsl(217, 100%, 90%)',
    opacity: { bg: 0.4, border: 0.5 },
  },
  rendering: {
    base: 'hsl(262, 60%, 55%)', // Purple
    hover: 'hsl(262, 60%, 60%)',
    border: 'hsl(262, 50%, 50%)',
    text: 'hsl(262, 100%, 90%)',
    opacity: { bg: 0.45, border: 0.55 },
  },
  ready: {
    base: 'hsl(142, 60%, 45%)', // Green
    hover: 'hsl(142, 60%, 50%)',
    border: 'hsl(142, 50%, 40%)',
    text: 'hsl(142, 100%, 90%)',
    opacity: { bg: 0.35, border: 0.45 },
  },
  uploaded: {
    base: 'hsl(200, 70%, 50%)', // Cyan
    hover: 'hsl(200, 70%, 55%)',
    border: 'hsl(200, 60%, 45%)',
    text: 'hsl(200, 100%, 90%)',
    opacity: { bg: 0.4, border: 0.5 },
  },
  verified: {
    base: 'hsl(142, 70%, 40%)', // Darker green
    hover: 'hsl(142, 70%, 45%)',
    border: 'hsl(142, 60%, 35%)',
    text: 'hsl(142, 100%, 95%)',
    opacity: { bg: 0.5, border: 0.6 },
  },
  failed: {
    base: 'hsl(0, 65%, 50%)', // Red
    hover: 'hsl(0, 65%, 55%)',
    border: 'hsl(0, 55%, 45%)',
    text: 'hsl(0, 100%, 90%)',
    opacity: { bg: 0.4, border: 0.5 },
  },
}

/**
 * Map backend status values to unified ScheduleEventStatus
 */
export function normalizeStatus(backendStatus: string): ScheduleEventStatus {
  // Normalize to lowercase and trim
  const normalized = backendStatus?.toLowerCase().trim() || ''
  
  // Direct mapping for English statuses
  const statusMap: Record<string, ScheduleEventStatus> = {
    // Backend English statuses
    'pending': 'draft',
    'remixing': 'planned',
    'rendering': 'rendering',
    'uploading': 'uploaded',
    'completed': 'verified',
    'ready': 'ready',
    'failed': 'failed',
    'error': 'failed',
    
    // Backend Chinese statuses
    '待制作': 'draft',
    '制作中': 'planned',
    '渲染中': 'rendering',
    '上传中': 'uploaded',
    '已完成': 'verified',
    '已锁定': 'verified',
    '排播完毕待播出': 'uploaded',
    '已跳过': 'draft',
    
    // Unified statuses (pass-through)
    'draft': 'draft',
    'planned': 'planned',
    'rendering': 'rendering',
    'ready': 'ready',
    'uploaded': 'uploaded',
    'verified': 'verified',
    'failed': 'failed',
  }
  
  return statusMap[normalized] || 'draft'
}

/**
 * Get color for a status with optional asset completeness modifier
 */
export function getStatusColor(
  status: ScheduleEventStatus,
  completeness: AssetCompleteness = 'complete'
): StatusColor {
  const baseColor = statusColors[status]
  
  // Modify saturation/brightness based on completeness
  if (completeness === 'missing') {
    // Desaturate and darken
    return {
      ...baseColor,
      base: adjustHslOpacity(baseColor.base, { saturation: -30, lightness: -10 }),
      opacity: { ...baseColor.opacity, bg: baseColor.opacity.bg * 0.6 },
    }
  } else if (completeness === 'partial') {
    // Slight desaturation
    return {
      ...baseColor,
      base: adjustHslOpacity(baseColor.base, { saturation: -15 }),
      opacity: { ...baseColor.opacity, bg: baseColor.opacity.bg * 0.8 },
    }
  }
  
  return baseColor
}

/**
 * Adjust HSL color properties
 */
function adjustHslOpacity(
  hsl: string,
  adjustments: { hue?: number; saturation?: number; lightness?: number }
): string {
  const match = hsl.match(/hsl\((\d+),\s*(\d+)%,\s*(\d+)%\)/)
  if (!match) return hsl
  
  let [, h, s, l] = match.map(Number)
  
  if (adjustments.hue !== undefined) h = Math.max(0, Math.min(360, h + adjustments.hue))
  if (adjustments.saturation !== undefined) s = Math.max(0, Math.min(100, s + adjustments.saturation))
  if (adjustments.lightness !== undefined) l = Math.max(0, Math.min(100, l + adjustments.lightness))
  
  return `hsl(${h}, ${s}%, ${l}%)`
}

/**
 * Design spacing tokens (8px grid system)
 */
export const spacing = {
  xs: '0.25rem', // 4px
  sm: '0.5rem', // 8px
  md: '0.75rem', // 12px
  lg: '1rem', // 16px
  xl: '1.5rem', // 24px
  '2xl': '2rem', // 32px
  '3xl': '3rem', // 48px
} as const

/**
 * Design timing tokens (animation durations)
 */
export const timing = {
  fast: '150ms',
  normal: '250ms',
  slow: '400ms',
  verySlow: '600ms',
} as const

/**
 * Design easing functions
 */
export const easing = {
  easeInOut: 'cubic-bezier(0.4, 0, 0.2, 1)',
  easeOut: 'cubic-bezier(0, 0, 0.2, 1)',
  easeIn: 'cubic-bezier(0.4, 0, 1, 1)',
  spring: 'cubic-bezier(0.175, 0.885, 0.32, 1.275)',
} as const

/**
 * Shadow tokens for depth
 */
export const shadows = {
  sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
  md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
  lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
  xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
  inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)',
  glow: '0 0 20px rgba(74, 158, 255, 0.3)',
} as const

/**
 * Border radius tokens
 */
export const radii = {
  sm: '0.25rem', // 4px
  md: '0.5rem', // 8px
  lg: '0.75rem', // 12px
  xl: '1rem', // 16px
  full: '9999px',
} as const
