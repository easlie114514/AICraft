"use client"

import { useState, useEffect } from 'react'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { api } from '@/lib/api'

export default function SettingsPage({ isActive }: { isActive?: boolean }) {
  const [showEmotion, setShowEmotion] = useState(true)

  useEffect(() => {
    if (isActive) {
      api.get<{ show_emotion_portrait?: boolean }>('/settings')
        .then((data) => setShowEmotion(data.show_emotion_portrait ?? true))
        .catch(() => {})
    }
  }, [isActive])

  const handleToggle = async (v: boolean) => {
    setShowEmotion(v)
    await api.put('/settings', { show_emotion_portrait: v }).catch(() => {
      setShowEmotion(!v) // rollback on error
    })
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden p-6">
      <h2 className="text-xl font-semibold text-text-primary mb-6">设置</h2>

      <div className="space-y-6 max-w-lg">
        {/* Emotion Portrait Toggle */}
        <div className="flex items-center justify-between bg-card border border-border rounded-xl p-4">
          <div className="flex-1 min-w-0 mr-4">
            <Label className="text-sm font-medium">显示 AI 情绪画像</Label>
            <p className="text-xs text-muted-foreground mt-1">
              在聊天界面底部显示当前角色的像素风情绪头像
            </p>
          </div>
          <Switch checked={showEmotion} onCheckedChange={handleToggle} />
        </div>
      </div>
    </div>
  )
}
