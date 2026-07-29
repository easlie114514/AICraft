import { useState, useEffect, useCallback } from 'react'
import { Plus, Cpu, Star, Trash2, RefreshCw, Zap, Eye, EyeOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

interface ModelConfig {
  name: string
  provider: string
  model_id: string
  api_key?: string
  api_base?: string
  protocol?: string
  tier?: string
  supports_thinking?: boolean
  supports_web_search?: boolean
  is_default?: boolean
  is_current?: boolean
}

interface ChannelInfo {
  type: string
  name: string
  base_url: string
  protocol: string
  models: { name: string; model_id: string; tier: string }[]
}

type TestStatus = { model: string; ok: boolean; message: string } | null

export default function ModelPage() {
  const [models, setModels] = useState<ModelConfig[]>([])
  const [channels, setChannels] = useState<ChannelInfo[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [showChannel, setShowChannel] = useState(false)
  const [testResults, setTestResults] = useState<Record<string, TestStatus>>({})
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({})

  // 手动添加表单
  const [form, setForm] = useState({
    name: '',
    provider: 'deepseek',
    model_id: '',
    api_key: '',
    api_base: '',
    protocol: '',
    tier: '',
    supports_thinking: false,
    supports_web_search: false,
  })

  // 通道表单（仅 DeepSeek）
  const [channelApiKey, setChannelApiKey] = useState('')

  const loadModels = useCallback(async () => {
    try {
      const data = await api.get<ModelConfig[]>('/models')
      setModels(data)
    } catch { /* ignore */ }
  }, [])

  const loadChannels = useCallback(async () => {
    try {
      const data = await api.get<ChannelInfo[]>('/models/channels')
      setChannels(data)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadModels(); loadChannels() }, [loadModels, loadChannels])

  const handleAdd = async () => {
    if (!form.name || !form.model_id) return
    await api.post('/models', form)
    setShowAdd(false)
    setForm({ name: '', provider: 'deepseek', model_id: '', api_key: '', api_base: '', protocol: '', tier: '', supports_thinking: false, supports_web_search: false })
    loadModels()
  }

  const handleAddChannel = async () => {
    if (!channelApiKey.trim()) return
    await api.post('/models/channel', { channel_type: 'deepseek', api_key: channelApiKey.trim() })
    setShowChannel(false)
    setChannelApiKey('')
    loadModels()
  }

  const handleDelete = async (name: string) => {
    await api.delete(`/models/${encodeURIComponent(name)}`)
    loadModels()
  }

  const handleSetDefault = async (name: string) => {
    await api.put(`/models/${encodeURIComponent(name)}/default`)
    loadModels()
  }

  const handleSetCurrent = async (modelId: string) => {
    await api.put('/models/current', { model_id: modelId })
    loadModels()
  }

  const handleTest = async (name: string) => {
    setTestResults((prev) => ({ ...prev, [name]: null }))
    try {
      const data = await api.post<{ ok: boolean; message: string }>(`/models/${encodeURIComponent(name)}/test`)
      setTestResults((prev) => ({ ...prev, [name]: { model: name, ok: data.ok, message: data.message } }))
    } catch (e: any) {
      setTestResults((prev) => ({ ...prev, [name]: { model: name, ok: false, message: e?.message || String(e) } }))
    }
  }

  const toggleKey = (name: string) => {
    setShowKeys((prev) => ({ ...prev, [name]: !prev[name] }))
  }

  // 获取 DeepSeek 通道预设详情用于展示
  const deepseekChannel = channels.find((c) => c.type === 'deepseek')

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden p-6 animate-in fade-in duration-200">
      <div className="shrink-0 flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/15 to-primary/5 ring-1 ring-primary/10 flex items-center justify-center shrink-0">
            <Cpu className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-text-primary">模型配置</h2>
            <p className="text-xs text-text-tertiary">管理 AI 模型与 API 通道连接</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => { loadModels(); loadChannels() }}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button onClick={() => setShowChannel(true)} className="bg-primary text-white">
            <Zap className="h-4 w-4 mr-1" />
            DeepSeek一键接入
          </Button>
          <Button onClick={() => setShowAdd(true)} variant="outline">
            <Plus className="h-4 w-4 mr-1" />
            自定义模型
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        {models.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
            <Cpu className="w-16 h-16 text-text-disabled mb-4" />
            <p className="text-sm text-text-secondary">暂无模型配置</p>
            <p className="text-xs text-text-tertiary mt-1">点击"DeepSeek一键接入"快速配置，或"自定义模型"手动填写</p>
          </div>
        ) : (
          <div className="grid gap-4 pr-1">
            {models.map((m) => {
              const test = testResults[m.name]
              return (
                <Card key={m.name} className="hover:shadow-card-hover transition-shadow duration-200">
                  <CardContent className="p-4">
                    <div className="flex items-start gap-4">
                      <Avatar className={`h-10 w-10 shrink-0 rounded-full ${m.tier === 'flash' ? 'bg-warning/15' : 'bg-primary/15'}`}>
                        <AvatarFallback className={`bg-transparent ${m.tier === 'flash' ? 'text-warning' : 'text-primary'}`}>
                          <Cpu className="h-5 w-5" />
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-medium text-foreground">{m.name}</span>
                          {m.tier && (
                            <Badge variant={m.tier === 'pro' ? 'default' : 'secondary'} className="rounded-lg text-[10px]">
                              {m.tier === 'pro' ? 'Pro' : m.tier === 'flash' ? 'Flash' : m.tier}
                            </Badge>
                          )}
                          {m.is_default && <Badge className="rounded-lg">默认</Badge>}
                          {m.is_current && <Badge variant="secondary" className="rounded-lg">当前</Badge>}
                        </div>
                        <p className="text-sm text-muted-foreground font-mono mt-0.5 truncate">{m.model_id}</p>
                        <div className="flex items-center gap-2 mt-1 flex-wrap">
                          {m.protocol && (
                            <span className="text-[10px] text-text-tertiary bg-muted px-1.5 py-0.5 rounded">
                              {m.protocol}
                            </span>
                          )}
                          {m.supports_thinking && (
                            <span className="text-[10px] text-text-tertiary bg-muted px-1.5 py-0.5 rounded">
                              思考
                            </span>
                          )}
                          {m.supports_web_search && (
                            <span className="text-[10px] text-text-tertiary bg-muted px-1.5 py-0.5 rounded">
                              联网搜索
                            </span>
                          )}
                          {test && (
                            <Badge variant={test.ok ? 'default' : 'destructive'} className="rounded-lg text-[10px]">
                              {test.ok ? '✓ 连接成功' : '✗ 连接失败'}
                            </Badge>
                          )}
                        </div>
                        {test && !test.ok && (
                          <p className="text-xs text-destructive mt-1 truncate max-w-md">{test.message}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <Button variant="outline" size="sm" onClick={() => handleTest(m.name)} className="text-xs">
                          测试
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleSetDefault(m.name)}
                          className={cn(m.is_default && 'text-yellow-500')}
                          title="设为默认"
                        >
                          <Star className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(m.name)}
                          className="text-muted-foreground hover:text-destructive"
                          title="删除"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        )}
      </ScrollArea>

      {/* ── DeepSeek一键接入 Dialog ── */}
      <Dialog open={showChannel} onOpenChange={setShowChannel}>
        <DialogContent className="sm:max-w-[520px]">
          <DialogHeader icon={Zap}>
            <DialogTitle>DeepSeek 一键接入</DialogTitle>
            <DialogDescription>填入 API Key 即可自动创建 DeepSeek V4 Pro + Flash 模型配置</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-4">
            {/* API Key */}
            <div className="rounded-xl border border-border/50 bg-muted/20 p-4 space-y-2">
              <Label className="text-xs text-text-secondary">API Key</Label>
              <Input
                type="password"
                placeholder="sk-..."
                value={channelApiKey}
                onChange={(e) => setChannelApiKey(e.target.value)}
              />
            </div>

            {/* 只读：端点 & 将自动创建的模型 */}
            {deepseekChannel && (
              <div className="rounded-xl border border-border/50 bg-muted/20 p-4 relative overflow-hidden">
                <div className="absolute top-0 left-4 right-4 h-[2px] bg-gradient-to-r from-transparent via-primary/30 to-transparent" />
                <div className="space-y-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-text-tertiary">端点</span>
                    <span className="font-mono text-text-primary">{deepseekChannel.base_url}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-text-tertiary">协议</span>
                    <span className="font-mono text-text-primary">{deepseekChannel.protocol}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-text-tertiary">将自动创建</span>
                    <span>
                      {deepseekChannel.models.map((m) => (
                        <Badge key={m.model_id} variant="secondary" className="rounded-lg ml-1 text-[10px]">
                          {m.name}
                        </Badge>
                      ))}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowChannel(false)} >取消</Button>
            <Button
              onClick={handleAddChannel}
              disabled={!channelApiKey.trim()}
            >
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── 自定义模型 Dialog ── */}
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent className="sm:max-w-[520px]">
          <DialogHeader icon={Plus}>
            <DialogTitle>自定义模型</DialogTitle>
            <DialogDescription>手动配置 LLM API 连接信息</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            {/* 模型名称 — 独占一行 */}
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">模型名称</Label>
              <Input
                placeholder="例如: DeepSeek V4、GPT-4o"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="h-8 text-sm"
              />
            </div>

            {/* Provider + Model ID — 双列 */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Provider</Label>
                <Select value={form.provider} onValueChange={(v) => setForm({ ...form, provider: v ?? 'deepseek' })}>
                  <SelectTrigger className="w-full h-8 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent sideOffset={6} alignItemWithTrigger={false}>
                    <SelectItem value="openai">OpenAI</SelectItem>
                    <SelectItem value="deepseek">DeepSeek</SelectItem>
                    <SelectItem value="anthropic">Anthropic</SelectItem>
                    <SelectItem value="other">其他 / 中转站</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Model ID</Label>
                <Input
                  placeholder="deepseek-chat"
                  value={form.model_id}
                  onChange={(e) => setForm({ ...form, model_id: e.target.value })}
                  className="h-8 text-sm"
                />
              </div>
            </div>

            {/* API 协议 + 模型层级 — 双列 */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">API 协议</Label>
                <Select value={form.protocol} onValueChange={(v) => setForm({ ...form, protocol: v ?? '' })}>
                  <SelectTrigger className="w-full h-8 text-sm">
                    <SelectValue placeholder="自动推断" />
                  </SelectTrigger>
                  <SelectContent sideOffset={6} alignItemWithTrigger={false}>
                    <SelectItem value="">自动推断</SelectItem>
                    <SelectItem value="anthropic">Anthropic Messages</SelectItem>
                    <SelectItem value="openai">OpenAI Completions</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">模型层级</Label>
                <Select value={form.tier} onValueChange={(v) => setForm({ ...form, tier: v ?? '' })}>
                  <SelectTrigger className="w-full h-8 text-sm">
                    <SelectValue placeholder="不参与 Auto 路由" />
                  </SelectTrigger>
                  <SelectContent sideOffset={6} alignItemWithTrigger={false}>
                    <SelectItem value="">无</SelectItem>
                    <SelectItem value="pro">Pro（主力推理）</SelectItem>
                    <SelectItem value="flash">Flash（快速轻量）</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* API Key — 独占一行 */}
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">API Key</Label>
              <Input
                type="password"
                placeholder="sk-..."
                value={form.api_key}
                onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                className="h-8 text-sm"
              />
            </div>

            {/* API Base — 独占一行 */}
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">API Base</Label>
              <Input
                placeholder="https://api.openai.com/v1"
                value={form.api_base}
                onChange={(e) => setForm({ ...form, api_base: e.target.value })}
                className="h-8 text-sm font-mono"
              />
            </div>

            {/* 深度思考 + 联网搜索 — 双列开关 */}
            <div className="grid grid-cols-2 gap-3">
              <div className="flex items-center justify-between bg-muted/40 rounded-lg px-3 py-2">
                <Label className="text-xs cursor-pointer" htmlFor="sw-thinking">深度思考</Label>
                <Switch
                  id="sw-thinking"
                  checked={form.supports_thinking}
                  onCheckedChange={(v) => setForm({ ...form, supports_thinking: v })}
                />
              </div>
              <div className="flex items-center justify-between bg-muted/40 rounded-lg px-3 py-2">
                <Label className="text-xs cursor-pointer" htmlFor="sw-search">联网搜索</Label>
                <Switch
                  id="sw-search"
                  checked={form.supports_web_search}
                  onCheckedChange={(v) => setForm({ ...form, supports_web_search: v })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAdd(false)} >取消</Button>
            <Button onClick={handleAdd} >添加</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
