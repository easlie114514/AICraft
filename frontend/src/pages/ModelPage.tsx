import { useState, useEffect, useCallback } from 'react'
import { Plus, Cpu, Star, Trash2, RefreshCw, Zap, Pencil } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'

function cardGradient(provider: string): React.CSSProperties {
  const tints: Record<string, string> = {
    deepseek: '#4D6BFE',
    openai: '#10A37F',
    anthropic: '#D97757',
  }
  const tint = tints[provider]
  if (tint) {
    // 底板：主题渐变 + 左上自然光（与其他页面统一）
    // 中间~22%：左下→右上厂商纯色带，两侧各~5%过渡区柔和融入主题底
    return {
      background: `
        radial-gradient(ellipse 40% 50% at 18% 18%, rgba(255,255,255,0.10) 0%, transparent 60%),
        linear-gradient(135deg,
          color-mix(in srgb, var(--theme-nav-bg) 68%, var(--theme-primary) 32%) 0%,
          color-mix(in srgb, var(--theme-nav-bg) 50%, ${tint} 50%) 34%,
          ${tint} 39%,
          ${tint} 61%,
          color-mix(in srgb, var(--theme-nav-bg) 50%, ${tint} 50%) 66%,
          color-mix(in srgb, var(--theme-nav-bg) 88%, var(--theme-primary) 12%) 100%
        )
      `,
    }
  }
  return {
    // 其他/中转站：岩灰紫 #8E8EA0 色带
    background: `
      radial-gradient(ellipse 40% 50% at 18% 18%, rgba(255,255,255,0.10) 0%, transparent 60%),
      linear-gradient(135deg,
        color-mix(in srgb, var(--theme-nav-bg) 68%, var(--theme-primary) 32%) 0%,
        color-mix(in srgb, var(--theme-nav-bg) 50%, #8E8EA0 50%) 34%,
        #8E8EA0 39%,
        #8E8EA0 61%,
        color-mix(in srgb, var(--theme-nav-bg) 50%, #8E8EA0 50%) 66%,
        color-mix(in srgb, var(--theme-nav-bg) 88%, var(--theme-primary) 12%) 100%
      )
    `,
  }
}

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

interface ModelFormValue {
  name: string
  provider: string
  model_id: string
  api_key: string
  api_base: string
  protocol: string
  tier: string
  supports_thinking: boolean
  supports_web_search: boolean
}

const DEFAULT_FORM: ModelFormValue = {
  name: '', provider: 'deepseek', model_id: '', api_key: '',
  api_base: '', protocol: '', tier: '',
  supports_thinking: false, supports_web_search: false,
}

