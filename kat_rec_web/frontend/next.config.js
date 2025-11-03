/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Static export for desktop app (can be overridden for server builds)
  // In dev mode, output is not set (allows middleware to work)
  output: process.env.NEXT_OUTPUT_MODE === 'standalone' ? 'standalone' : 
          process.env.NEXT_OUTPUT_MODE === 'export' ? 'export' : undefined,
  trailingSlash: true,
  // Optimize bundle size
  experimental: {
    optimizePackageImports: ['lucide-react', '@tanstack/react-query'],
  },
}

module.exports = nextConfig

