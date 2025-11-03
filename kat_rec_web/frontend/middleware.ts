import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

/**
 * Middleware for route aliasing
 * Redirects /t2r and / to /mcrb for public-facing UI
 * Internal code still uses t2r, but public URLs use mcrb
 * 
 * Note: Middleware is disabled for static exports (output: export)
 * In that case, route aliasing should be handled client-side or via routing config
 */
export function middleware(req: NextRequest) {
  const pathname = req.nextUrl.pathname

  // Redirect /t2r to /mcrb (backward compatibility)
  // Note: In static export mode, Next.js will show a warning but this won't break
  if (pathname === '/t2r' || pathname === '/t2r/') {
    const url = req.nextUrl.clone()
    url.pathname = '/mcrb'
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/t2r/:path*', '/'],
}

