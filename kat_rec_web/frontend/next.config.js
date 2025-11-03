/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Static export for desktop app (can be overridden for server builds)
  output: process.env.NEXT_OUTPUT_MODE === 'standalone' ? 'standalone' : 'export',
  trailingSlash: true,
  // Optimize bundle size
  experimental: {
    optimizePackageImports: ['lucide-react', '@tanstack/react-query'],
  },
}

module.exports = nextConfig

