"use client"

import React from 'react'
import AutoUpdateManager from '@/components/AutoUpdateManager'
import { useSettings } from '@/components/SettingsProvider'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'

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
    </div>
  )
}
