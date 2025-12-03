"use client"

import React from 'react'
import AutoUpdateManager from '@/components/AutoUpdateManager'
import { useSettings } from '@/components/SettingsProvider'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Activity, Zap, TrendingUp, TrendingDown, AlertCircle, RotateCcw } from 'lucide-react'
import { DEFAULT_EVENT_THRESHOLDS, DEFAULT_EVENT_VISIBILITY } from '@/lib/settings'

// 事件类型的显示名称和描述
const EVENT_TYPE_INFO = {
  attention_spike: {
    label: 'Attention Spike',
    description: '综合注意力超过阈值',
    icon: Zap,
    color: 'text-yellow-500',
  },
  high_weighted_event: {
    label: 'High Weighted Event',
    description: '高权重新闻事件',
    icon: Activity,
    color: 'text-blue-500',
  },
  high_bullish: {
    label: 'High Bullish',
    description: '高看涨情绪',
    icon: TrendingUp,
    color: 'text-green-500',
  },
  high_bearish: {
    label: 'High Bearish',
    description: '高看跌情绪',
    icon: TrendingDown,
    color: 'text-red-500',
  },
  event_intensity: {
    label: 'Event Intensity',
    description: '新闻事件强度标志',
    icon: AlertCircle,
    color: 'text-orange-500',
  },
} as const;

type EventTypeKey = keyof typeof EVENT_TYPE_INFO;

