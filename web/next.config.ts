import type { NextConfig } from 'next'
import path from 'path'

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Fix Next.js root inference warning in monorepo/multi-lockfile setups
  outputFileTracingRoot: path.join(__dirname, '..'),
  
  // 性能优化
  compiler: {
    // 移除 console.log（生产环境）
    removeConsole: process.env.NODE_ENV === 'production' ? { exclude: ['error', 'warn'] } : false,
  },
  
  // 实验性功能：优化包大小
  experimental: {
    optimizePackageImports: ['lucide-react', 'lightweight-charts'],
  },
  
  // 允许后端 API 跨域（开发环境）
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*', // Python 后端地址
      },
    ]
  },
  
  // 缓存优化
  async headers() {
    return [
      {
        source: '/:all*(svg|jpg|png|woff|woff2)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
    ]
  },
}

export default nextConfig
