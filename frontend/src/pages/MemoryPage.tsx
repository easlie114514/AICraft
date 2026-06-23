import { useState, useEffect, useCallback } from 'react'
import { Eye, Trash2, Search, RefreshCw, FileText, MessageSquare, Settings2, Merge, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { api } from '@/lib/api'

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
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<string[]>([])
  const [activeTab, setActiveTab] = useState('conversations')

  // ── 记忆设置状态 ──
  const [config, setConfig] = useState<MemoryConfig>(DEFAULT_CONFIG)
  const [stats, setStats] = useState<MemoryStats>({ compact_count: 0, compact_total_chars: 0, compact_total_tokens: 0, long_term_size: 0, long_term_tokens: 0 })
  const [configLoaded, setConfigLoaded] = useState(false)

  const loadConversations = useCallback(async () => {
    try {
      const data = await api.get<Conversation[]>('/memory/conversations')
      setConversations(data)
    } catch { /* ignore */ }
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
    setConfig(DEFAULT_CONFIG)
  }

  const handleMergeNow = async () => {
    try {
      const result = await api.post<{ ok: boolean; message: string }>('/memory/merge', {})
      if (result.ok) {
        loadNotes()
        loadStats()
      }
      alert(result.message || (result.ok ? '合并完成' : '合并失败'))
    } catch { /* ignore */ }
  }

  const updateConfig = <K extends keyof MemoryConfig>(key: K, value: MemoryConfig[K]) => {
    setConfig(prev => ({ ...prev, [key]: value }))
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden p-6">
      <div className="shrink-0 flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-text-primary">记忆</h2>
        <Button variant="outline" size="icon" onClick={() => { loadConversations(); loadNotes(); loadStats() }}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {/* Search */}
      <div className="shrink-0 flex items-center gap-2 mb-4">
        <Input
          placeholder="搜索记忆..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="flex-1 rounded-lg"
        />
        <Button variant="outline" size="icon" onClick={handleSearch} className="shrink-0">
          <Search className="h-4 w-4" />
        </Button>
      </div>

      {searchResults.length > 0 && (
        <div className="shrink-0 mb-4">
          <p className="text-xs font-medium text-muted-foreground mb-2">搜索结果</p>
          <ScrollArea className="max-h-40">
            <div className="space-y-2">
              {searchResults.map((r, i) => (
                <div key={i} className="text-sm bg-muted p-3 rounded-lg whitespace-pre-wrap break-all">{r}</div>
              ))}
            </div>
          </ScrollArea>
        </div>
      )}

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
            {conversations.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
                <MessageSquare className="h-10 w-10 mb-2 text-text-disabled" />
                <p className="text-sm text-text-secondary">暂无对话历史</p>
              </div>
            ) : (
              <div className="grid gap-3 pr-1">
                {conversations.map((c) => (
                  <Card key={c.id} className="hover:shadow-card-hover transition-shadow duration-200">
                    <CardContent className="p-3">
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium font-mono">{c.id}</span>
                            <Badge variant="secondary" className="rounded-lg text-xs">{c.message_count} 条消息</Badge>
                          </div>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {c.created} &middot; {c.model} &middot; {c.role}
                          </p>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          <Button variant="ghost" size="sm" onClick={() => handleView(c.id)} >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDeleteConv(c.id)} className="text-muted-foreground hover:text-destructive">
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
                  <Card key={n.name} className="hover:shadow-card-hover transition-shadow duration-200">
                    <CardContent className="p-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 min-w-0">
                          <Badge
                            variant={n.kind === 'long_term' ? 'default' : 'outline'}
                            className="rounded-lg text-xs shrink-0"
                          >
                            {n.kind === 'long_term' ? '长期记忆' : '短期'}
                          </Badge>
                          <span className="text-sm font-medium truncate">{n.name}</span>
                          <span className="text-[10px] text-muted-foreground shrink-0">{formatTokens(n.tokens)}</span>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteNote(n.filename)}
                          className="text-muted-foreground hover:text-destructive shrink-0 ml-2"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1 truncate">{n.preview}</p>
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
              <Card className="hover:shadow-card-hover transition-shadow duration-200">
                <CardContent className="p-4 space-y-3">
                  <p className="text-sm font-medium">触发条件</p>
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
                        onChange={(e) => updateConfig('memory_compact_interval_chars', Number(e.target.value))}
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
                        onChange={(e) => updateConfig('memory_compact_interval_msgs', Number(e.target.value))}
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
                        onChange={(e) => updateConfig('memory_compact_window', Number(e.target.value))}
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
                        onChange={(e) => updateConfig('memory_compact_max_tokens', Number(e.target.value))}
                        className="w-24 h-8 rounded-lg text-xs"
                      />
                      <span className="text-xs text-muted-foreground">tokens</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

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
                        onChange={(e) => updateConfig('memory_merge_threshold', Number(e.target.value))}
                        className="w-24 h-8 rounded-lg text-xs"
                      />
                      <span className="text-xs text-muted-foreground">个片段</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* 注入控制 */}
              <Card className="hover:shadow-card-hover transition-shadow duration-200">
                <CardContent className="p-4 space-y-3">
                  <p className="text-sm font-medium">注入控制</p>
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-muted-foreground">注入上限</Label>
                    <div className="flex items-center gap-1">
                      <Input
                        type="number"
                        min={500}
                        max={50000}
                        value={config.memory_inject_max_chars}
                        onChange={(e) => updateConfig('memory_inject_max_chars', Number(e.target.value))}
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
                        onChange={(e) => updateConfig('cross_session_inject_count', Number(e.target.value))}
                        className="w-24 h-8 rounded-lg text-xs"
                      />
                      <span className="text-xs text-muted-foreground">条</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* 上下文预算 */}
              <Card className="hover:shadow-card-hover transition-shadow duration-200">
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">上下文预算</p>
                      <p className="text-xs text-muted-foreground">统筹所有注入内容，防止超出模型窗口</p>
                    </div>
                    <Switch
                      id="budget-enabled"
                      checked={config.context_budget_enabled}
                      onCheckedChange={(v) => updateConfig('context_budget_enabled', v)}
                    />
                  </div>
                  {config.context_budget_enabled && (
                    <>
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
                            onChange={(e) => updateConfig('context_window_override', Number(e.target.value))}
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
                            onChange={(e) => updateConfig('output_reserve_ratio', Number(e.target.value))}
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
                            onChange={(e) => updateConfig('budget_alert_threshold', Number(e.target.value))}
                            className="w-24 h-8 rounded-lg text-xs"
                          />
                          <span className="text-xs text-muted-foreground">{(config.budget_alert_threshold * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>

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
        <DialogContent className="sm:max-w-[600px] max-h-[80vh]">
          <DialogHeader>
            <DialogTitle className="text-sm font-mono">对话 {viewConv?.id as string || ''}</DialogTitle>
          </DialogHeader>
          <ScrollArea className="max-h-[50vh]">
            <div className="space-y-3">
              {((viewConv?.messages || []) as Array<{ role: string; content: string }>).map((m, i) => (
                <div key={i} className={`text-sm ${m.role === 'user' ? 'text-primary' : m.role === 'assistant' ? '' : 'text-muted-foreground'}`}>
                  <span className="font-medium text-xs text-muted-foreground">{m.role}</span>
                  <p className="whitespace-pre-wrap mt-0.5">{m.content?.slice(0, 500)}{m.content?.length > 500 ? '...' : ''}</p>
                </div>
              ))}
            </div>
          </ScrollArea>
          <DialogFooter>
            <Button variant="outline" onClick={() => setViewConv(null)} >关闭</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function formatTokens(n: number): string {
  if (n === 0) return '0 tokens'
  if (n < 1000) return `${n} tokens`
  return `${(n / 1000).toFixed(1)}K tokens`
}
