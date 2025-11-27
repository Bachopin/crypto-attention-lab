"use client"

import React from 'react'
import AutoUpdateManager from '@/components/AutoUpdateManager'

export default function SettingsTab({ onUpdate }: { onUpdate: () => void }) {
  return (
    <section>
      <AutoUpdateManager onUpdate={onUpdate} />
    </section>
  )
}
