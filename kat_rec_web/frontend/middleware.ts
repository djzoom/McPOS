import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

/**
 * Middleware for route aliasing
 * Redirects /t2r and / to /mcrb for public-facing UI
 * Internal code still uses t2r, but public URLs use mcrb
 */
export function middleware(req: NextRequest) {
  const pathname = req.nextUrl.pathname

  // Redirect /t2r to /mcrb (backward compatibility)
  if (pathname === '/t2r' || pathname === '/t2r/') {
    const url = req.nextUrl.clone()
    url.pathname = '/mcrb'
    return NextResponse.redirect(url)
  }

  // Optional: redirect root to /mcrb if needed
  // if (pathname === '/') {
  //   const url = req.nextUrl.clone()
  //   url.pathname = '/mcrb'
  //   return NextResponse.redirect(url)
  // }

  return NextResponse.next()
}

export const config = {
  matcher: ['/t2r/:path*', '/'],
}

