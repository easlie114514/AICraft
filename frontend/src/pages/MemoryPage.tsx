import { useState, useEffect, useCallback } from 'react'
import { Eye, Trash2, Search, RefreshCw, FileText, MessageSquare } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
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
  preview: string
  path: string
}

interface SearchResult {
  results: string[]
}

export default function MemoryPage() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [notes, setNotes] = useState<Note[]>([])
  const [viewConv, setViewConv] = useState<Record<string, unknown> | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<string[]>([])

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

  useEffect(() => {
    loadConversations()
    loadNotes()
  }, [loadConversations, loadNotes])

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

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    try {
      const data = await api.post<SearchResult>('/memory/search', { query: searchQuery, top_k: 5 })
      setSearchResults(data.results)
    } catch { /* ignore */ }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden p-6">
      <div className="shrink-0 flex items-center justify-between mb-4">
        <h2 className="text-lg font-medium text-foreground">记忆</h2>
        <Button variant="outline" size="icon" onClick={() => { loadConversations(); loadNotes() }} className="rounded-xl">
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
          className="flex-1 rounded-[10px]"
        />
        <Button variant="outline" size="icon" onClick={handleSearch} className="rounded-xl shrink-0">
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

      <Tabs defaultValue="conversations" className="flex-1 flex flex-col min-h-0">
        <TabsList className="w-fit rounded-xl mb-4">
          <TabsTrigger value="conversations" className="rounded-xl">
            <MessageSquare className="h-4 w-4 mr-1" />
            对话历史
          </TabsTrigger>
          <TabsTrigger value="notes" className="rounded-xl">
            <FileText className="h-4 w-4 mr-1" />
            项目笔记
          </TabsTrigger>
        </TabsList>

        <TabsContent value="conversations" className="flex-1">
          <ScrollArea className="flex-1 min-h-0">
            {conversations.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
                <MessageSquare className="h-10 w-10 mb-2 opacity-30" />
                <p className="text-sm">暂无对话历史</p>
              </div>
            ) : (
              <div className="grid gap-3 pr-1">
                {conversations.map((c) => (
                  <Card key={c.id} className="rounded-2xl">
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
                          <Button variant="ghost" size="sm" onClick={() => handleView(c.id)} className="rounded-xl">
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDeleteConv(c.id)} className="rounded-xl text-muted-foreground hover:text-destructive">
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
        </TabsContent>

        <TabsContent value="notes" className="flex-1">
          <ScrollArea className="flex-1 min-h-0">
            {notes.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
                <FileText className="h-10 w-10 mb-2 opacity-30" />
                <p className="text-sm">暂无项目笔记</p>
                <p className="text-xs mt-1">在 memory/project-notes/ 下创建 .md 文件</p>
              </div>
            ) : (
              <div className="grid gap-3 pr-1">
                {notes.map((n) => (
                  <Card key={n.name} className="rounded-2xl">
                    <CardContent className="p-3">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="rounded-lg text-xs">笔记</Badge>
                        <span className="text-sm font-medium">{n.name}</span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1 truncate">{n.preview}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </ScrollArea>
        </TabsContent>
      </Tabs>

      {/* View Conversation Dialog */}
      <Dialog open={!!viewConv} onOpenChange={() => setViewConv(null)}>
        <DialogContent className="sm:max-w-[600px] rounded-[20px] max-h-[80vh]">
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
            <Button variant="outline" onClick={() => setViewConv(null)} className="rounded-xl">关闭</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
