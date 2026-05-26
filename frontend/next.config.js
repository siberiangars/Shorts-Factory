/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  images: {
    remotePatterns: [
      // Google аватары
      { protocol: 'https', hostname: 'lh3.googleusercontent.com' },
      // Telegram аватары
      { protocol: 'https', hostname: 't.me' },
      { protocol: 'https', hostname: '*.telegram.org' },
    ],
  },
}

module.exports = nextConfig
