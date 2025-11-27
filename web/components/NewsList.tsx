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
}

export default function NewsList({ news, maxItems = 10 }: NewsListProps) {
  const displayNews = news.slice(0, maxItems)

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Recent News</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 max-h-[500px] overflow-y-auto">
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
                <span className="font-medium">{item.source}</span>
                <span>•</span>
                <span>{format(new Date(item.datetime), 'MMM dd, HH:mm')}</span>
              </div>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