export default function SettingsTab({ onUpdate }: { onUpdate: () => void }) {
  const { settings, updateSettings } = useSettings();

  return (
    <div className="space-y-6">
      {/* Runtime Preferences */}
      <section className="space-y-4">
        <h2 className="text-2xl font-bold">Runtime Preferences</h2>
        <AutoUpdateManager onUpdate={onUpdate} />
      </section>

      <Separator />

      {/* Research Preferences */}
      <section className="space-y-4">
        <h2 className="text-2xl font-bold">Research Preferences</h2>
        
        <div className="grid gap-6 md:grid-cols-2">
          {/* Default Attention Source */}
          <Card>
            <CardHeader>
              <CardTitle>Default Attention Source</CardTitle>
              <CardDescription>
                Select the default attention metric used for backtesting and analysis modules.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <RadioGroup 
                value={settings.defaultAttentionSource} 
                onValueChange={(val) => updateSettings({ defaultAttentionSource: val as 'composite' | 'news_channel' })}
              >
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="composite" id="att-composite" />
                  <Label htmlFor="att-composite">Composite (News + Google + Twitter)</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="news_channel" id="att-news" />
                  <Label htmlFor="att-news">News Channel Only</Label>
                </div>
              </RadioGroup>
            </CardContent>
          </Card>

          {/* Default Timeframe */}
          <Card>
            <CardHeader>
              <CardTitle>Default Timeframe</CardTitle>
              <CardDescription>
                Set the default timeframe for charts, regime analysis, and scenario planning.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <RadioGroup 
                value={settings.defaultTimeframe} 
                onValueChange={(val) => updateSettings({ defaultTimeframe: val as '1D' | '4H' })}
              >
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="1D" id="tf-1d" />
                  <Label htmlFor="tf-1d">1 Day (Daily)</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="4H" id="tf-4h" />
                  <Label htmlFor="tf-4h">4 Hours</Label>
                </div>
              </RadioGroup>
            </CardContent>
          </Card>

          {/* Default Analysis Window */}
          <Card>
            <CardHeader>
              <CardTitle>Default Analysis Window (Days)</CardTitle>
              <CardDescription>
                The default lookback period for calculating regimes, scenarios, and similarity.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4">
                <Label htmlFor="window-days" className="w-24">Window Days</Label>
                <Input 
                  id="window-days" 
                  type="number" 
                  min={7} 
                  max={365}
                  value={settings.defaultWindowDays}
                  onChange={(e) => updateSettings({ defaultWindowDays: parseInt(e.target.value) || 30 })}
                  className="w-32"
                />
              </div>
              <p className="text-sm text-muted-foreground mt-2">
                Recommended: 30, 60, or 90 days.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      <Separator />

      {/* Chart & Analysis Preferences */}
      <section className="space-y-4">
        <h2 className="text-2xl font-bold">Chart & Analysis Preferences</h2>
        
        <div className="grid gap-6 md:grid-cols-2">
          {/* Show Event Markers */}
          <Card>
            <CardHeader>
              <CardTitle>Chart Event Markers</CardTitle>
              <CardDescription>
                Show attention spike events on price charts by default.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center space-x-2">
                <RadioGroup 
                  value={settings.showEventMarkers ? "show" : "hide"} 
                  onValueChange={(val) => updateSettings({ showEventMarkers: val === "show" })}
                >
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="show" id="events-show" />
                    <Label htmlFor="events-show">Show Events</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="hide" id="events-hide" />
                    <Label htmlFor="events-hide">Hide Events</Label>
                  </div>
                </RadioGroup>
              </div>
            </CardContent>
          </Card>

          {/* Event Detection Sensitivity */}
          <Card className="md:col-span-2">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Event Detection Sensitivity</CardTitle>
                  <CardDescription>
                    配置事件检测的灵敏度和显示过滤。调高分位数阈值可以减少事件标注数量，只保留更显著的事件。
                  </CardDescription>
                </div>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => {
                    updateSettings({ 
                      eventTypeThresholds: DEFAULT_EVENT_THRESHOLDS,
                      eventTypeVisibility: DEFAULT_EVENT_VISIBILITY,
                      eventDetectionQuantile: 0.9,
                      eventDetectionLookbackDays: 30,
                    });
                  }}
                  className="gap-1"
                >
                  <RotateCcw className="w-3 h-3" />
                  Reset
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* API Parameters - 影响后端返回的事件数据 */}
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-medium">API 请求参数</h4>
                  <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">影响后端检测</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  这些参数决定后端如何检测事件。修改后需要刷新页面以重新获取数据。
                </p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2 p-3 bg-muted/20 rounded-lg">
                    <Label htmlFor="lookback-days" className="text-sm font-medium">Lookback Days（回溯天数）</Label>
                    <div className="flex items-center gap-2">
                      <Input 
                        id="lookback-days" 
                        type="number" 
                        min={7} 
                        max={90}
                        value={settings.eventDetectionLookbackDays}
                        onChange={(e) => updateSettings({ eventDetectionLookbackDays: parseInt(e.target.value) || 30 })}
                        className="w-24"
                      />
                      <span className="text-xs text-muted-foreground">天</span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      用于计算滚动分位数的窗口大小。例如设为 30 天，则当某天的注意力分数超过过去 30 天的 90% 分位时才标记为事件。
                    </p>
                  </div>
                  <div className="space-y-2 p-3 bg-muted/20 rounded-lg">
                    <Label htmlFor="global-quantile" className="text-sm font-medium">Global Quantile（全局分位数）</Label>
                    <div className="flex items-center gap-2">
                      <Input 
                        id="global-quantile" 
                        type="number" 
                        min={0.7} 
                        max={0.99}
                        step={0.01}
                        value={settings.eventDetectionQuantile}
                        onChange={(e) => updateSettings({ eventDetectionQuantile: parseFloat(e.target.value) || 0.9 })}
                        className="w-24"
                      />
                    </div>
                    <p className="text-xs text-muted-foreground">
                      事件检测的分位数阈值。0.9 表示只有超过历史 90% 分位的注意力才被标记为事件。设置越高，事件越少但越显著。
                    </p>
                  </div>
                </div>
              </div>

              <Separator />

              {/* Per-Event-Type Settings - 前端显示过滤 */}
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-medium">事件类型显示过滤</h4>
                  <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">前端过滤</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  控制图表上显示哪些类型的事件标注。关闭不需要的事件类型可以减少图表杂乱。
                </p>
                <div className="grid gap-2">
                  {(Object.keys(EVENT_TYPE_INFO) as EventTypeKey[]).map((eventType) => {
                    const info = EVENT_TYPE_INFO[eventType];
                    const Icon = info.icon;
                    const isVisible = settings.eventTypeVisibility?.[eventType] ?? true;
                    
                    return (
                      <div 
                        key={eventType} 
                        className={`flex items-center justify-between p-2.5 rounded-lg border transition-colors ${
                          isVisible ? 'bg-muted/30' : 'bg-muted/10 opacity-60'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <Switch
                            checked={isVisible}
                            onCheckedChange={(checked) => {
                              updateSettings({
                                eventTypeVisibility: {
                                  ...settings.eventTypeVisibility,
                                  [eventType]: checked,
                                },
                              });
                            }}
                          />
                          <Icon className={`w-4 h-4 ${info.color}`} />
                          <div>
                            <div className="text-sm font-medium">{info.label}</div>
                            <div className="text-xs text-muted-foreground">{info.description}</div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                <p className="text-sm text-blue-600 dark:text-blue-400">
                  💡 <strong>提示：</strong>如果 SPIKE EVT 事件过多，可以将 Global Quantile 设为 0.95（仅显示 Top 5%）或关闭 Attention Spike 类型。
                  事件标注会自动显示在价格图表的对应时间位置上。
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      <Separator />

      {/* System Tools */}
      <section className="space-y-4">
        <h2 className="text-2xl font-bold">System Tools</h2>
        <Card>
          <CardHeader>
            <CardTitle>Debug & Diagnostics</CardTitle>
            <CardDescription>
              Access system diagnostics, API testing tools, and real-time connection status.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/debug/api-test">
              <Button variant="outline" className="gap-2">
                <Activity className="w-4 h-4" />
                Open API Debugger
              </Button>
            </Link>
          </CardContent>
        </Card>
      </section>
    </div>
  )
}
