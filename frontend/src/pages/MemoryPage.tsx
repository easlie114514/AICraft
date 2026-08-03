import { useState, useEffect, useCallback } from 'react'
import { Eye, Trash2, Search, RefreshCw, FileText, MessageSquare, Settings2, Merge, RotateCcw, CheckCircle2, AlertCircle, ChevronDown, Brain } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { api } from '@/lib/api'
import { themeCardGradient, clamp } from '@/lib/utils'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'

interface Conversation {
  id: string
  created: string
  model: string
  role: string
  message_count: number
}

interface Note {
  name: string
  filename: string
  preview: string
  path: string
  kind: 'compact' | 'long_term'
  chars: number
  tokens: number
}

interface SearchResult {
  results: string[]
}

interface MemoryStats {
  compact_count: number
  compact_total_chars: number
  compact_total_tokens: number
  long_term_size: number
  long_term_tokens: number
}

interface MemoryConfig {
  max_history_chars: number
  memory_compact_enabled: boolean
  memory_compact_trigger: string
  memory_compact_interval_chars: number
  memory_compact_interval_msgs: number
  memory_compact_window: number
  memory_compact_max_tokens: number
  memory_merge_threshold: number
  memory_inject_max_chars: number
  memory_inject_strategy: string
  cross_session_inject_count: number
  context_budget_enabled: boolean
  context_window_override: number
  output_reserve_ratio: number
  budget_alert_threshold: number
}

const DEFAULT_CONFIG: MemoryConfig = {
  max_history_chars: 50000,
  memory_compact_enabled: true,
  memory_compact_trigger: 'messages',
  memory_compact_interval_chars: 8000,
  memory_compact_interval_msgs: 20,
  memory_compact_window: 40,
  memory_compact_max_tokens: 800,
  memory_merge_threshold: 8,
  memory_inject_max_chars: 4000,
  memory_inject_strategy: 'latest',
  cross_session_inject_count: 10,
  context_budget_enabled: true,
  context_window_override: 0,
  output_reserve_ratio: 0.20,
  budget_alert_threshold: 0.75,
}

