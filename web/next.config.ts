import type { NextConfig } from 'next'
import path from 'path'

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Fix Next.js root inference warning in monorepo/multi-lockfile setups
  outputFileTracingRoot: path.join(__dirname, '..'),
  // 允许后端 API 跨域（开发环境）
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*', // Python 后端地址
      },
    ]
  },
}

export default nextConfig
