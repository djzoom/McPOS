/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Enable standalone output for smaller Docker images
  output: 'standalone',
  // Optimize bundle size
  experimental: {
    optimizePackageImports: ['lucide-react', '@tanstack/react-query'],
  },
}

module.exports = nextConfig

