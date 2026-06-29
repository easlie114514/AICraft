"use client"

import { useState, useEffect, useCallback } from 'react'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import UpdateDialog, { type UpdateInfo } from '@/components/UpdateDialog'

export default function SettingsPage({ isActive }: { isActive?: boolean }) {
  const [showEmotion, setShowEmotion] = useState(true)
  const [maxToolRounds, setMaxToolRounds] = useState(25)
  const [currentVersion, setCurrentVersion] = useState("")
  const [checking, setChecking] = useState(false)
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null)
  const [noUpdateToast, setNoUpdateToast] = useState(false)

  useEffect(() => {
    if (isActive) {
      api.get<{ show_emotion_portrait?: boolean; max_tool_rounds?: number }>('/settings')
        .then((data) => {
          setShowEmotion(data.show_emotion_portrait ?? true)
          setMaxToolRounds(data.max_tool_rounds ?? 25)
        })
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

  const handleMaxToolRounds = async (v: number) => {
    const clamped = Math.max(1, Math.min(100, v))
    setMaxToolRounds(clamped)
    await api.put('/settings', { max_tool_rounds: clamped }).catch(() => {})
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

        {/* Max Tool Rounds */}
        <div className="flex items-center justify-between bg-card border border-border rounded-xl p-4">
          <div className="flex-1 min-w-0 mr-4">
            <Label className="text-sm font-medium">最大工具调用轮次</Label>
            <p className="text-xs text-muted-foreground mt-1">
              LLM 连续调用工具的最大轮次，超过后自动停止（1-100）
            </p>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              disabled={maxToolRounds <= 1}
              onClick={() => handleMaxToolRounds(maxToolRounds - 1)}
            >
              −
            </Button>
            <input
              type="number"
              min={1}
              max={100}
              value={maxToolRounds}
              onChange={(e) => {
                const v = parseInt(e.target.value, 10)
                if (!isNaN(v)) handleMaxToolRounds(v)
              }}
              className="h-8 w-14 text-center text-sm border border-border rounded-md bg-background text-text-primary [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
            />
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              disabled={maxToolRounds >= 100}
              onClick={() => handleMaxToolRounds(maxToolRounds + 1)}
            >
              +
            </Button>
          </div>
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
