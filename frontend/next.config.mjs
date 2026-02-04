/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable strict mode for highlighting potential problems
  reactStrictMode: true,

  // API proxy to backend during development
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/v1/:path*`,
      },
    ]
  },

  // Image optimization config
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**',
      },
    ],
  },
}

export default nextConfig