function ModelFormFields({
  value,
  onChange,
  nameDisabled = false,
  providerDisabled = false,
}: {
  value: ModelFormValue
  onChange: (next: ModelFormValue) => void
  nameDisabled?: boolean
  providerDisabled?: boolean
}) {
  return (
    <div className="space-y-3 py-2">
      {/* 模型名称 — 独占一行 */}
      <div className="space-y-1.5">
        <Label className="text-xs text-muted-foreground">模型名称</Label>
        <Input
          placeholder="例如: DeepSeek V4、GPT-4o"
          value={value.name}
          onChange={(e) => onChange({ ...value, name: e.target.value })}
          className="h-8 text-sm"
          disabled={nameDisabled}
        />
        {nameDisabled && (
          <p className="text-[11px] text-text-tertiary">模型名称创建后不可修改，如确需改名请删除后重新添加</p>
        )}
      </div>

      {/* Provider + Model ID — 双列 */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Provider</Label>
          <Select
            value={value.provider}
            onValueChange={(v) => onChange({ ...value, provider: v ?? 'deepseek' })}
            disabled={providerDisabled}
          >
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
            value={value.model_id}
            onChange={(e) => onChange({ ...value, model_id: e.target.value })}
            className="h-8 text-sm"
          />
        </div>
      </div>

      {/* API 协议 + 模型层级 — 双列 */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">API 协议</Label>
          <Select value={value.protocol} onValueChange={(v) => onChange({ ...value, protocol: v ?? '' })}>
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
          <Select value={value.tier} onValueChange={(v) => onChange({ ...value, tier: v ?? '' })}>
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
          value={value.api_key}
          onChange={(e) => onChange({ ...value, api_key: e.target.value })}
          className="h-8 text-sm"
        />
      </div>

      {/* API Base — 独占一行 */}
      <div className="space-y-1.5">
        <Label className="text-xs text-muted-foreground">API Base</Label>
        <Input
          placeholder="https://api.openai.com/v1"
          value={value.api_base}
          onChange={(e) => onChange({ ...value, api_base: e.target.value })}
          className="h-8 text-sm font-mono"
        />
      </div>

      {/* 深度思考 + 联网搜索 — 双列开关 */}
      <div className="grid grid-cols-2 gap-3">
        <div className="flex items-center justify-between bg-muted/40 rounded-lg px-3 py-2">
          <Label className="text-xs cursor-pointer" htmlFor="sw-thinking">深度思考</Label>
          <Switch
            id="sw-thinking"
            checked={value.supports_thinking}
            onCheckedChange={(v) => onChange({ ...value, supports_thinking: v })}
          />
        </div>
        <div className="flex items-center justify-between bg-muted/40 rounded-lg px-3 py-2">
          <Label className="text-xs cursor-pointer" htmlFor="sw-search">联网搜索</Label>
          <Switch
            id="sw-search"
            checked={value.supports_web_search}
            onCheckedChange={(v) => onChange({ ...value, supports_web_search: v })}
          />
        </div>
      </div>
    </div>
  )
}

export default function ModelPage() {
  const [models, setModels] = useState<ModelConfig[]>([])
  const [channels, setChannels] = useState<ChannelInfo[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [showChannel, setShowChannel] = useState(false)
  const [testResults, setTestResults] = useState<Record<string, TestStatus>>({})
  const [refreshing, setRefreshing] = useState(false)

  // 手动添加表单
  const [form, setForm] = useState<ModelFormValue>(DEFAULT_FORM)

  // 编辑表单
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [showEdit, setShowEdit] = useState<ModelConfig | null>(null)
  const [editForm, setEditForm] = useState<ModelFormValue>(DEFAULT_FORM)

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
    setForm(DEFAULT_FORM)
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

  const openEdit = (m: ModelConfig) => {
    setShowEdit(m)
    setEditForm({
      name: m.name,
      provider: m.provider,
      model_id: m.model_id,
      api_key: '',
      api_base: m.api_base ?? '',
      protocol: m.protocol ?? '',
      tier: m.tier ?? '',
      supports_thinking: m.supports_thinking ?? false,
      supports_web_search: m.supports_web_search ?? false,
    })
  }

  const handleEditSave = async () => {
    if (!showEdit || !editForm.model_id.trim()) return
    const body: Record<string, unknown> = {
      model_id: editForm.model_id.trim(),
      api_base: editForm.api_base,
      protocol: editForm.protocol,
      tier: editForm.tier,
      supports_thinking: editForm.supports_thinking,
      supports_web_search: editForm.supports_web_search,
    }
    // 仅当用户输入了新 Key 才发送；后端按 key 是否存在判断是否同步
    if (editForm.api_key.trim()) {
      body.api_key = editForm.api_key.trim()
    }
    await api.put(`/models/${encodeURIComponent(showEdit.name)}`, body)
    setShowEdit(null)
    loadModels()
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
          <Button variant="outline" size="icon" disabled={refreshing} onClick={async () => {
            setRefreshing(true)
            await Promise.all([loadModels(), loadChannels()])
            setRefreshing(false)
          }}>
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
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
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pr-1">
            {models.map((m) => {
              const test = testResults[m.name]
              return (
                <Card
                  key={m.name}
                  className="relative overflow-hidden group border-0 text-white" style={cardGradient(m.provider)}
                >
                  {/* 首字母丝印 */}
                  <div className="absolute -bottom-3 -right-4 text-[130px] font-black text-white/[0.05] leading-none select-none pointer-events-none">
                    {(m.provider === 'other' ? 'X' : ((m.provider || '?').trim()[0]?.toUpperCase() || '?'))}
                  </div>

                  <CardContent className="p-5 relative z-10">
                    {/* 主体：图标 + 名称 */}
                    <div className="flex items-center gap-4">
                      <div className="w-14 h-14 rounded-2xl bg-white/10 backdrop-blur-sm flex items-center justify-center shrink-0 ring-1 ring-white/10">
                        <span className="text-2xl font-bold text-white/90">
                          {(m.provider === 'other' ? 'X' : ((m.provider || '?').trim()[0]?.toUpperCase() || '?'))}
                        </span>
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="font-semibold text-lg truncate text-white/95">{m.name}</span>
                          {m.tier && (
                            <span className="text-[10px] bg-white/12 backdrop-blur-sm px-1.5 py-0.5 rounded-md font-medium uppercase tracking-wide text-white/80">
                              {m.tier}
                            </span>
                          )}
                          {m.is_default && (
                            <span className="text-[10px] bg-white/18 backdrop-blur-sm px-1.5 py-0.5 rounded-md text-white/80">
                              首选
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-white/55 font-mono mt-0.5 truncate">{m.model_id}</p>
                      </div>

                      {/* 右上操作图标 */}
                      <div className="flex items-center gap-0.5 shrink-0">
                        <Button
                          variant="ghost" size="icon"
                          onClick={() => handleSetDefault(m.name)}
                          className={cn('text-white/40 hover:text-amber-200 hover:bg-white/8', m.is_default && 'text-amber-200/90')}
                          title="设为首选"
                        >
                          <Star className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost" size="icon"
                          onClick={() => setDeleteTarget(m.name)}
                          className="text-white/25 hover:text-red-200/80 hover:bg-white/8"
                          title="删除"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    {/* 特性标签 */}
                    {(m.protocol || m.supports_thinking || m.supports_web_search || test) && (
                      <div className="flex items-center gap-1.5 mt-3 flex-wrap">
                        {m.protocol && (
                          <span className="text-[10px] text-white/45 bg-white/8 px-1.5 py-0.5 rounded">{m.protocol}</span>
                        )}
                        {m.supports_thinking && (
                          <span className="text-[10px] text-white/45 bg-white/8 px-1.5 py-0.5 rounded">思考</span>
                        )}
                        {m.supports_web_search && (
                          <span className="text-[10px] text-white/45 bg-white/8 px-1.5 py-0.5 rounded">联网搜索</span>
                        )}
                        {test && (
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${test.ok ? 'bg-emerald-400/15 text-emerald-200/90' : 'bg-red-400/15 text-red-200/90'}`}>
                            {test.ok ? '✓ 连接成功' : '✗ 连接失败'}
                          </span>
                        )}
                      </div>
                    )}

                    {test && !test.ok && (
                      <p className="text-xs text-red-200/80 mt-1 line-clamp-2 break-all">{test.message}</p>
                    )}

                    {/* 操作栏 */}
                    <div className="flex items-center gap-1.5 mt-3 pt-3 border-t border-white/8">
                      <Button variant="ghost" size="sm" onClick={() => handleTest(m.name)} className="text-white/60 hover:text-white hover:bg-white/8 text-xs">
                        测试
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => openEdit(m)} className="text-white/60 hover:text-white hover:bg-white/8 text-xs">
                        <Pencil className="h-3.5 w-3.5 mr-1" />
                        编辑
                      </Button>
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
          <ModelFormFields value={form} onChange={setForm} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAdd(false)} >取消</Button>
            <Button onClick={handleAdd} >添加</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── 编辑模型 Dialog ── */}
      <Dialog open={showEdit !== null} onOpenChange={(open) => { if (!open) setShowEdit(null) }}>
        <DialogContent className="sm:max-w-[520px]">
          <DialogHeader icon={Pencil}>
            <DialogTitle>编辑模型</DialogTitle>
            <DialogDescription>修改 {showEdit?.name} 的连接信息（名称与 Provider 不可修改）</DialogDescription>
          </DialogHeader>
          <ModelFormFields
            value={editForm}
            onChange={setEditForm}
            nameDisabled
            providerDisabled
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEdit(null)}>取消</Button>
            <Button onClick={handleEditSave} disabled={!editForm.model_id.trim()}>保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── 删除确认 Dialog ── */}
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}
        title="删除模型"
        description={`确定要删除 ${deleteTarget} 吗？删除后需重新配置才能使用。`}
        onConfirm={async () => {
          if (deleteTarget) await handleDelete(deleteTarget)
          setDeleteTarget(null)
        }}
      />
    </div>
  )
}
