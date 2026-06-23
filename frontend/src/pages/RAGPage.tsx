import { useState, useEffect, useCallback } from 'react'
import { Plus, Trash2, Folder, RefreshCw, Database, Settings2, Eye, EyeOff, FlaskConical } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Separator } from '@/components/ui/separator'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { api } from '@/lib/api'

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
}

const EMBEDDING_MODELS = [
  { value: 'BAAI/bge-large-zh-v1.5', label: 'BAAI/bge-large-zh-v1.5 (中文, 1024维)' },
  { value: 'BAAI/bge-large-en-v1.5', label: 'BAAI/bge-large-en-v1.5 (英文, 1024维)' },
  { value: 'BAAI/bge-m3', label: 'BAAI/bge-m3 (多语言, 1024维)' },
]

export default function RAGPage() {
  const [sources, setSources] = useState<RAGSource[]>([])
  const [showAdd, setShowAdd] = useState(false)
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
    try {
      const data = await api.get<RAGSource[]>('/rag')
      setSources(data)
    } catch { /* ignore */ }
  }, [])

  const loadRagConfig = useCallback(async () => {
    setConfigLoading(true)
    try {
      const data = await api.get<RAGConfig>('/rag/config')
      setRagConfig(data)
      setEmbedMode(data.embedding_mode)
      setEmbedModel(data.embedding_model)
      setApiBase(data.embedding_api_base)
      // 不清空 apiKey — 保持用户已输入的内容
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

  const handleModeChange = async (mode: string | null) => {
    if (!mode) return
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
    // 失焦时保存
  }

  const handleApiBaseBlur = () => {
    if (apiBase.trim() && apiBase !== ragConfig?.embedding_api_base) {
      saveRagConfig({ embedding_api_base: apiBase.trim() })
    }
  }

  const handleSaveKey = async () => {
    if (!apiKey.trim()) return
    await saveRagConfig({ embedding_api_key: apiKey.trim() })
    // 保存成功后保持输入内容，不清空
  }

  const handleTestConnection = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const key = apiKey.trim() || ''  // 用当前输入或已保存的 key
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
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden p-6">
      <div className="shrink-0 flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-text-primary">RAG 数据源</h2>
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
        {/* ── Embedding 配置卡片 ── */}
        <Card className="mb-4">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <Settings2 className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Embedding 配置</span>
              {ragConfig?.has_api_key && (
                <Badge className="rounded-lg text-xs" variant="secondary">API 已配置</Badge>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Embedding 模式 */}
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Embedding 模式</Label>
                <Select value={embedMode} onValueChange={handleModeChange}>
                  <SelectTrigger className="w-full h-8 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent sideOffset={6} alignItemWithTrigger={false}>
                    <SelectItem value="auto">auto — 有 Key 用 API，否则本地</SelectItem>
                    <SelectItem value="api">api — 强制硅基流动 API</SelectItem>
                    <SelectItem value="local">local — 本地 ONNX 模型</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Embedding 模型 */}
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Embedding 模型</Label>
                <Select value={embedModel} onValueChange={handleModelChange} disabled={isLocalMode}>
                  <SelectTrigger className="w-full h-8 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent sideOffset={6} alignItemWithTrigger={false}>
                    {EMBEDDING_MODELS.map((m) => (
                      <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* API 地址 */}
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">API 地址</Label>
                <Input
                  value={apiBase}
                  onChange={(e) => handleApiBaseChange(e.target.value)}
                  onBlur={handleApiBaseBlur}
                  disabled={isLocalMode}
                  className="h-8 text-sm font-mono"
                  placeholder="https://api.siliconflow.cn/v1"
                />
              </div>

              {/* API Key — local 模式隐藏 */}
              {!isLocalMode && (
                <div className="space-y-1.5">
                  <Label className="text-xs text-muted-foreground">
                    硅基流动 API Key
                    {ragConfig?.has_api_key && !apiKey && (
                      <span className="ml-1 text-muted-foreground/60">{ragConfig.embedding_api_key_masked}</span>
                    )}
                  </Label>
                  <div className="flex gap-1.5">
                    <div className="relative flex-1">
                      <Input
                        type={showKey ? 'text' : 'password'}
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        className="h-8 text-sm pr-8"
                        placeholder={ragConfig?.has_api_key ? '输入新 Key 覆盖旧值' : 'sk-...'}
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
                  {/* 测试结果 */}
                  {testResult && (
                    <p className={`text-xs mt-1 ${testResult.success ? 'text-green-600' : 'text-red-500'}`}>
                      {testResult.success
                        ? `✅ 连接成功，维度: ${testResult.dimension}`
                        : `❌ ${testResult.error}`}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* 模式切换提示 */}
            {ragConfig && embedMode !== ragConfig.embedding_mode && (
              <div className="mt-3 p-2 rounded-lg bg-warning-light/50 border border-warning/30">
                <p className="text-xs text-warning">
                  ⚠️ Embedding 模式已更改。API(1024维) 和本地 ONNX(384维) 向量不兼容，切换后需重新索引全部数据源。
                </p>
              </div>
            )}

            <Separator className="my-3" />

            <p className="text-xs text-muted-foreground">
              免费注册硅基流动 API Key: <a href="https://cloud.siliconflow.cn" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">cloud.siliconflow.cn</a>
            </p>
          </CardContent>
        </Card>

        {/* ── 数据源列表 ── */}
        {sources.length === 0 && !configLoading ? (
          <div className="flex flex-col items-center justify-center min-h-[300px] text-muted-foreground">
            <Database className="w-16 h-16 text-text-disabled mb-4" />
            <p className="text-base font-medium text-text-primary mb-1">RAG 知识库</p>
            <p className="text-sm text-text-secondary mb-4">给 AI 喂资料，让它从你的文档中找到答案。</p>
            <Button onClick={() => setShowAdd(true)} className="mb-4">
              <Plus className="h-4 w-4 mr-1" />
              添加数据源
            </Button>
            <div className="text-xs space-y-1 text-center text-text-tertiary">
              <p>💡 支持 txt/md/py/json/csv/html/xml/docx/pdf 格式</p>
              <p>💡 推荐先用硅基流动免费 API 做 Embedding（设置页配置）</p>
            </div>
          </div>
        ) : (
          <div className="grid gap-4 pr-1">
            {sources.map((s) => (
              <Card key={s.name} className="hover:shadow-card-hover transition-shadow duration-200">
                <CardContent className="p-4">
                  <div className="flex items-center gap-4">
                    <Avatar className="h-10 w-10 shrink-0 rounded-full bg-primary/15">
                      <AvatarFallback className="bg-transparent text-primary">
                        <Folder className="h-5 w-5" />
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{s.name}</span>
                        {s.indexed && <Badge className="rounded-lg text-xs">已索引</Badge>}
                      </div>
                      <p className="text-sm text-muted-foreground font-mono truncate mt-0.5">{s.path}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {s.file_count > 0 && `${s.file_count} 个文件`}
                        {s.chroma_docs > 0 && ` | ChromaDB: ${s.chroma_docs} 片段`}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Switch checked={s.enabled} onCheckedChange={(v) => handleToggle(s.name, v)} />
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleIndex(s.name)}
                        disabled={indexing[s.name]}
                        
                      >
                        <RefreshCw className={`h-4 w-4 mr-1 ${indexing[s.name] ? 'animate-spin' : ''}`} />
                        {indexing[s.name] ? '索引中...' : '索引'}
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => handleDelete(s.name)} className="text-muted-foreground hover:text-destructive">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
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
              <Label>数据源名称</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}  placeholder="例如: 项目文档" />
            </div>
            <div className="space-y-2">
              <Label>数据源路径</Label>
              <Input value={form.path} onChange={(e) => setForm({ ...form, path: e.target.value })}  placeholder="rag/使用指导 (相对项目根)" />
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
