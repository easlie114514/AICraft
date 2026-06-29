import { useState, useEffect, useRef, useCallback } from 'react'
import { Send, Square, RefreshCw, ArrowDown, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import ChatMessage from '@/components/ChatMessage'
import EmotionPortrait from '@/components/EmotionPortrait'
import PermissionDialog from '@/components/PermissionDialog'
import TokenPanel from '@/components/TokenPanel'
import { useChat } from '@/hooks/useChat'
import { api } from '@/lib/api'

const SCROLL_NEAR_BOTTOM_THRESHOLD = 60

interface ModelOption {
  name: string
  model_id: string
  is_current?: boolean
}

interface RoleOption {
  name: string
  is_current?: boolean
}

export default function ChatPage({ isActive }: { isActive?: boolean }) {
  const { messages, streaming, error, contextInfo, sceneCount, toggles, setToggles, sendMessage, stopStreaming, newScene, tokenStats, permissionRequest, respondPermission, emotion, emotionConfig, setEmotionConfig } = useChat()

  const hasMessages = messages.filter((m) => m.role === 'user' || m.role === 'assistant').length > 0
  const [input, setInput] = useState('')
  const [models, setModels] = useState<ModelOption[]>([])
  const [roles, setRoles] = useState<RoleOption[]>([])
  const [selectedModel, setSelectedModel] = useState('')
  const [selectedRole, setSelectedRole] = useState('')
  const [tokenPanelOpen, setTokenPanelOpen] = useState(false)
  const [showEmotionGlobal, setShowEmotionGlobal] = useState(true)
  const [emotionVersion, setEmotionVersion] = useState(0)
  const viewportRef = useRef<HTMLDivElement | null>(null)
  const [isNearBottom, setIsNearBottom] = useState(true)

  // ── Smart auto-scroll: once user scrolls up during streaming, stop following ──
  const userPausedScrollRef = useRef(false)
  const streamingRef = useRef(false)
  streamingRef.current = streaming

  // Reset the pause flag when streaming ends
  const prevStreamingRef = useRef(false)
  useEffect(() => {
    const wasStreaming = prevStreamingRef.current
    prevStreamingRef.current = streaming
    if (wasStreaming && !streaming) {
      // Stream just ended — reset pause for next round
      userPausedScrollRef.current = false
    }
  }, [streaming])

  // Load models and roles (prepend Auto option)
  const loadRoles = useCallback(() => {
    api.get<RoleOption[]>('/roles').then(setRoles).catch(() => {})
  }, [])

  const loadModels = useCallback(() => {
    api.get<ModelOption[]>('/models').then((data) => {
      setModels([{ name: '⚡ Auto（智能路由）', model_id: 'auto', is_current: false }, ...data])
    }).catch(() => {})
  }, [])

  useEffect(() => {
    loadModels()
    loadRoles()
    window.addEventListener('roles-changed', loadRoles)
    return () => window.removeEventListener('roles-changed', loadRoles)
  }, [loadModels, loadRoles])

  // Bump version whenever emotion changes → cache-bust portrait images
  useEffect(() => {
    if (emotion) {
      setEmotionVersion(v => v + 1)
    }
  }, [emotion])

  // Re-fetch roles when tab becomes active (e.g. returning from RolePage after external changes)
  useEffect(() => {
    if (isActive) {
      loadModels()
      loadRoles()
      // 加载全局情绪画像开关
      api.get<{ show_emotion_portrait?: boolean }>('/settings')
        .then((data) => setShowEmotionGlobal(data.show_emotion_portrait ?? true))
        .catch(() => {})
    }
  }, [isActive, loadModels, loadRoles])

  // Set defaults (Auto is default when no model selected)
  useEffect(() => {
    if (models.length && !selectedModel) {
      setSelectedModel('auto')
    }
  }, [models, selectedModel])

  useEffect(() => {
    if (roles.length && !selectedRole) {
      const cur = roles.find((r) => r.is_current) || roles[0]
      setSelectedRole(cur.name)
    }
  }, [roles, selectedRole])

  // Persist role choice to backend when user changes role
  useEffect(() => {
    if (selectedRole) {
      api.put('/roles/current', { name: selectedRole }).catch(() => {})
      // 加载当前角色的情绪画像配置
      ;(async () => {
        const emotionData = await api.get<{ enabled: boolean; available: string[] }>(`/roles/${encodeURIComponent(selectedRole)}/emotion`).catch(() => null)
        if (emotionData) {
          setEmotionConfig({ available: emotionData.available, enabled: emotionData.enabled })
        } else {
          setEmotionConfig(null)
        }
      })()
    }
  }, [selectedRole])

  // ── Scroll helpers ──

  const scrollToBottom = useCallback(() => {
    const el = viewportRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [])

  // Check if near bottom; if user scrolls away during streaming, pause auto-scroll
  const checkNearBottom = useCallback(() => {
    const el = viewportRef.current
    if (!el) return
    const dist = el.scrollHeight - el.scrollTop - el.clientHeight
    const near = dist <= SCROLL_NEAR_BOTTOM_THRESHOLD
    setIsNearBottom(near)
    // User scrolled away during streaming → pause auto-follow until stream ends
    if (!near && streamingRef.current) {
      userPausedScrollRef.current = true
    }
  }, [])

  // Auto-scroll when messages change — but NOT if user has paused
  useEffect(() => {
    if (!userPausedScrollRef.current && isNearBottom) {
      requestAnimationFrame(scrollToBottom)
    }
  }, [messages, isNearBottom, scrollToBottom])

  // When streaming starts and user hasn't paused, scroll to bottom (catch late-arriving renders)
  useEffect(() => {
    if (streaming && !userPausedScrollRef.current) {
      const id = setTimeout(() => {
        if (!userPausedScrollRef.current && isNearBottom) scrollToBottom()
      }, 50)
      return () => clearTimeout(id)
    }
  }, [streaming, isNearBottom, scrollToBottom])

  const handleSend = () => {
    const text = input.trim()
    if (!text || streaming) return
    setInput('')
    // Reset pause and force scroll to bottom when user sends a message
    userPausedScrollRef.current = false
    setIsNearBottom(true)
    scrollToBottom()
    sendMessage(text, selectedModel, selectedRole, toggles)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden relative">
      {/* Messages */}
      <ScrollArea
        className="flex-1 min-h-0 px-4"
        viewportRef={(el: HTMLDivElement | null) => { viewportRef.current = el }}
        onScroll={checkNearBottom}
      >
        {!hasMessages ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-20">
            <div className="h-16 w-16 rounded-full bg-primary-light flex items-center justify-center mb-4">
              <Send className="h-7 w-7 text-primary/40" />
            </div>
            <p className="text-lg text-text-secondary">开始新对话</p>
            <p className="text-sm text-text-tertiary mt-1">输入消息，AI 将为你解答</p>
          </div>
        ) : (
          <div className="py-4 space-y-0 relative">
            {messages
              .filter((msg) => msg.role !== 'tool_call' && msg.role !== 'tool_result')
              .map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}
            {error && (
              <div className="flex justify-center py-2">
                <span className="text-xs text-destructive bg-danger-light/60 px-3 py-1.5 rounded-lg">
                  {error}
                </span>
              </div>
            )}
          </div>
        )}
      </ScrollArea>

      {/* Scroll-to-bottom floating button */}
      {!isNearBottom && hasMessages && (
        <div className="absolute bottom-[140px] left-1/2 -translate-x-1/2 z-10">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => { userPausedScrollRef.current = false; scrollToBottom(); setIsNearBottom(true) }}
            className="rounded-lg shadow-lg h-8 w-8 p-0"
          >
            <ArrowDown className="h-4 w-4" />
          </Button>
        </div>
      )}

      <Separator />

      {/* Input Area */}
      <div className="shrink-0 p-4">
        <div className="flex gap-2">
          {/* Emotion Portrait */}
          <EmotionPortrait
            roleName={selectedRole}
            emotion={emotion}
            available={emotionConfig?.available ?? []}
            visible={showEmotionGlobal}
            version={emotionVersion}
          />

          <div className="flex-1 bg-white border border-border rounded-xl shadow-card pl-2.5 pr-3 py-[10px] space-y-2">
        {/* Toggles */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <Switch
              id="toggle-rag"
              checked={toggles.rag}
              onCheckedChange={(v) => setToggles({ ...toggles, rag: v })}
            />
            <Label htmlFor="toggle-rag" className="text-xs text-text-secondary cursor-pointer">RAG检索</Label>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              id="toggle-memory"
              checked={toggles.memory}
              onCheckedChange={(v) => setToggles({ ...toggles, memory: v })}
            />
            <Label htmlFor="toggle-memory" className="text-xs text-text-secondary cursor-pointer">记忆注入</Label>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              id="toggle-thinking"
              checked={toggles.thinking}
              onCheckedChange={(v) => setToggles({ ...toggles, thinking: v })}
            />
            <Label htmlFor="toggle-thinking" className="text-xs text-text-secondary cursor-pointer">深度思考</Label>
          </div>

          {/* Context Budget Indicator */}
          {contextInfo && (
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded-full font-mono ${
                contextInfo.pct >= 90
                  ? 'bg-danger-light text-danger'
                  : contextInfo.pct >= 75
                  ? 'bg-warning-light text-warning'
                  : 'bg-muted text-text-secondary'
              }`}
              title={`已用 ${contextInfo.totalTokens.toLocaleString()} / ${contextInfo.inputBudget.toLocaleString()} tokens`}
            >
              📊 {contextInfo.pct}%
            </span>
          )}

          {/* 新场景按钮 */}
          <Button
            variant="outline"
            size="sm"
            onClick={newScene}
            disabled={streaming || !hasMessages}
            className="rounded-lg h-7 text-xs ml-auto"
          >
            <Plus className="h-3 w-3 mr-1" />
            新场景
          </Button>
        </div>

        {/* Input Row */}
        <div className="flex items-end gap-2">
          <Textarea
            placeholder="输入消息... (Shift+Enter 换行)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 min-h-[40px] max-h-[120px] resize-none"
            rows={1}
            disabled={streaming}
          />

          <Select value={selectedModel} onValueChange={(v) => setSelectedModel(v ?? '')}>
            <SelectTrigger className="w-[150px] !h-auto self-stretch text-xs">
              <SelectValue placeholder="模型" />
            </SelectTrigger>
            <SelectContent sideOffset={6}>
              {models.map((m) => (
                <SelectItem key={m.model_id} value={m.model_id} className="text-xs">
                  {m.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={selectedRole} onValueChange={(v) => setSelectedRole(v ?? '')}>
            <SelectTrigger className="w-[90px] !h-auto self-stretch text-xs">
              <SelectValue placeholder="角色" />
            </SelectTrigger>
            <SelectContent sideOffset={6}>
              {roles.map((r) => (
                <SelectItem key={r.name} value={r.name} className="text-xs">
                  {r.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <TokenPanel
            stats={tokenStats}
            isOpen={tokenPanelOpen}
            onToggle={() => setTokenPanelOpen((v) => !v)}
          />

          {streaming ? (
            <Button variant="destructive" size="icon" onClick={stopStreaming} className="h-10 min-w-[56px] px-3 rounded-lg shrink-0">
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <Button onClick={handleSend} disabled={!input.trim()} className="h-10 min-w-[86px] rounded-lg shrink-0">
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>
        </div>
        </div>
      </div>

      {/* Permission Dialog — overlaid on top of everything */}
      <PermissionDialog
        request={permissionRequest}
        onResponse={respondPermission}
      />
    </div>
  )
}
