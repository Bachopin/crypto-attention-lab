'use client'

import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import type { NewsItem } from '@/lib/api'
import { format } from 'date-fns'
import { ExternalLink } from 'lucide-react'

interface NewsListProps {
  news: NewsItem[]
  maxItems?: number
  title?: string
  containerHeight?: number
}

export default function NewsList({ news, maxItems = 10, title = "Recent News", containerHeight }: NewsListProps) {
  // Sort by datetime desc to ensure most recent first
  const displayNews = [...news]
    .sort((a, b) => new Date(b.datetime).getTime() - new Date(a.datetime).getTime())
    .slice(0, maxItems)

  // Calculate content area height: containerHeight - header padding (24px top + 16px bottom) - title height (~28px) - content padding (24px)
  const contentMaxHeight = containerHeight ? containerHeight - 92 : 400

  return (
    <Card className={containerHeight ? '' : 'h-full'} style={containerHeight ? { height: containerHeight } : undefined}>
      <CardHeader className="pb-3">
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 overflow-y-auto" style={{ maxHeight: contentMaxHeight }}>
        {displayNews.map((item, index) => (
          <div key={index}>
            {index > 0 && <Separator className="my-3" />}
            <div className="space-y-1">
              <div className="flex items-start justify-between gap-2">
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-medium hover:text-primary transition-colors flex-1 line-clamp-2"
                >
                  {item.title}
                </a>
                <ExternalLink className="w-4 h-4 text-muted-foreground flex-shrink-0 mt-0.5" />
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span className="font-medium text-foreground/80">{item.source}</span>
                <span>•</span>
                <span title={new Date(item.datetime).toString()}>
                  {format(new Date(item.datetime), 'yyyy-MM-dd HH:mm')}
                </span>
              </div>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
