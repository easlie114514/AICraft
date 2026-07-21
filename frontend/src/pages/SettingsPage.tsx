"use client"

import { useState, useEffect, useCallback } from 'react'
import { Settings2, Smile, Bug, Zap, Repeat, Info, CheckCircle2, RefreshCw } from 'lucide-react'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api } from '@/lib/api'
import UpdateDialog, { type UpdateInfo } from '@/components/UpdateDialog'
import { SettingRow, SectionLabel, NumberStepper } from '@/components/settings-ui'

// ─── Skeleton ─────────────────────────────────────────────────────

function SettingsSkeleton() {
  return (
    <div className="space-y-6 pr-1">
      {[1, 2, 3].map((i) => (
        <div key={i}>
          <div className="flex items-center gap-2.5 mb-3 ml-1 animate-pulse">
            <div className="w-4 h-4 rounded bg-muted/60" />
            <div className="space-y-1.5">
              <div className="h-4 w-20 bg-muted/60 rounded" />
              <div className="h-3 w-32 bg-muted/40 rounded" />
            </div>
          </div>
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <div className="flex items-center justify-between gap-6 px-4 py-3.5 animate-pulse">
              <div className="space-y-2">
                <div className="h-4 w-28 bg-muted/50 rounded" />
                <div className="h-3 w-48 bg-muted/30 rounded" />
              </div>
              <div className="h-5 w-10 bg-muted/50 rounded-full" />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Main Component ───────────────────────────────────────────────

export default function SettingsPage({ isActive }: { isActive?: boolean }) {
  const [showEmotion, setShowEmotion] = useState(true)
  const [debugMode, setDebugMode] = useState(false)
  const [maxToolRounds, setMaxToolRounds] = useState(25)
  const [currentVersion, setCurrentVersion] = useState("")
  const [checking, setChecking] = useState(false)
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null)
  const [noUpdateToast, setNoUpdateToast] = useState(false)
  const [settingsLoading, setSettingsLoading] = useState(true)

  useEffect(() => {
    if (isActive) {
      setSettingsLoading(true)
      Promise.all([
        api.get<{ show_emotion_portrait?: boolean; debug_mode?: boolean; max_tool_rounds?: number }>('/settings')
          .then((data) => {
            setShowEmotion(data.show_emotion_portrait ?? true)
            setDebugMode(data.debug_mode ?? false)
            setMaxToolRounds(data.max_tool_rounds ?? 25)
          }),
        api.get<{ current_version: string }>('/update/check')
          .then((data) => setCurrentVersion(data.current_version)),
      ])
        .catch(() => {})
        .finally(() => setSettingsLoading(false))
    }
  }, [isActive])

  const handleToggle = async (v: boolean) => {
    setShowEmotion(v)
    await api.put('/settings', { show_emotion_portrait: v }).catch(() => {
      setShowEmotion(!v)
    })
  }

  const handleDebugMode = async (v: boolean) => {
    setDebugMode(v)
    await api.put('/settings', { debug_mode: v }).catch(() => {
      setDebugMode(!v)
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
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden p-6 animate-in fade-in duration-200">
      {/* Page Header */}
      <div className="shrink-0 flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/15 to-primary/5 ring-1 ring-primary/10 flex items-center justify-center shrink-0">
          <Settings2 className="w-5 h-5 text-primary" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-text-primary">设置</h2>
          <p className="text-xs text-text-tertiary">应用偏好与配置管理</p>
        </div>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        <div className="pr-1 pb-4">
          {settingsLoading ? (
            <SettingsSkeleton />
          ) : (
            <>
              {/* ── 对话体验 ── */}
              <SectionLabel icon={Smile} title="对话体验" description="聊天界面的展示和行为设置" />
              <div className="rounded-xl border border-border bg-card overflow-hidden mb-6">
                <SettingRow
                  title="显示 AI 情绪画像"
                  description="在聊天界面底部显示当前角色的像素风情绪头像"
                >
                  <Switch checked={showEmotion} onCheckedChange={handleToggle} />
                </SettingRow>
                <Separator />
                <SettingRow
                  title="调试模式"
                  description="开启后在聊天中展示工具调用、回答评分、角色切换等调试信息"
                >
                  <Switch checked={debugMode} onCheckedChange={handleDebugMode} />
                </SettingRow>
              </div>

              {/* ── 工具与性能 ── */}
              <SectionLabel icon={Zap} title="工具与性能" description="工具调用和行为控制" />
              <div className="rounded-xl border border-border bg-card overflow-hidden mb-6">
                <SettingRow
                  title="最大工具调用轮次"
                  description="LLM 连续调用工具的最大轮次，超过后自动停止（1-100）"
                >
                  <NumberStepper
                    value={maxToolRounds}
                    min={1}
                    max={100}
                    onChange={handleMaxToolRounds}
                  />
                </SettingRow>
              </div>

              {/* ── 关于 ── */}
              <SectionLabel icon={Info} title="关于" description="版本信息和更新" />
              <div className="rounded-xl border border-border bg-card overflow-hidden">
                <SettingRow
                  title="当前版本"
                  description={`v${currentVersion || "..."}`}
                >
                  <div className="flex items-center gap-2">
                    {noUpdateToast && (
                      <span className="inline-flex items-center gap-1 text-xs text-success bg-success-light border border-success/30 rounded-lg px-2 py-1 animate-in fade-in slide-in-from-right-2 duration-300">
                        <CheckCircle2 className="h-3 w-3" />
                        已是最新版本
                      </span>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleCheckUpdate}
                      disabled={checking}
                    >
                      {checking ? (
                        <span className="inline-flex items-center gap-1">
                          <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                          检查中...
                        </span>
                      ) : (
                        "检查更新"
                      )}
                    </Button>
                  </div>
                </SettingRow>
              </div>
            </>
          )}
        </div>
      </ScrollArea>

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
