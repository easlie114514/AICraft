import { useState, useEffect, useRef, useCallback } from 'react'
import { Send, Square, RefreshCw, ArrowDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'

import { ScrollArea } from '@/components/ui/scroll-area'
import ChatMessage from '@/components/ChatMessage'
import ToolCallCard from '@/components/ToolCallCard'
import ProjectContextPopover from '@/components/ProjectContextPopover'
import ReplyGlowBar from '@/components/ReplyGlowBar'
import EmotionPortrait from '@/components/EmotionPortrait'
import PermissionDialog from '@/components/PermissionDialog'
import TokenPanel from '@/components/TokenPanel'
import { useChat } from '@/hooks/useChat'
import { api } from '@/lib/api'

const SCROLL_NEAR_BOTTOM_THRESHOLD = 60
const SCROLL_NEAR_TOP_THRESHOLD = 60
const SCROLL_THROTTLE_MS = 80  // 约 12fps，防止高频滚动造成视觉抖动

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
  const { messages, streaming, error, contextInfo, sceneCount, toggles, setToggles, debugMode, setDebugMode, sendMessage, stopStreaming, newScene, tokenStats, permissionRequest, respondPermission, emotion, emotionConfig, setEmotionConfig, hasOlderConversations, hasPreviousConversations, loadingOlder, loadLastConversation, loadOlderConversation } = useChat()

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
  const [isNearTop, setIsNearTop] = useState(true)

  // ── Smart auto-scroll: once user scrolls up during streaming, stop following ──
  const userPausedScrollRef = useRef(false)
  const streamingRef = useRef(false)
  streamingRef.current = streaming
  const isNearBottomRef = useRef(true)       // 同步读取，消除 state 竞态
  const lastScrollTimeRef = useRef(0)         // 滚动节流时间戳

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
    api.get<RoleOption[]>('/roles').then((data) => {
      setRoles(data)
      // Sync selectedRole when current role is changed externally (e.g. from RolePage)
      const cur = data.find((r) => r.is_current)
      if (cur) {
        setSelectedRole((prev) => (!prev || prev !== cur.name) ? cur.name : prev)
      }
    }).catch(() => {})
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
      // 加载全局情绪画像开关 & 调试模式
      api.get<{ show_emotion_portrait?: boolean; debug_mode?: boolean }>('/settings')
        .then((data) => {
          setShowEmotionGlobal(data.show_emotion_portrait ?? true)
          setDebugMode(data.debug_mode ?? false)
        })
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
    const now = performance.now()
    if (now - lastScrollTimeRef.current < SCROLL_THROTTLE_MS) return
    lastScrollTimeRef.current = now
    const el = viewportRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [])

  // Check if near bottom/top; if user scrolls away during streaming, pause auto-scroll
  const checkScrollPosition = useCallback(() => {
    const el = viewportRef.current
    if (!el) return
    const dist = el.scrollHeight - el.scrollTop - el.clientHeight
    const nearBottom = dist <= SCROLL_NEAR_BOTTOM_THRESHOLD
    isNearBottomRef.current = nearBottom  // 同步更新 ref，供 auto-scroll effect 立即读取
    setIsNearBottom(nearBottom)
    const nearTop = el.scrollTop <= SCROLL_NEAR_TOP_THRESHOLD
    setIsNearTop(nearTop)
    // User scrolled away during streaming → pause auto-follow until stream ends
    if (!nearBottom && streamingRef.current) {
      userPausedScrollRef.current = true
    }
  }, [])

  // Auto-scroll when messages change — but NOT if user has paused
  useEffect(() => {
    if (!userPausedScrollRef.current && isNearBottomRef.current) {
      requestAnimationFrame(scrollToBottom)
    }
  }, [messages, scrollToBottom])

  // wheel：用户在 AI 输出期间向上滚动 → 立即暂停自动跟随（比 scroll 事件更早触发）
  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (streamingRef.current && e.deltaY < 0) {
      userPausedScrollRef.current = true
    }
  }, [])

  // 记住最后一条用户消息（用于重试）
  const lastUserMessageRef = useRef('')

  const handleSend = (retry: boolean = false) => {
    const text = retry ? lastUserMessageRef.current : input.trim()
    if (!text || streaming) return
    if (!retry) {
      setInput('')
      lastUserMessageRef.current = text
    }
    userPausedScrollRef.current = false
    isNearBottomRef.current = true
    setIsNearBottom(true)
    scrollToBottom()
    sendMessage(text, selectedModel, selectedRole, toggles, retry)
    requestAnimationFrame(() => {
      userPausedScrollRef.current = false
      scrollToBottom()
    })
  }

  const handleSuggestionClick = (text: string) => {
    if (streaming) return
    lastUserMessageRef.current = text
    userPausedScrollRef.current = false
    isNearBottomRef.current = true
    setIsNearBottom(true)
    scrollToBottom()
    sendMessage(text, selectedModel, selectedRole, toggles, false)
    requestAnimationFrame(() => {
      userPausedScrollRef.current = false
      scrollToBottom()
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend(false)
    }
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden relative bg-nav-bg">
      {/* Messages */}
      <ScrollArea
        className="flex-1 min-h-0 px-4 bg-background rounded-b-[20px] chat-bg-pattern"
        viewportRef={(el: HTMLDivElement | null) => { viewportRef.current = el }}
        onScroll={checkScrollPosition}
        onWheel={handleWheel}
      >
        <div className="relative h-full">
        {/* 继续上次对话 — 绝对定位在顶部，不影响欢迎内容居中 */}
        {!hasMessages && hasPreviousConversations && (
          <div className="absolute top-0 left-0 right-0 flex justify-center pt-3 z-10">
            <Button
              variant="default"
              size="sm"
              onClick={loadLastConversation}
              disabled={loadingOlder}
              className="rounded-full shadow-lg hover:shadow-xl h-8 px-4 text-xs"
            >
              继续上次对话
            </Button>
          </div>
        )}

        {!hasMessages ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-12 px-4">
            {/* 欢迎图标 */}
            <div className="h-20 w-20 rounded-2xl bg-gradient-to-br from-primary/15 via-primary/10 to-primary/5 ring-1 ring-primary/10 flex items-center justify-center mb-5 shadow-sm">
              <Send className="h-9 w-9 text-primary/40" />
            </div>
            <h3 className="text-xl font-semibold text-text-primary mb-1.5">欢迎使用 AICraft</h3>
            <p className="text-sm text-text-secondary max-w-xs">AI 对话 · 技能调用 · 知识检索 · 角色定制</p>

            {/* 新手引导 — 两行各2个，点击直接发送 */}
            <div className="flex flex-wrap gap-2 justify-center mt-6">
              {[
                '用角色设计师帮我创建一个新角色',
                'AICraft 怎么上手呢？',
              ].map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => handleSuggestionClick(s)}
                  className="px-3.5 py-2 text-sm rounded-xl border border-border/50 bg-white hover:border-primary/30 hover:bg-primary-light/40 hover:text-primary transition-all duration-200 text-text-secondary shadow-sm hover:shadow-md"
                >
                  {s}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2 justify-center mt-2">
              {[
                '查一下当前百度热搜前三的新闻',
                '写一个html欢迎页放在桌面上',
              ].map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => handleSuggestionClick(s)}
                  className="px-3.5 py-2 text-sm rounded-xl border border-border/50 bg-white hover:border-primary/30 hover:bg-primary-light/40 hover:text-primary transition-all duration-200 text-text-secondary shadow-sm hover:shadow-md"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="py-4 space-y-0 relative">
            {/* 加载更早对话 — 滚动到顶时出现 */}
            {hasOlderConversations && isNearTop && (
              <div className="flex justify-center pb-3">
                <Button
                  variant="default"
                  size="sm"
                  onClick={loadOlderConversation}
                  disabled={loadingOlder}
                  className="rounded-full shadow-lg hover:shadow-xl h-8 px-4 text-xs"
                >
                  加载更早对话
                </Button>
              </div>
            )}
            {messages
              .filter((msg) => {
                // 调试模式：显示全部
                if (debugMode) return true
                // 非调试模式：隐藏所有 system 消息，但保留 auto_routing 和 context_reset
                if (msg.role === 'system') {
                  return msg.subtype === 'auto_routing' || msg.subtype === 'context_reset'
                }
                // 非调试模式：隐藏工具调用卡
                if (msg.role === 'tool_call' || msg.role === 'tool_result' || msg.role === 'tool') {
                  return false
                }
                return true
              })
              .map((msg, i, arr) => {
                // 工具调用卡片 — 内联在消息流中
                if (msg.role === 'tool_call' || msg.role === 'tool_result') {
                  return (
                    <ToolCallCard
                      key={msg.id}
                      name={msg.toolName || ''}
                      args={msg.role === 'tool_call' ? msg.toolArgs : undefined}
                      result={msg.role === 'tool_result' ? msg.toolResult : undefined}
                    />
                  )
                }
                // 找最近的上一条用户消息（用于反馈上下文）
                const prevUser = arr
                  .slice(0, i)
                  .filter((m) => m.role === 'user')
                  .at(-1)
                return (
                  <ChatMessage
                    key={msg.id}
                    message={msg}
                    convId={localStorage.getItem('aicraft_last_conv_id') || ''}
                    userMessage={prevUser?.content || ''}
                    onRetry={() => handleSend(true)}
                    streaming={streaming}
                  />
                )
              })}
            {error && (
              <div className="flex justify-center py-2">
                <span className="text-xs text-destructive bg-danger-light/60 px-3 py-1.5 rounded-lg">
                  {error}
                </span>
              </div>
            )}
          </div>
        )}
      </div>
      </ScrollArea>

      {/* ── 泛光条（聊天区与 Input 交接处，偏上 4px）── */}
      <div className="relative h-0 w-full z-10 pointer-events-none">
        <div className="absolute -top-[10px] left-0 right-0">
          <ReplyGlowBar active={streaming} />
        </div>
      </div>

      {/* Scroll-to-bottom floating button */}
      {!isNearBottom && hasMessages && (
        <div className="absolute bottom-[195px] left-1/2 -translate-x-1/2 z-10">
          <Button
            variant="default"
            size="sm"
            onClick={() => { userPausedScrollRef.current = false; isNearBottomRef.current = true; scrollToBottom(); setIsNearBottom(true) }}
            className="rounded-full shadow-lg hover:shadow-xl h-9 w-16 p-0"
          >
            <ArrowDown className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Input Area */}
      <div className="shrink-0 p-4 space-y-2 bg-nav-bg">

        {/* ── 工具栏行：开关 + 选择器 ── */}
        <div className="grid grid-cols-[1fr_auto_1fr] items-center bg-white shadow-sm border border-border/20 rounded-lg px-3 py-1.5">
          {/* 左：功能开关 */}
          <div className="flex items-center gap-4">
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
                id="toggle-rag"
                checked={toggles.rag}
                onCheckedChange={(v) => setToggles({ ...toggles, rag: v })}
              />
              <Label htmlFor="toggle-rag" className="text-xs text-text-secondary cursor-pointer">RAG检索</Label>
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
          </div>

          {/* 中：项目上下文 */}
          <div className="flex items-center">
            <ProjectContextPopover
              enabled={toggles.projectContext}
              onToggle={(v) => setToggles({ ...toggles, projectContext: v })}
            />
          </div>

          {/* 右：模型 / 角色 / Token / 新场景 */}
          <div className="flex items-center gap-1.5 justify-self-end">
            <Select value={selectedModel} onValueChange={(v) => setSelectedModel(v ?? '')}>
              <SelectTrigger className="w-[160px] h-8 text-sm">
                <SelectValue placeholder="模型" />
              </SelectTrigger>
              <SelectContent side="top" sideOffset={6} alignItemWithTrigger={false}>
                {models.map((m) => (
                  <SelectItem key={m.model_id} value={m.model_id}>
                    {m.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={selectedRole} onValueChange={(v) => setSelectedRole(v ?? '')}>
              <SelectTrigger className="w-[160px] h-8 text-sm">
                <SelectValue placeholder="角色" />
              </SelectTrigger>
              <SelectContent side="top" sideOffset={6} alignItemWithTrigger={false}>
                {roles.map((r) => (
                  <SelectItem key={r.name} value={r.name}>
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

            <Button
              variant="outline"
              size="sm"
              onClick={newScene}
              disabled={streaming || !hasMessages}
              className="rounded-lg h-8 text-xs"
            >
              新场景
            </Button>
          </div>
        </div>

        {/* ── 输入行：情绪画像 + 输入面板 ── */}
        <div className="flex gap-2">
          {/* Emotion Portrait — 保持不变 */}
          <EmotionPortrait
            roleName={selectedRole}
            emotion={emotion}
            available={emotionConfig?.available ?? []}
            visible={showEmotionGlobal}
            version={emotionVersion}
          />

          {/* 输入面板：Textarea + 发送 */}
          <div className="flex-1 bg-white border border-border rounded-xl shadow-card p-2 flex items-end gap-2">
            <Textarea
              placeholder="输入消息... (Shift+Enter 换行)"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              className="flex-1 h-20 resize-none overflow-y-auto"
              rows={1}
              disabled={streaming}
              maxLength={50000}
            />

            {streaming ? (
              <Button variant="destructive" size="icon" onClick={stopStreaming} className="h-20 w-10 rounded-lg shrink-0">
                <Square className="h-4 w-4" />
              </Button>
            ) : (
              <Button onClick={() => handleSend(false)} disabled={!input.trim()} size="icon" className="h-20 w-10 rounded-lg shrink-0">
                <Send className="h-4 w-4" />
              </Button>
            )}
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
