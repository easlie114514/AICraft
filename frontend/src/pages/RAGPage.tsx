import { useState, useEffect, useCallback } from 'react'
import { Plus, Trash2, Folder, RefreshCw, Database, Settings2, Eye, EyeOff, FlaskConical, Info, Cloud, Link, Monitor } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '@/components/ui/tooltip'
import { SettingRow, SectionLabel, NumberStepper } from '@/components/settings-ui'
import { api } from '@/lib/api'
import { themeCardGradient } from '@/lib/utils'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'

interface RAGSource {
  name: string
  path: string
  source_type: string
  enabled: boolean
  file_count: number
  indexed: boolean
  chroma_docs: number
}

interface RAGConfig {
  embedding_mode: string
  embedding_api_key_masked: string
  has_api_key: boolean
  embedding_model: string
  embedding_api_base: string
  chunk_max_tokens: number
  top_k: number
}

const EMBEDDING_MODELS = [
  { value: 'BAAI/bge-large-zh-v1.5', label: 'BAAI/bge-large-zh-v1.5 (中文, 1024维)' },
  { value: 'BAAI/bge-large-en-v1.5', label: 'BAAI/bge-large-en-v1.5 (英文, 1024维)' },
  { value: 'BAAI/bge-m3', label: 'BAAI/bge-m3 (多语言, 1024维)' },
]

const EMBEDDING_MODE_OPTIONS = [
  {
    value: 'auto',
    icon: Cloud,
    title: 'auto — 智能切换',
    desc: '有 API Key 使用硅基流动，否则自动使用本地 ONNX',
  },
  {
    value: 'api',
    icon: Link,
    title: 'api — 强制 API',
    desc: '始终使用硅基流动 API（需配置 API Key）',
  },
  {
    value: 'local',
    icon: Monitor,
    title: 'local — 本地 ONNX',
    desc: '使用内置 all-MiniLM-L6-v2 模型，无需联网',
  },
]

