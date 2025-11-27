"use client";

import React from 'react';
import type { AttentionEvent } from '@/lib/api';

export default function AttentionEvents({ events }: { events: AttentionEvent[] }) {
  if (!events || events.length === 0) {
    return (
      <div className="bg-card rounded-lg border p-4 text-sm text-muted-foreground">
        No attention events detected in range.
      </div>
    );
  }

  return (
    <div className="bg-card rounded-lg border p-4">
      <h3 className="text-lg font-semibold mb-3">Attention Events</h3>
      <div className="space-y-2 max-h-64 overflow-auto pr-1">
        {events.map((e, idx) => (
          <div key={idx} className="flex items-start gap-3 border-b border-border/50 pb-2 last:border-b-0">
            <div className="mt-1 w-2 h-2 rounded-full bg-yellow-500" />
            <div className="flex-1">
              <div className="text-sm text-muted-foreground">{new Date(e.datetime).toLocaleString()}</div>
              <div className="text-sm"><span className="font-medium">{e.event_type}</span> · intensity {e.intensity.toFixed(2)}</div>
              <div className="text-xs text-muted-foreground">{e.summary}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
