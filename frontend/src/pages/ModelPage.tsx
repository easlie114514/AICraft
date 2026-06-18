import { useState, useEffect, useCallback } from 'react'
import { Plus, Cpu, Star, Trash2, RefreshCw } from 'lucide-react'
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
  is_default?: boolean
  is_current?: boolean
}

type TestStatus = { model: string; ok: boolean; message: string } | null

export default function ModelPage() {
  const [models, setModels] = useState<ModelConfig[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [testResults, setTestResults] = useState<Record<string, TestStatus>>({})
  const [form, setForm] = useState({ name: '', provider: 'deepseek', model_id: '', api_key: '', api_base: '' })

  const loadModels = useCallback(async () => {
    try {
      const data = await api.get<ModelConfig[]>('/models')
      setModels(data)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadModels() }, [loadModels])

  const handleAdd = async () => {
    if (!form.name || !form.model_id) return
    await api.post('/models', form)
    setShowAdd(false)
    setForm({ name: '', provider: 'deepseek', model_id: '', api_key: '', api_base: '' })
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
      setTestResults((prev) => ({ ...prev, [name]: data }))
    } catch (e: any) {
      setTestResults((prev) => ({ ...prev, [name]: { model: name, ok: false, message: e.message } }))
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden p-6">
      <div className="shrink-0 flex items-center justify-between mb-4">
        <h2 className="text-lg font-medium text-foreground">模型配置</h2>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={loadModels} className="rounded-xl">
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button onClick={() => setShowAdd(true)} className="rounded-xl">
            <Plus className="h-4 w-4 mr-1" />
            添加模型
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        {models.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
            <Cpu className="h-12 w-12 mb-3 opacity-30" />
            <p className="text-sm">暂无模型配置</p>
            <p className="text-xs mt-1">点击"添加模型"开始配置 LLM API</p>
          </div>
        ) : (
          <div className="grid gap-4 pr-1">
            {models.map((m) => {
              const test = testResults[m.name]
              return (
                <Card key={m.name} className="rounded-2xl">
                  <CardContent className="p-4">
                    <div className="flex items-start gap-4">
                      <Avatar className="h-10 w-10 shrink-0 rounded-xl" style={{ background: 'linear-gradient(135deg, #5B9BD5, #2B4C7E)' }}>
                        <AvatarFallback className="bg-transparent text-white">
                          <Cpu className="h-5 w-5" />
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-medium text-foreground">{m.name}</span>
                          {m.is_default && <Badge className="rounded-lg">默认</Badge>}
                          {m.is_current && <Badge variant="secondary" className="rounded-lg">当前</Badge>}
                        </div>
                        <p className="text-sm text-muted-foreground font-mono mt-0.5 truncate">{m.model_id}</p>
                        {test && (
                          <Badge variant={test.ok ? 'default' : 'destructive'} className="rounded-lg mt-1.5">
                            {test.ok ? '✓ 连接成功' : '✗ 连接失败'}
                          </Badge>
                        )}
                        {test && !test.ok && (
                          <p className="text-xs text-destructive mt-1 truncate max-w-md">{test.message}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <Button variant="outline" size="sm" onClick={() => handleTest(m.name)} className="rounded-xl">
                          测试连接
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleSetDefault(m.name)}
                          className={cn('rounded-xl', m.is_default && 'text-yellow-500')}
                          title="设为默认"
                        >
                          <Star className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(m.name)}
                          className="rounded-xl text-muted-foreground hover:text-destructive"
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

      {/* Add Model Dialog */}
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent className="sm:max-w-[520px] rounded-[20px]">
          <DialogHeader>
            <DialogTitle>添加模型</DialogTitle>
            <DialogDescription>配置 LLM API 连接信息</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>模型名称</Label>
              <Input
                placeholder="例如: DeepSeek-V4"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="rounded-[10px]"
              />
            </div>
            <div className="space-y-2">
              <Label>Provider</Label>
              <Select value={form.provider} onValueChange={(v) => setForm({ ...form, provider: v })}>
                <SelectTrigger className="rounded-[10px]">
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
                className="rounded-[10px]"
              />
            </div>
            <div className="space-y-2">
              <Label>API Key</Label>
              <Input
                type="password"
                placeholder="sk-..."
                value={form.api_key}
                onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                className="rounded-[10px]"
              />
            </div>
            <div className="space-y-2">
              <Label>API Base (可选)</Label>
              <Input
                placeholder="https://api.example.com/v1"
                value={form.api_base}
                onChange={(e) => setForm({ ...form, api_base: e.target.value })}
                className="rounded-[10px]"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAdd(false)} className="rounded-xl">取消</Button>
            <Button onClick={handleAdd} className="rounded-xl">添加</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
