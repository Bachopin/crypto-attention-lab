'use client'

import React from 'react'
import { useWebSocketStatus } from '@/lib/websocket'
import { cn } from '@/lib/utils'

interface WebSocketStatusIndicatorProps {
  className?: string
  showLabel?: boolean
}

/**
 * WebSocket 连接状态指示器
 * 显示实时数据连接状态
 */
export function WebSocketStatusIndicator({
  className,
  showLabel = true,
}: WebSocketStatusIndicatorProps) {
  const { priceStatus, attentionStatus } = useWebSocketStatus()

  // 综合状态
  const overallStatus = 
    priceStatus === 'connected' || attentionStatus === 'connected' 
      ? 'connected' 
      : priceStatus === 'connecting' || attentionStatus === 'connecting'
        ? 'connecting'
        : priceStatus === 'error' || attentionStatus === 'error'
          ? 'error'
          : 'disconnected'

  const statusConfig = {
    connected: {
      color: 'bg-green-500',
      pulseColor: 'bg-green-400',
      label: '实时连接',
      animate: true,
    },
    connecting: {
      color: 'bg-yellow-500',
      pulseColor: 'bg-yellow-400',
      label: '连接中...',
      animate: true,
    },
    disconnected: {
      color: 'bg-gray-500',
      pulseColor: 'bg-gray-400',
      label: '离线',
      animate: false,
    },
    error: {
      color: 'bg-red-500',
      pulseColor: 'bg-red-400',
      label: '连接错误',
      animate: false,
    },
  }

  const config = statusConfig[overallStatus]

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className="relative">
        <span
          className={cn(
            'block h-2.5 w-2.5 rounded-full',
            config.color
          )}
        />
        {config.animate && (
          <span
            className={cn(
              'absolute inset-0 h-2.5 w-2.5 rounded-full animate-ping opacity-75',
              config.pulseColor
            )}
          />
        )}
      </div>
      {showLabel && (
        <span className="text-xs text-muted-foreground">
          {config.label}
        </span>
      )}
    </div>
  )
}

/**
 * 详细的 WebSocket 状态面板
 * 显示价格和注意力数据的连接状态
 */
export function WebSocketStatusPanel({ className }: { className?: string }) {
  const { priceStatus, attentionStatus } = useWebSocketStatus()

  const StatusBadge = ({ status, label }: { status: string; label: string }) => {
    const colors = {
      connected: 'bg-green-500/10 text-green-500 border-green-500/20',
      connecting: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
      disconnected: 'bg-gray-500/10 text-gray-400 border-gray-500/20',
      error: 'bg-red-500/10 text-red-500 border-red-500/20',
    }

    return (
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        <span
          className={cn(
            'px-2 py-0.5 text-xs rounded-full border',
            colors[status as keyof typeof colors] || colors.disconnected
          )}
        >
          {status}
        </span>
      </div>
    )
  }

  return (
    <div className={cn('space-y-2 p-3 rounded-lg bg-card border', className)}>
      <div className="flex items-center gap-2 mb-2">
        <WebSocketStatusIndicator showLabel={false} />
        <span className="text-sm font-medium">实时数据连接</span>
      </div>
      <StatusBadge status={priceStatus} label="价格数据" />
      <StatusBadge status={attentionStatus} label="注意力数据" />
    </div>
  )
}

export default WebSocketStatusIndicator
