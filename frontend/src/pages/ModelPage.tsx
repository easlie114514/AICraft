import { useState, useEffect, useCallback } from 'react'
import { Plus, Cpu, Star, Trash2, RefreshCw, Zap, Eye, EyeOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
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
  const [form, setForm] = useState({ name: '', provider: 'deepseek', model_id: '', api_key: '', api_base: '' })

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
    setForm({ name: '', provider: 'deepseek', model_id: '', api_key: '', api_base: '' })
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
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden p-6">
      <div className="shrink-0 flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-text-primary">模型配置</h2>
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
          <DialogHeader>
            <DialogTitle>DeepSeek一键接入</DialogTitle>
            <DialogDescription>填入 API Key 即可自动创建 DeepSeek V4 Pro + Flash 模型配置</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {/* API Key */}
            <div className="space-y-2">
              <Label>API Key</Label>
              <Input
                type="password"
                placeholder="sk-..."
                value={channelApiKey}
                onChange={(e) => setChannelApiKey(e.target.value)}
                
              />
            </div>

            {/* 只读：端点 & 将自动创建的模型 */}
            {deepseekChannel && (
              <div className="space-y-2 rounded-xl bg-muted/50 p-3 border border-border/50">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">端点</span>
                  <span className="font-mono text-foreground">{deepseekChannel.base_url}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">协议</span>
                  <span className="font-mono text-foreground">{deepseekChannel.protocol}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">将自动创建</span>
                  <span className="text-foreground">
                    {deepseekChannel.models.map((m) => (
                      <Badge key={m.model_id} variant="secondary" className="rounded-lg ml-1 text-[10px]">
                        {m.name}
                      </Badge>
                    ))}
                  </span>
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowChannel(false)} >取消</Button>
            <Button
              onClick={handleAddChannel}
              className="bg-primary text-white"
              disabled={!channelApiKey.trim()}
            >
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── 自定义模型 Dialog（保留原有手动添加功能）── */}
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent className="sm:max-w-[520px]">
          <DialogHeader>
            <DialogTitle>自定义模型</DialogTitle>
            <DialogDescription>手动配置 LLM API 连接信息</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>模型名称</Label>
              <Input
                placeholder="例如: DeepSeek-V4"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                
              />
            </div>
            <div className="space-y-2">
              <Label>Provider</Label>
              <Select value={form.provider} onValueChange={(v) => setForm({ ...form, provider: v ?? 'deepseek' })}>
                <SelectTrigger >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="openai">OpenAI</SelectItem>
                  <SelectItem value="deepseek">DeepSeek</SelectItem>
                  <SelectItem value="anthropic">Anthropic</SelectItem>
                  <SelectItem value="other">其他</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Model ID</Label>
              <Input
                placeholder="例如: deepseek/deepseek-chat"
                value={form.model_id}
                onChange={(e) => setForm({ ...form, model_id: e.target.value })}
                
              />
            </div>
            <div className="space-y-2">
              <Label>API Key</Label>
              <Input
                type="password"
                placeholder="sk-..."
                value={form.api_key}
                onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                
              />
            </div>
            <div className="space-y-2">
              <Label>API Base (可选)</Label>
              <Input
                placeholder="https://api.example.com/v1"
                value={form.api_base}
                onChange={(e) => setForm({ ...form, api_base: e.target.value })}
                
              />
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
