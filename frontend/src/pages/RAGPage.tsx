import { useState, useEffect, useCallback } from 'react'
import { Plus, Trash2, Folder, RefreshCw, Database } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
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

export default function RAGPage() {
  const [sources, setSources] = useState<RAGSource[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [indexing, setIndexing] = useState<Record<string, boolean>>({})
  const [form, setForm] = useState({ name: '', path: '' })

  const loadSources = useCallback(async () => {
    try {
      const data = await api.get<RAGSource[]>('/rag')
      setSources(data)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadSources() }, [loadSources])

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

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden p-6">
      <div className="shrink-0 flex items-center justify-between mb-4">
        <h2 className="text-lg font-medium text-foreground">RAG 数据源</h2>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={loadSources} className="rounded-xl">
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button onClick={() => setShowAdd(true)} className="rounded-xl">
            <Plus className="h-4 w-4 mr-1" />
            添加数据源
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        {sources.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
            <Database className="h-12 w-12 mb-3 opacity-30" />
            <p className="text-sm">暂无 RAG 数据源</p>
            <p className="text-xs mt-1">添加本地文档目录作为知识库数据源</p>
          </div>
        ) : (
          <div className="grid gap-4 pr-1">
            {sources.map((s) => (
              <Card key={s.name} className="rounded-2xl">
                <CardContent className="p-4">
                  <div className="flex items-center gap-4">
                    <Avatar className="h-10 w-10 shrink-0 rounded-xl" style={{ background: 'linear-gradient(135deg, #5B9BD5, #2B4C7E)' }}>
                      <AvatarFallback className="bg-transparent text-white">
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
                      <Switch checked={s.enabled} onCheckedChange={(v) => handleToggle(s.name, v)} className="rounded-xl" />
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleIndex(s.name)}
                        disabled={indexing[s.name]}
                        className="rounded-xl"
                      >
                        <RefreshCw className={`h-4 w-4 mr-1 ${indexing[s.name] ? 'animate-spin' : ''}`} />
                        {indexing[s.name] ? '索引中...' : '索引'}
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => handleDelete(s.name)} className="rounded-xl text-muted-foreground hover:text-destructive">
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
        <DialogContent className="sm:max-w-[520px] rounded-[20px]">
          <DialogHeader>
            <DialogTitle>添加数据源</DialogTitle>
            <DialogDescription>添加本地文档目录，系统将自动索引文档内容</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>数据源名称</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="rounded-[10px]" placeholder="例如: 项目文档" />
            </div>
            <div className="space-y-2">
              <Label>数据源路径</Label>
              <Input value={form.path} onChange={(e) => setForm({ ...form, path: e.target.value })} className="rounded-[10px]" placeholder="rag/使用指导 (相对项目根)" />
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