/** Small info icon that shows a tooltip on hover */
function InfoTip({ text }: { text: string }) {
  return (
    <TooltipProvider delay={300}>
      <Tooltip>
        <TooltipTrigger>
          <span className="inline-flex cursor-help text-muted-foreground/50 hover:text-muted-foreground transition-colors">
            <Info className="h-3.5 w-3.5" />
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-64 text-xs leading-relaxed">
          {text}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

export default function RAGPage() {
  const [sources, setSources] = useState<RAGSource[]>([])
  const [sourcesLoading, setSourcesLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [indexing, setIndexing] = useState<Record<string, boolean>>({})
  const [form, setForm] = useState({ name: '', path: '' })

  // RAG Embedding config state
  const [ragConfig, setRagConfig] = useState<RAGConfig | null>(null)
  const [configLoading, setConfigLoading] = useState(false)
  const [embedMode, setEmbedMode] = useState('auto')
  const [apiKey, setApiKey] = useState(() => sessionStorage.getItem('aicraft_rag_apikey') || '')
  const [showKey, setShowKey] = useState(false)
  const [embedModel, setEmbedModel] = useState('BAAI/bge-large-zh-v1.5')
  const [apiBase, setApiBase] = useState('https://api.siliconflow.cn/v1')
  const [chunkMaxTokens, setChunkMaxTokens] = useState(800)
  const [topK, setTopK] = useState(20)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; dimension?: number; error?: string } | null>(null)
  const [configSaving, setConfigSaving] = useState(false)

  // 持久化 API Key 输入到 sessionStorage（页面切换不丢失）
  useEffect(() => {
    if (apiKey) {
      sessionStorage.setItem('aicraft_rag_apikey', apiKey)
    } else {
      sessionStorage.removeItem('aicraft_rag_apikey')
    }
  }, [apiKey])

  const loadSources = useCallback(async () => {
    setSourcesLoading(true)
    try {
      const data = await api.get<RAGSource[]>('/rag')
      setSources(data)
    } catch { /* ignore */ }
    finally { setSourcesLoading(false) }
  }, [])

  const loadRagConfig = useCallback(async () => {
    setConfigLoading(true)
    try {
      const data = await api.get<RAGConfig>('/rag/config')
      setRagConfig(data)
      setEmbedMode(data.embedding_mode)
      setEmbedModel(data.embedding_model)
      setApiBase(data.embedding_api_base)
      setChunkMaxTokens(data.chunk_max_tokens || 800)
      setTopK(data.top_k ?? 20)
    } catch { /* ignore */ }
    setConfigLoading(false)
  }, [])

  useEffect(() => { loadSources(); loadRagConfig() }, [loadSources, loadRagConfig])

  const saveRagConfig = async (updates: Record<string, string>) => {
    setConfigSaving(true)
    try {
      const res = await api.post<{ success: boolean; error?: string }>('/rag/config', updates)
      if (res.success) {
        loadRagConfig()
        setTestResult(null)
      }
    } catch { /* ignore */ }
    setConfigSaving(false)
  }

  const handleModeChange = async (mode: string) => {
    setEmbedMode(mode)
    await saveRagConfig({ embedding_mode: mode })
  }

  const handleModelChange = async (model: string | null) => {
    if (!model) return
    setEmbedModel(model)
    await saveRagConfig({ embedding_model: model })
  }

  const handleApiBaseChange = async (base: string) => {
    setApiBase(base)
  }

  const handleApiBaseBlur = () => {
    if (apiBase.trim() && apiBase !== ragConfig?.embedding_api_base) {
      saveRagConfig({ embedding_api_base: apiBase.trim() })
    }
  }

  const handleChunkTokensBlur = () => {
    if (chunkMaxTokens > 0 && chunkMaxTokens !== ragConfig?.chunk_max_tokens) {
      saveRagConfig({ chunk_max_tokens: String(chunkMaxTokens) })
    }
  }

  const handleTopKChange = (v: number) => {
    const clamped = Math.max(10, Math.min(30, v))
    setTopK(clamped)
    if (clamped !== (ragConfig?.top_k ?? 20)) {
      saveRagConfig({ top_k: String(clamped) })
    }
  }

  const handleSaveKey = async () => {
    if (!apiKey.trim()) return
    await saveRagConfig({ embedding_api_key: apiKey.trim() })
  }

  const handleTestConnection = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const key = apiKey.trim() || ''
      const res = await api.post<{ success: boolean; dimension?: number; error?: string }>('/rag/test-embedding', {
        api_key: key || '',
        model: embedModel,
        api_base: apiBase,
      })
      setTestResult(res)
    } catch {
      setTestResult({ success: false, error: '请求失败' })
    }
    setTesting(false)
  }

  const handleAdd = async () => {
    if (!form.name.trim() || !form.path.trim()) return
    await api.post('/rag', { ...form, source_type: 'local' })
    setShowAdd(false)
    setForm({ name: '', path: '' })
    loadSources()
  }

  const handleToggle = async (name: string, enabled: boolean) => {
    await api.put(`/rag/${encodeURIComponent(name)}/toggle`, { enabled })
    loadSources()
  }

  const handleIndex = async (name: string) => {
    setIndexing((prev) => ({ ...prev, [name]: true }))
    try {
      await api.post(`/rag/${encodeURIComponent(name)}/index`)
      loadSources()
    } finally {
      setIndexing((prev) => ({ ...prev, [name]: false }))
    }
  }

  const handleDelete = async (name: string) => {
    await api.delete(`/rag/${encodeURIComponent(name)}`)
    loadSources()
  }

  const isLocalMode = embedMode === 'local'

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden p-6 animate-in fade-in duration-200">
      {/* ── Page Header ── */}
      <div className="shrink-0 flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/15 to-primary/5 ring-1 ring-primary/10 flex items-center justify-center shrink-0">
            <Database className="w-5 h-5 text-primary" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-text-primary">RAG 知识库</h2>
              {ragConfig?.has_api_key && (
                <Badge className="rounded-lg text-xs" variant="secondary">API 已配置</Badge>
              )}
            </div>
            <p className="text-xs text-text-tertiary">配置 Embedding 参数并管理文档数据源</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => { loadSources(); loadRagConfig() }}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button onClick={() => setShowAdd(true)}>
            <Plus className="h-4 w-4 mr-1" />
            添加数据源
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        <div className="pr-1 pb-4">
          {/* ── Embedding 配置 ── */}
          <SectionLabel icon={Settings2} title="Embedding 配置" description="向量化模型、API 连接与检索参数" />

          <div className="rounded-xl border border-border bg-card overflow-hidden mb-4">
            <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr]">
              {/* ── 左栏：Embedding 模式 ── */}
              <div className="flex flex-col justify-center gap-2 p-5 lg:border-r border-border">
                <span className="text-sm font-medium text-text-primary inline-flex items-center gap-1 mb-0.5">
                  Embedding 模式
                  <InfoTip text="auto：有 API Key 时使用硅基流动 API（1024维），否则使用本地 ONNX 模型（384维）。api：强制使用硅基流动 API。local：强制使用本地 ONNX 模型。注意：API 和本地向量维度不同，切换后需重新索引全部数据源。" />
                </span>
                <p className="text-xs text-text-tertiary -mt-0.5 mb-1">选择文本向量化的运行方式</p>
                {EMBEDDING_MODE_OPTIONS.map((opt) => {
                  const isSelected = embedMode === opt.value
                  const OptIcon = opt.icon
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => handleModeChange(opt.value)}
                      className={`flex items-center gap-2.5 px-3 py-2 rounded-lg border text-left transition-colors cursor-pointer ${
                        isSelected
                          ? 'border-primary bg-primary/5 ring-1 ring-primary/20'
                          : 'border-border hover:border-muted-foreground/30 hover:bg-muted/30'
                      }`}
                    >
                      <span className={`shrink-0 w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center transition-colors ${
                        isSelected ? 'border-primary' : 'border-muted-foreground/40'
                      }`}>
                        {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-primary" />}
                      </span>
                      <OptIcon className={`shrink-0 h-3.5 w-3.5 ${isSelected ? 'text-primary' : 'text-muted-foreground'}`} />
                      <div className="min-w-0">
                        <div className={`text-xs font-medium truncate ${isSelected ? 'text-text-primary' : 'text-text-secondary'}`}>
                          {opt.title}
                        </div>
                        <div className="text-[11px] text-text-tertiary leading-tight">{opt.desc}</div>
                      </div>
                    </button>
                  )
                })}
              </div>

              {/* ── 右栏：参数配置 ── */}
              <div className="h-fit">
                {/* 仅在非 local 模式下显示 */}
                {!isLocalMode && (
                  <>
                    <SettingRow
                      title="Embedding 模型"
                      description="选择文本向量化模型，多语言场景推荐 BGE-M3"
                    >
                      <div className="flex items-center gap-1.5">
                        <Select value={embedModel} onValueChange={handleModelChange}>
                          <SelectTrigger className="w-56 h-8 text-sm">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent sideOffset={6}>
                            {EMBEDDING_MODELS.map((m) => (
                              <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <InfoTip text="选择 Embedding 模型。BGE-M3 支持中英多语言，效果最好且免费。BGE-large-zh-v1.5 专为中文优化。切换模型后需重新索引全部数据源。" />
                      </div>
                    </SettingRow>
                    <Separator />

                    <SettingRow
                      title="API 地址"
                      description="硅基流动 API 端点地址，通常无需修改"
                    >
                      <div className="flex items-center gap-1.5">
                        <Input
                          value={apiBase}
                          onChange={(e) => handleApiBaseChange(e.target.value)}
                          onBlur={handleApiBaseBlur}
                          className="w-[400px] h-8 text-sm font-mono"
                          placeholder="https://api.siliconflow.cn/v1"
                          maxLength={500}
                        />
                        <InfoTip text="硅基流动 API 的基础地址。默认使用官方服务，如使用兼容 OpenAI 格式的代理服务可在此更改地址。" />
                      </div>
                    </SettingRow>
                    <Separator />

                    {/* API Key */}
                    <div className="px-4 py-3.5">
                      <div className="flex items-start justify-between gap-6">
                        <div className="space-y-0.5 min-w-0 pt-0.5">
                          <span className="text-sm text-text-primary inline-flex items-center gap-1">
                            API Key
                            <InfoTip text="在 cloud.siliconflow.cn 免费注册获取。硅基流动提供免费 Embedding 额度，日常使用基本够用。" />
                          </span>
                          <p className="text-xs text-text-tertiary leading-relaxed">
                            {ragConfig?.has_api_key && !apiKey
                              ? `已保存: ${ragConfig.embedding_api_key_masked}`
                              : '输入硅基流动 API Key'}
                          </p>
                        </div>
                        <div className="shrink-0 space-y-1.5">
                          <div className="flex gap-1.5">
                            <div className="relative">
                              <Input
                                type={showKey ? 'text' : 'password'}
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                className="w-80 h-8 text-sm pr-8"
                                placeholder={ragConfig?.has_api_key ? '输入新 Key 覆盖旧值' : 'sk-...'}
                                maxLength={500}
                              />
                              <button
                                type="button"
                                onClick={() => setShowKey(!showKey)}
                                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                              >
                                {showKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                              </button>
                            </div>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={handleSaveKey}
                              disabled={!apiKey.trim() || configSaving}
                              className="h-8 text-xs shrink-0"
                            >
                              {configSaving ? '保存中...' : '保存'}
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={handleTestConnection}
                              disabled={testing}
                              className="h-8 text-xs shrink-0"
                            >
                              <FlaskConical className={`h-3.5 w-3.5 mr-1 ${testing ? 'animate-spin' : ''}`} />
                              测试
                            </Button>
                          </div>
                          {testResult && (
                            <p className={`text-xs ${testResult.success ? 'text-green-600' : 'text-red-500'}`}>
                              {testResult.success
                                ? `✅ 连接成功，维度: ${testResult.dimension}`
                                : `❌ ${testResult.error}`}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                    <Separator />
                  </>
                )}

                {/* 分片 Token 上限 — 始终显示 */}
                <SettingRow
                  title="分片 Token 上限"
                  description={isLocalMode ? '本地模式固定为 200 token' : '每个文本片段的最大 Token 数'}
                >
                  <div className="flex items-center gap-1.5">
                    <Input
                      type="number"
                      min={100}
                      max={8192}
                      value={isLocalMode ? 200 : chunkMaxTokens}
                      onChange={(e) => {
                        const v = Number(e.target.value)
                        if (e.target.value === '' || isNaN(v)) return
                        setChunkMaxTokens(Math.max(100, Math.min(8192, v)))
                      }}
                      onBlur={handleChunkTokensBlur}
                      disabled={isLocalMode}
                      className="w-24 h-8 text-sm text-center"
                    />
                    <InfoTip text="每个文本片段的最大 Token 数。值越大单个片段包含越多上下文，但可能超出 Embedding 模型的输入限制（BGE-M3 支持 8192 token）。本地 ONNX 模型固定限制为 200 token。推荐 800-1500。" />
                  </div>
                </SettingRow>

                <Separator />

                {/* Top-K 召回数 — 始终显示 */}
                <SettingRow
                  title="检索数量 (Top-K)"
                  description="每次查询返回的最相关片段数，推荐 15-25"
                >
                  <div className="flex items-center gap-1.5">
                    <NumberStepper value={topK} min={10} max={30} onChange={handleTopKChange} />
                    <InfoTip text="每次查询从知识库中召回的最相关文本片段数量。值越大覆盖范围越广，但可能引入噪音。配合精排（API 模式）或 MMR 去重（本地模式）过滤低质量结果。范围 10-30，推荐 20。" />
                  </div>
                </SettingRow>
              </div>
            </div>
          </div>

          {/* 提示 */}
          <p className="text-xs text-muted-foreground mb-6">
            推荐非内网情况下首选硅基流动，比软件自带的 onnx 模型更快，免费额度基本够用(∩_∩)。免费注册硅基流动 API Key: <a href="https://cloud.siliconflow.cn" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">cloud.siliconflow.cn</a>
          </p>

          {/* ── 数据源列表 ── */}
          {sourcesLoading ? (
            <div className="grid gap-4 pr-1">
              {[1, 2].map((i) => (
                <Card key={i} className="border-0 text-white" style={themeCardGradient()}>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-4 animate-pulse">
                      <div className="h-10 w-10 rounded-full bg-white/10 shrink-0" />
                      <div className="flex-1 space-y-2.5">
                        <div className="flex items-center gap-2">
                          <div className="h-4 w-20 bg-white/15 rounded" />
                          <div className="h-4 w-12 bg-white/10 rounded-lg" />
                        </div>
                        <div className="h-3 w-48 bg-white/10 rounded font-mono" />
                        <div className="h-3 w-32 bg-white/10 rounded" />
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="h-8 w-8 bg-white/10 rounded" />
                        <div className="h-8 w-8 bg-white/10 rounded" />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : sources.length === 0 && !configLoading ? (
            <div className="flex flex-col items-center justify-center min-h-[300px] text-muted-foreground">
              <Database className="w-16 h-16 text-text-disabled mb-4" />
              <p className="text-base font-medium text-text-primary mb-1">知识库为空</p>
              <p className="text-sm text-text-secondary mb-4">给 AI 喂资料，让它从你的文档中找到答案。</p>
              <Button onClick={() => setShowAdd(true)} className="mb-4">
                <Plus className="h-4 w-4 mr-1" />
                添加数据源
              </Button>
              <div className="text-xs space-y-1 text-center text-text-tertiary">
                <p>💡 支持 txt/md/py/json/csv/html/xml/docx/pdf 格式</p>
                <p>💡 推荐先用硅基流动免费 API 做 Embedding</p>
              </div>
            </div>
          ) : (
            <div className="grid gap-4 pr-1">
              {sources.map((s) => (
                <Card key={s.name} className={`relative overflow-hidden group text-white transition-colors duration-300 ${s.enabled ? 'border-0' : 'border border-white/5'}`} style={themeCardGradient(s.enabled)}>
                  {/* 首字母丝印 */}
                  <div className={`absolute -bottom-3 -right-4 text-[130px] font-black leading-none select-none pointer-events-none transition-opacity duration-300 ${s.enabled ? 'text-white/[0.05]' : 'text-white/[0.02]'}`}>
                    {(s.name.trim()[0]?.toUpperCase() || 'R')}
                  </div>

                  <CardContent className="p-4 relative z-10">
                    <div className="flex items-center gap-4">
                      <div className={`w-10 h-10 shrink-0 rounded-full flex items-center justify-center transition-colors duration-300 ${
                        s.enabled ? 'bg-white/12 backdrop-blur-sm ring-1 ring-white/10' : 'bg-white/5 ring-1 ring-white/5'
                      }`}>
                        <Folder className={`h-5 w-5 transition-colors duration-300 ${s.enabled ? 'text-white/80' : 'text-white/30'}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={`font-medium transition-colors duration-300 ${s.enabled ? 'text-white/95' : 'text-white/50'}`}>{s.name}</span>
                          {s.indexed && <span className={`text-[10px] px-1.5 py-0.5 rounded-md transition-colors duration-300 ${s.enabled ? 'bg-white/18 backdrop-blur-sm text-white/80' : 'bg-white/5 text-white/35'}`}>已索引</span>}
                        </div>
                        <p className={`text-sm font-mono truncate mt-0.5 transition-colors duration-300 ${s.enabled ? 'text-white/50' : 'text-white/25'}`}>{s.path}</p>
                        <p className={`text-xs mt-0.5 transition-colors duration-300 ${s.enabled ? 'text-white/40' : 'text-white/20'}`}>
                          {s.file_count > 0 && `${s.file_count} 个文件`}
                          {s.chroma_docs > 0 && ` | ChromaDB: ${s.chroma_docs} 片段`}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <Switch checked={s.enabled} onCheckedChange={(v) => handleToggle(s.name, v)} />
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleIndex(s.name)}
                          disabled={indexing[s.name]}
                          className={`text-xs transition-colors duration-300 ${s.enabled ? 'text-white/60 hover:text-white hover:bg-white/8' : 'text-white/30 hover:text-white/50 hover:bg-white/5'}`}
                        >
                          <RefreshCw className={`h-4 w-4 mr-1 ${indexing[s.name] ? 'animate-spin' : ''}`} />
                          {indexing[s.name] ? '索引中...' : '索引'}
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => setDeleteTarget(s.name)} className={`transition-colors duration-300 ${s.enabled ? 'text-white/25 hover:text-red-200/80 hover:bg-white/8' : 'text-white/15 hover:text-red-200/60 hover:bg-white/5'}`}>
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
      </ScrollArea>

      {/* Add RAG Source Dialog */}
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent className="sm:max-w-[520px]">
          <DialogHeader>
            <DialogTitle>添加数据源</DialogTitle>
            <DialogDescription>添加本地文档目录，系统将自动索引文档内容</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>数据源名称 <span className="text-red-500">*</span></Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="例如: 项目文档" maxLength={100} />
            </div>
            <div className="space-y-2">
              <Label>数据源路径 <span className="text-red-500">*</span></Label>
              <Input value={form.path} onChange={(e) => setForm({ ...form, path: e.target.value })} placeholder="rag/使用指导 (相对项目根)" maxLength={500} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAdd(false)}>取消</Button>
            <Button onClick={handleAdd}>添加</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── 删除确认 ── */}
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}
        title="删除数据源"
        description={`确定要删除数据源 ${deleteTarget} 吗？此操作不可撤销。`}
        onConfirm={async () => {
          if (deleteTarget) await handleDelete(deleteTarget)
          setDeleteTarget(null)
        }}
      />
    </div>
  )
}
