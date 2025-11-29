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
  
  // 实验性功能：优化包大小和启动速度
  experimental: {
    optimizePackageImports: ['lucide-react', 'lightweight-charts', 'recharts', '@radix-ui/react-icons'],
  },
  
  // 开发模式优化：使用 Turbopack（更快的打包器）
  // 注意：如果遇到兼容性问题可以注释掉这行
  // turbopack: {},
  
  // 允许后端 API 跨域（开发环境）
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*', // Python 后端地址
      },
      {
        source: '/health',
        destination: 'http://localhost:8000/health', // 健康检查端点
      },
      {
        source: '/ping',
        destination: 'http://localhost:8000/ping', // Ping 端点
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