export default function MemoryPage() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [notes, setNotes] = useState<Note[]>([])
  const [viewConv, setViewConv] = useState<Record<string, unknown> | null>(null)
  const [viewNote, setViewNote] = useState<{ name: string; content: string; kind: string } | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [deleteTargetType, setDeleteTargetType] = useState<'conv' | 'note'>('conv')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<string[]>([])
  const [activeTab, setActiveTab] = useState('conversations')

  // ── 记忆设置状态 ──
  const [config, setConfig] = useState<MemoryConfig>(DEFAULT_CONFIG)
  const [stats, setStats] = useState<MemoryStats>({ compact_count: 0, compact_total_chars: 0, compact_total_tokens: 0, long_term_size: 0, long_term_tokens: 0 })
  const [configLoaded, setConfigLoaded] = useState(false)
  const [convsLoading, setConvsLoading] = useState(true)
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false)

  const loadConversations = useCallback(async () => {
    setConvsLoading(true)
    try {
      const data = await api.get<Conversation[]>('/memory/conversations')
      setConversations(data)
    } catch { /* ignore */ }
    finally { setConvsLoading(false) }
  }, [])

  const loadNotes = useCallback(async () => {
    try {
      const data = await api.get<Note[]>('/memory/notes')
      setNotes(data)
    } catch { /* ignore */ }
  }, [])

  const loadConfig = useCallback(async () => {
    try {
      const data = await api.get<MemoryConfig>('/memory/config')
      setConfig(data)
      setConfigLoaded(true)
    } catch { /* ignore */ }
  }, [])

  const loadStats = useCallback(async () => {
    try {
      const data = await api.get<MemoryStats>('/memory/stats')
      setStats(data)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    loadConversations()
    loadNotes()
    loadConfig()
    loadStats()
  }, [loadConversations, loadNotes, loadConfig, loadStats])

  const handleView = async (id: string) => {
    try {
      const data = await api.get<Record<string, unknown>>(`/memory/conversations/${encodeURIComponent(id)}`)
      setViewConv(data)
    } catch { /* ignore */ }
  }

  const handleDeleteConv = async (id: string) => {
    await api.delete(`/memory/conversations/${encodeURIComponent(id)}`)
    loadConversations()
  }

  const handleViewNote = async (filename: string) => {
    try {
      const data = await api.get<{ name: string; content: string; kind: string }>(
        `/memory/notes/${encodeURIComponent(filename)}`
      )
      setViewNote(data)
    } catch { /* ignore */ }
  }

  const handleDeleteNote = async (filename: string) => {
    await api.delete(`/memory/notes/${encodeURIComponent(filename)}`)
    loadNotes()
    loadStats()
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    try {
      const data = await api.post<SearchResult>('/memory/search', { query: searchQuery, top_k: 5 })
      setSearchResults(data.results)
    } catch { /* ignore */ }
  }

  // ── 设置操作 ──

  const handleSaveConfig = async () => {
    try {
      await api.put('/memory/config', config)
      loadStats()
    } catch { /* ignore */ }
  }

  const handleResetConfig = () => {
    setResetConfirmOpen(true)
  }

  const confirmReset = () => {
    setConfig(DEFAULT_CONFIG)
    setResetConfirmOpen(false)
  }

  const handleMergeNow = async () => {
    try {
      const result = await api.post<{ ok: boolean; message: string }>('/memory/merge', {})
      if (result.ok) {
        loadNotes()
        loadStats()
      }
      setNotification({ type: result.ok ? 'success' : 'error', message: result.message || (result.ok ? '合并完成' : '合并失败') })
      setTimeout(() => setNotification(null), 3000)
    } catch { /* ignore */ }
  }

  const updateConfig = <K extends keyof MemoryConfig>(key: K, value: MemoryConfig[K]) => {
    setConfig(prev => ({ ...prev, [key]: value }))
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden p-6 animate-in fade-in duration-200">
      <div className="shrink-0 flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/15 to-primary/5 ring-1 ring-primary/10 flex items-center justify-center shrink-0">
            <Brain className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-text-primary">记忆</h2>
            <p className="text-xs text-text-tertiary">管理对话历史、记忆巩固与注入策略</p>
          </div>
        </div>
        <Button variant="outline" size="icon" onClick={() => { loadConversations(); loadNotes(); loadStats() }}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {/* Search */}
      <div className="shrink-0 relative flex items-center gap-2 mb-4">
        <Input
          placeholder="搜索记忆..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="flex-1 rounded-lg bg-card border border-border"
          maxLength={200}
        />
        <Button variant="outline" size="icon" onClick={handleSearch} className="shrink-0">
          <Search className="h-4 w-4" />
        </Button>

        {/* 搜索结果下拉浮层 */}
        {searchResults.length > 0 && (
          <Card className="absolute top-full left-0 right-0 mt-1 z-10 shadow-dropdown max-h-48 overflow-y-auto">
            <CardContent className="p-2 space-y-1">
              <p className="text-[10px] font-medium text-text-tertiary px-2 pt-1">搜索结果</p>
              {searchResults.map((r, i) => (
                <div key={i} className="text-xs p-2 rounded-md hover:bg-muted cursor-pointer whitespace-pre-wrap break-all">
                  {r}
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
        <TabsList className="w-fit mb-4" variant="line">
          <TabsTrigger value="conversations">
            <MessageSquare className="h-4 w-4 mr-1" />
            对话历史
          </TabsTrigger>
          <TabsTrigger value="notes">
            <FileText className="h-4 w-4 mr-1" />
            记忆巩固
          </TabsTrigger>
          <TabsTrigger value="settings">
            <Settings2 className="h-4 w-4 mr-1" />
            记忆设置
          </TabsTrigger>
        </TabsList>

        {/* ── 对话历史 Tab ── */}
        <TabsContent value="conversations" className="flex-1 flex flex-col min-h-0 overflow-hidden">
          <div className="flex-1 min-h-0 overflow-y-auto">
            {convsLoading ? (
              <div className="grid gap-3 pr-1">
                {[1, 2, 3].map((i) => (
                  <Card key={i} className="border-0 text-white" style={themeCardGradient(true)}>
                    <CardContent className="p-3">
                      <div className="flex items-center justify-between animate-pulse">
                        <div className="flex-1 space-y-2">
                          <div className="flex items-center gap-2">
                            <div className="h-4 w-48 bg-white/15 rounded font-mono" />
                            <div className="h-4 w-14 bg-white/10 rounded-lg" />
                          </div>
                          <div className="h-3 w-40 bg-white/10 rounded" />
                        </div>
                        <div className="flex items-center gap-1">
                          <div className="h-8 w-8 bg-white/10 rounded" />
                          <div className="h-8 w-8 bg-white/10 rounded" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : conversations.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
                <MessageSquare className="h-10 w-10 mb-2 text-text-disabled" />
                <p className="text-sm text-text-secondary">暂无对话历史</p>
              </div>
            ) : (
              <div className="grid gap-3 pr-1">
                {conversations.map((c) => (
                  <Card key={c.id} className="relative overflow-hidden group border-0 text-white transition-colors duration-300" style={themeCardGradient(true)}>
                    <CardContent className="p-3 relative z-10">
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium font-mono text-white/90">{c.id}</span>
                            <span className="text-[10px] bg-white/12 backdrop-blur-sm px-1.5 py-0.5 rounded-md text-white/70">{c.message_count} 条消息</span>
                          </div>
                          <p className="text-xs text-white/45 mt-0.5">
                            {c.created} &middot; {c.model} &middot; {c.role}
                          </p>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          <Button variant="ghost" size="sm" onClick={() => handleView(c.id)} className="text-white/55 hover:text-white hover:bg-white/8">
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => { setDeleteTargetType('conv'); setDeleteTarget(c.id) }} className="text-white/35 hover:text-red-200/80 hover:bg-white/8">
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </TabsContent>

        {/* ── 长期碎片记忆 Tab ── */}
        <TabsContent value="notes" className="flex-1 flex flex-col min-h-0 overflow-hidden">
          <div className="flex-1 min-h-0 overflow-y-auto">
            {notes.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
                <FileText className="h-10 w-10 mb-2 text-text-disabled" />
                <p className="text-sm text-text-secondary">暂无记忆巩固记录</p>
                <p className="text-xs text-text-tertiary mt-1">对话过程中会自动压缩生成</p>
              </div>
            ) : (
              <div className="grid gap-3 pr-1">
                {notes.map((n) => (
                  <Card key={n.name} className="relative overflow-hidden group border-0 text-white transition-colors duration-300" style={themeCardGradient(true)}>
                    <CardContent className="p-3 relative z-10">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-md shrink-0 ${n.kind === 'long_term' ? 'bg-white/18 backdrop-blur-sm text-white/85' : 'bg-white/8 text-white/55'}`}>
                            {n.kind === 'long_term' ? '长期记忆' : '短期'}
                          </span>
                          <span className="text-sm font-medium truncate text-white/90">{n.name}</span>
                          <span className="text-[10px] text-white/40 shrink-0">{formatTokens(n.tokens)}</span>
                        </div>
                        <div className="flex items-center gap-0.5 shrink-0 ml-2">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleViewNote(n.filename)}
                            className="h-8 w-8 text-white/50 hover:text-white hover:bg-white/8"
                            title="查看全文"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => { setDeleteTargetType('note'); setDeleteTarget(n.filename) }}
                            className="h-8 w-8 text-white/30 hover:text-red-200/80 hover:bg-white/8"
                            title="删除"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                      <p className="text-xs text-white/45 mt-1 truncate">{n.preview}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </TabsContent>

        {/* ── 记忆设置 Tab ── */}
        <TabsContent value="settings" className="flex-1 flex flex-col min-h-0 overflow-hidden">
          <ScrollArea className="flex-1 min-h-0">
            <div className="space-y-4 pr-1 pb-4">
              {/* 压缩开关 */}
              <Card className="hover:shadow-card-hover transition-shadow duration-200">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="compact-enabled" className="text-sm font-medium">记忆压缩</Label>
                    <Switch
                      id="compact-enabled"
                      checked={config.memory_compact_enabled}
                      onCheckedChange={(v) => updateConfig('memory_compact_enabled', v)}
                    />
                  </div>
                </CardContent>
              </Card>

              {/* 触发条件 */}
              <Collapsible defaultOpen={true}>
                <Card className="hover:shadow-card-hover transition-shadow duration-200">
                  <CardContent className="p-4 space-y-3">
                    <CollapsibleTrigger className="flex items-center gap-2 cursor-pointer hover:text-primary transition-colors">
                      <ChevronDown className="h-4 w-4" />
                      <span className="text-sm font-medium">触发条件</span>
                    </CollapsibleTrigger>
                    <CollapsibleContent className="space-y-3 data-[open]:mt-3">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-muted-foreground">触发方式</Label>
                    <Select
                      value={config.memory_compact_trigger}
                      onValueChange={(v) => updateConfig('memory_compact_trigger', v ?? 'chars')}
                    >
                      <SelectTrigger className="w-36 rounded-lg h-8 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="chars">按字符数</SelectItem>
                        <SelectItem value="messages">按消息条数</SelectItem>
                        <SelectItem value="both">两者任一</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-muted-foreground">字符阈值</Label>
                    <div className="flex items-center gap-1">
                      <Input
                        type="number"
                        min={1000}
                        value={config.memory_compact_interval_chars}
                        onChange={(e) => {
                          const v = Number(e.target.value)
                          if (e.target.value === '' || isNaN(v)) return
                          updateConfig('memory_compact_interval_chars', clamp(v, 1000, 1000000))
                        }}
                        className="w-24 h-8 rounded-lg text-xs"
                      />
                      <span className="text-xs text-muted-foreground">字符</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-muted-foreground">条数阈值</Label>
                    <div className="flex items-center gap-1">
                      <Input
                        type="number"
                        min={5}
                        value={config.memory_compact_interval_msgs}
                        onChange={(e) => {
                          const v = Number(e.target.value)
                          if (e.target.value === '' || isNaN(v)) return
                          updateConfig('memory_compact_interval_msgs', clamp(v, 5, 1000))
                        }}
                        className="w-24 h-8 rounded-lg text-xs"
                      />
                      <span className="text-xs text-muted-foreground">条消息</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-muted-foreground">压缩窗口</Label>
                    <div className="flex items-center gap-1">
                      <Input
                        type="number"
                        min={10}
                        max={200}
                        value={config.memory_compact_window}
                        onChange={(e) => {
                          const v = Number(e.target.value)
                          if (e.target.value === '' || isNaN(v)) return
                          updateConfig('memory_compact_window', clamp(v, 10, 200))
                        }}
                        className="w-24 h-8 rounded-lg text-xs"
                      />
                      <span className="text-xs text-muted-foreground">条消息</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-muted-foreground">压缩输出上限</Label>
                    <div className="flex items-center gap-1">
                      <Input
                        type="number"
                        min={100}
                        max={4000}
                        value={config.memory_compact_max_tokens}
                        onChange={(e) => {
                          const v = Number(e.target.value)
                          if (e.target.value === '' || isNaN(v)) return
                          updateConfig('memory_compact_max_tokens', clamp(v, 100, 4000))
                        }}
                        className="w-24 h-8 rounded-lg text-xs"
                      />
                      <span className="text-xs text-muted-foreground">tokens</span>
                    </div>
                  </div>
                    </CollapsibleContent>
                  </CardContent>
                </Card>
              </Collapsible>

              {/* 长期记忆 */}
              <Card className="hover:shadow-card-hover transition-shadow duration-200">
                <CardContent className="p-4 space-y-3">
                  <p className="text-sm font-medium">长期记忆</p>
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-muted-foreground">自动合并阈值</Label>
                    <div className="flex items-center gap-1">
                      <Input
                        type="number"
                        min={2}
                        max={50}
                        value={config.memory_merge_threshold}
                        onChange={(e) => {
                          const v = Number(e.target.value)
                          if (e.target.value === '' || isNaN(v)) return
                          updateConfig('memory_merge_threshold', clamp(v, 2, 50))
                        }}
                        className="w-24 h-8 rounded-lg text-xs"
                      />
                      <span className="text-xs text-muted-foreground">个片段</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* 注入控制 */}
              <Collapsible defaultOpen={true}>
                <Card className="hover:shadow-card-hover transition-shadow duration-200">
                  <CardContent className="p-4 space-y-3">
                    <CollapsibleTrigger className="flex items-center gap-2 cursor-pointer hover:text-primary transition-colors">
                      <ChevronDown className="h-4 w-4" />
                      <span className="text-sm font-medium">注入控制</span>
                    </CollapsibleTrigger>
                    <CollapsibleContent className="space-y-3 data-[open]:mt-3">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-muted-foreground">注入上限</Label>
                    <div className="flex items-center gap-1">
                      <Input
                        type="number"
                        min={500}
                        max={50000}
                        value={config.memory_inject_max_chars}
                        onChange={(e) => {
                          const v = Number(e.target.value)
                          if (e.target.value === '' || isNaN(v)) return
                          updateConfig('memory_inject_max_chars', clamp(v, 500, 50000))
                        }}
                        className="w-24 h-8 rounded-lg text-xs"
                      />
                      <span className="text-xs text-muted-foreground">字符</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-muted-foreground">注入策略</Label>
                    <Select
                      value={config.memory_inject_strategy}
                      onValueChange={(v) => updateConfig('memory_inject_strategy', v ?? 'latest')}
                    >
                      <SelectTrigger className="w-36 rounded-lg h-8 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="latest">最近优先</SelectItem>
                        <SelectItem value="relevant">RAG检索</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-muted-foreground">跨会话条数</Label>
                    <div className="flex items-center gap-1">
                      <Input
                        type="number"
                        min={0}
                        max={50}
                        value={config.cross_session_inject_count}
                        onChange={(e) => {
                          const v = Number(e.target.value)
                          if (e.target.value === '' || isNaN(v)) return
                          updateConfig('cross_session_inject_count', clamp(v, 0, 50))
                        }}
                        className="w-24 h-8 rounded-lg text-xs"
                      />
                      <span className="text-xs text-muted-foreground">条</span>
                    </div>
                  </div>
                    </CollapsibleContent>
                  </CardContent>
                </Card>
              </Collapsible>

              {/* 上下文预算 */}
              <Collapsible defaultOpen={true}>
                <Card className="hover:shadow-card-hover transition-shadow duration-200">
                  <CardContent className="p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <CollapsibleTrigger className="flex items-center gap-2 cursor-pointer hover:text-primary transition-colors">
                        <ChevronDown className="h-4 w-4" />
                        <span className="text-sm font-medium">上下文预算</span>
                      </CollapsibleTrigger>
                      <p className="text-xs text-muted-foreground flex-1 ml-4">统筹所有注入内容，防止超出模型窗口</p>
                      <Switch
                        id="budget-enabled"
                        checked={config.context_budget_enabled}
                        onCheckedChange={(v) => updateConfig('context_budget_enabled', v)}
                      />
                    </div>
                    {config.context_budget_enabled && (
                      <CollapsibleContent className="space-y-3 data-[open]:mt-3">
                      <Separator />
                      <div className="flex items-center justify-between">
                        <Label className="text-xs text-muted-foreground">窗口覆盖 (0=自动)</Label>
                        <div className="flex items-center gap-1">
                          <Input
                            type="number"
                            min={0}
                            max={1000000}
                            step={1000}
                            value={config.context_window_override}
                            onChange={(e) => {
                              const v = Number(e.target.value)
                              if (e.target.value === '' || isNaN(v)) return
                              updateConfig('context_window_override', clamp(v, 0, 1000000))
                            }}
                            className="w-24 h-8 rounded-lg text-xs"
                          />
                          <span className="text-xs text-muted-foreground">tokens</span>
                        </div>
                      </div>
                      <div className="flex items-center justify-between">
                        <Label className="text-xs text-muted-foreground">输出预留比例</Label>
                        <div className="flex items-center gap-1">
                          <Input
                            type="number"
                            min={0.05}
                            max={0.50}
                            step={0.05}
                            value={config.output_reserve_ratio}
                            onChange={(e) => {
                              const v = Number(e.target.value)
                              if (e.target.value === '' || isNaN(v)) return
                              updateConfig('output_reserve_ratio', clamp(v, 0.05, 0.50))
                            }}
                            className="w-24 h-8 rounded-lg text-xs"
                          />
                          <span className="text-xs text-muted-foreground">{(config.output_reserve_ratio * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                      <div className="flex items-center justify-between">
                        <Label className="text-xs text-muted-foreground">告警阈值</Label>
                        <div className="flex items-center gap-1">
                          <Input
                            type="number"
                            min={0.25}
                            max={1.0}
                            step={0.05}
                            value={config.budget_alert_threshold}
                            onChange={(e) => {
                              const v = Number(e.target.value)
                              if (e.target.value === '' || isNaN(v)) return
                              updateConfig('budget_alert_threshold', clamp(v, 0.25, 1.0))
                            }}
                            className="w-24 h-8 rounded-lg text-xs"
                          />
                          <span className="text-xs text-muted-foreground">{(config.budget_alert_threshold * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                      </CollapsibleContent>
                  )}
                </CardContent>
              </Card>
              </Collapsible>

              {/* 状态 */}
              <Card className="hover:shadow-card-hover transition-shadow duration-200">
                <CardContent className="p-4 space-y-3">
                  <p className="text-sm font-medium">状态</p>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">短期记忆</span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{stats.compact_count} 个</span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleMergeNow}
                        disabled={stats.compact_count < 2}
                        className="rounded-xl h-7 text-xs"
                      >
                        <Merge className="h-3 w-3 mr-1" />
                        合并现在
                      </Button>
                    </div>
                  </div>
                  <Separator />
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">短期记忆总量</span>
                    <span className="text-sm font-medium">{formatTokens(stats.compact_total_tokens)}</span>
                  </div>
                  <Separator />
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">长期记忆总量</span>
                    <span className="text-sm font-medium">{formatTokens(stats.long_term_tokens)}</span>
                  </div>
                </CardContent>
              </Card>

              {/* 通知 */}
              {notification && (
                <div className={`text-xs px-3 py-2 rounded-lg flex items-center gap-1.5 ${notification.type === 'success' ? 'bg-success-light text-success' : 'bg-danger-light text-danger'}`}>
                  {notification.type === 'success'
                    ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                    : <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                  }
                  {notification.message}
                </div>
              )}

              {/* 操作按钮 */}
              <div className="flex gap-2">
                <Button variant="outline" onClick={handleResetConfig} className="rounded-xl flex-1">
                  <RotateCcw className="h-4 w-4 mr-1" />
                  恢复默认
                </Button>
                <Button onClick={handleSaveConfig} className="rounded-xl flex-1">
                  保存
                </Button>
              </div>
            </div>
          </ScrollArea>
        </TabsContent>
      </Tabs>

      {/* View Conversation Dialog */}
      <Dialog open={!!viewConv} onOpenChange={() => setViewConv(null)}>
        <DialogContent className="sm:max-w-[680px] max-h-[88vh] flex flex-col overflow-hidden">
          <DialogHeader className="shrink-0" icon={MessageSquare}>
            <DialogTitle>对话记录</DialogTitle>
            <DialogDescription>
              {(viewConv?.id as string)?.slice(0, 8) ?? ''} &middot; {((viewConv?.messages || []) as Array<{ role: string }>).length} 条消息
            </DialogDescription>
          </DialogHeader>
          {/* 对话内容 — 带边框的流式聊天区 */}
          <div className="flex-1 min-h-0 rounded-xl border border-border bg-muted/10 overflow-y-auto">
            <div className="p-4 space-y-2.5">
              {((viewConv?.messages || []) as Array<{ role: string; content: string }>).map((m, i) => (
                m.role === 'user' ? (
                  <div key={i} className="flex justify-end">
                    <div className="max-w-[80%] rounded-2xl rounded-br-md bg-primary text-primary-foreground px-3.5 py-2.5 text-sm leading-relaxed shadow-sm">
                      <p className="whitespace-pre-wrap break-all">{m.content}</p>
                    </div>
                  </div>
                ) : m.role === 'assistant' ? (
                  <div key={i} className="flex justify-start gap-2">
                    <div className="w-7 h-7 rounded-full bg-gradient-to-br from-primary/15 to-primary/5 ring-1 ring-primary/20 flex items-center justify-center shrink-0 mt-0.5">
                      <span className="text-[11px] font-bold text-primary">AI</span>
                    </div>
                    <div className="max-w-[80%] rounded-2xl rounded-bl-md bg-card border border-border/60 px-3.5 py-2.5 text-sm leading-relaxed shadow-sm">
                      <p className="whitespace-pre-wrap break-all">{m.content}</p>
                    </div>
                  </div>
                ) : (
                  <div key={i} className="flex justify-center py-1">
                    <span className="text-[11px] text-text-tertiary">{m.content}</span>
                  </div>
                )
              ))}
            </div>
          </div>
          <DialogFooter className="shrink-0">
            <Button variant="outline" onClick={() => setViewConv(null)} >关闭</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Note Dialog */}
      <Dialog open={!!viewNote} onOpenChange={() => setViewNote(null)}>
        <DialogContent className="sm:max-w-[600px] max-h-[85vh] flex flex-col overflow-hidden">
          <DialogHeader className="shrink-0" icon={FileText}>
            <DialogTitle className="flex items-center gap-2">
              {viewNote?.name}
              <Badge variant={viewNote?.kind === 'long_term' ? 'default' : 'outline'} className="rounded-lg text-[11px]">
                {viewNote?.kind === 'long_term' ? '长期记忆' : '短期记忆'}
              </Badge>
            </DialogTitle>
          </DialogHeader>
          {/* 元信息 */}
          <div className="rounded-lg border border-border/50 bg-muted/20 px-3 py-2 flex items-center gap-4 text-[11px] text-text-tertiary">
            <span>类型：{viewNote?.kind === 'long_term' ? '长期记忆' : '短期记忆'}</span>
            <span className="text-border">|</span>
            <span>字符数：{viewNote?.content?.length ?? 0}</span>
          </div>
          <ScrollArea className="flex-1 min-h-0">
            <div className="rounded-xl border border-border/50 bg-muted/30 p-4">
              <div className="text-sm whitespace-pre-wrap leading-relaxed text-text-secondary">
                {viewNote?.content || '(空)'}
              </div>
            </div>
          </ScrollArea>
          <DialogFooter className="shrink-0">
            <Button variant="outline" onClick={() => setViewNote(null)}>关闭</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── 删除确认 ── */}
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => { if (!open) { setDeleteTarget(null) } }}
        title={deleteTargetType === 'conv' ? '删除对话' : '删除记忆'}
        description={`确定要删除该${deleteTargetType === 'conv' ? '对话记录' : '记忆笔记'}吗？此操作不可撤销。`}
        onConfirm={async () => {
          if (!deleteTarget) return
          if (deleteTargetType === 'conv') {
            await handleDeleteConv(deleteTarget)
          } else {
            await handleDeleteNote(deleteTarget)
          }
          setDeleteTarget(null)
        }}
      />

      {/* ── 恢复默认确认 ── */}
      <ConfirmDialog
        open={resetConfirmOpen}
        onOpenChange={setResetConfirmOpen}
        title="恢复默认设置"
        description="确定要恢复所有记忆设置为默认值吗？当前修改将丢失。"
        onConfirm={confirmReset}
      />
    </div>
  )
}

function formatTokens(n: number): string {
  if (n === 0) return '0 tokens'
  if (n < 1000) return `${n} tokens`
  return `${(n / 1000).toFixed(1)}K tokens`
}
