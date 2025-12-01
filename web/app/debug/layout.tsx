'use client'

import React, { Component, ReactNode, ErrorInfo } from 'react'

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

/**
 * Debug 页面专用的 Error Boundary
 * 确保 debug 页面即使在其他组件崩溃时也能显示
 */
class DebugErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  constructor(props: { children: ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo })
    console.error('[Debug Page Error]', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gray-950 text-white p-4">
          <div className="max-w-4xl mx-auto">
            <header className="border-b border-gray-800 pb-4 mb-4">
              <h1 className="text-xl font-bold text-red-500">⚠️ Debug 页面加载失败</h1>
              <p className="text-sm text-gray-400 mt-1">
                页面组件发生错误，但您仍可以查看错误详情
              </p>
            </header>
            
            <div className="space-y-4">
              <div className="bg-gray-900 border border-red-500/30 rounded-lg p-4">
                <h2 className="text-sm font-semibold text-red-400 mb-2">错误信息</h2>
                <pre className="text-xs text-red-300 whitespace-pre-wrap break-all overflow-auto max-h-40">
                  {this.state.error?.message || 'Unknown error'}
                </pre>
              </div>
              
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                <h2 className="text-sm font-semibold text-gray-400 mb-2">堆栈信息</h2>
                <pre className="text-xs text-gray-500 whitespace-pre-wrap break-all overflow-auto max-h-60">
                  {this.state.error?.stack || 'No stack trace'}
                </pre>
              </div>
              
              {this.state.errorInfo && (
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                  <h2 className="text-sm font-semibold text-gray-400 mb-2">组件堆栈</h2>
                  <pre className="text-xs text-gray-500 whitespace-pre-wrap break-all overflow-auto max-h-60">
                    {this.state.errorInfo.componentStack}
                  </pre>
                </div>
              )}
              
              <div className="flex gap-2">
                <button
                  onClick={() => this.setState({ hasError: false, error: null, errorInfo: null })}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-sm font-medium"
                >
                  重试
                </button>
                <button
                  onClick={() => window.location.href = '/'}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm font-medium"
                >
                  返回首页
                </button>
                <button
                  onClick={() => window.location.reload()}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm font-medium"
                >
                  刷新页面
                </button>
              </div>
              
              <div className="mt-6 p-4 bg-gray-900 border border-gray-700 rounded-lg">
                <h2 className="text-sm font-semibold text-gray-400 mb-2">快速诊断</h2>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-gray-500">当前 URL</span>
                    <code className="text-gray-300">{typeof window !== 'undefined' ? window.location.href : 'SSR'}</code>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">User Agent</span>
                    <code className="text-gray-300 truncate max-w-md">
                      {typeof navigator !== 'undefined' ? navigator.userAgent.slice(0, 50) + '...' : 'SSR'}
                    </code>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">时间戳</span>
                    <code className="text-gray-300">{new Date().toISOString()}</code>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

export default function DebugLayout({ children }: { children: ReactNode }) {
  return (
    <DebugErrorBoundary>
      {children}
    </DebugErrorBoundary>
  )
}
