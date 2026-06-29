"use client"

import { useState, useEffect, useCallback } from 'react'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import UpdateDialog, { type UpdateInfo } from '@/components/UpdateDialog'

export default function SettingsPage({ isActive }: { isActive?: boolean }) {
  const [showEmotion, setShowEmotion] = useState(true)
  const [currentVersion, setCurrentVersion] = useState("")
  const [checking, setChecking] = useState(false)
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null)
  const [noUpdateToast, setNoUpdateToast] = useState(false)

  useEffect(() => {
    if (isActive) {
      api.get<{ show_emotion_portrait?: boolean }>('/settings')
        .then((data) => setShowEmotion(data.show_emotion_portrait ?? true))
        .catch(() => {})
      // 获取当前版本号
      api.get<{ current_version: string }>('/update/check')
        .then((data) => setCurrentVersion(data.current_version))
        .catch(() => {})
    }
  }, [isActive])

  const handleToggle = async (v: boolean) => {
    setShowEmotion(v)
    await api.put('/settings', { show_emotion_portrait: v }).catch(() => {
      setShowEmotion(!v) // rollback on error
    })
  }

  const handleCheckUpdate = useCallback(async () => {
    setChecking(true)
    try {
      const data = await api.get<UpdateInfo>('/update/check?force=true')
      if (data.has_update) {
        setUpdateInfo(data)
      } else {
        setNoUpdateToast(true)
        setTimeout(() => setNoUpdateToast(false), 3000)
      }
    } catch {
      // 静默失败
    } finally {
      setChecking(false)
    }
  }, [])

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

        {/* Version & Update Check */}
        <div className="flex items-center justify-between bg-card border border-border rounded-xl p-4">
          <div className="flex-1 min-w-0 mr-4">
            <Label className="text-sm font-medium">版本</Label>
            <p className="text-xs text-muted-foreground mt-1">
              当前版本 v{currentVersion || "..."}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {noUpdateToast && (
              <span className="text-xs text-green-600 dark:text-green-400 animate-in fade-in">
                已是最新版本
              </span>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={handleCheckUpdate}
              disabled={checking}
            >
              {checking ? "检查中..." : "检查更新"}
            </Button>
          </div>
        </div>
      </div>

      {updateInfo && (
        <UpdateDialog
          open={true}
          onClose={() => setUpdateInfo(null)}
          info={updateInfo}
        />
      )}
    </div>
  )
}
