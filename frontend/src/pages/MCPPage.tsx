import { useState, useEffect, useCallback } from 'react'
import { Plus, Trash2, Zap, ChevronDown, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { api } from '@/lib/api'

interface MCPConnection {
  name: string
  type: string
  host: string
  port: number
  url: string
  command: string
  args: string[]
  env: Record<string, string>
  enabled: boolean
  status: string
  tools: { name: string; description?: string }[]
  error_msg: string
  display_url: string
}

const statusMap: Record<string, { variant: 'default' | 'secondary' | 'destructive'; label: string }> = {
  connected: { variant: 'default', label: '已连接' },
  disconnected: { variant: 'secondary', label: '未连接' },
  connecting: { variant: 'secondary', label: '连接中' },
  error: { variant: 'destructive', label: '错误' },
}

export default function MCPPage() {
  const [connections, setConnections] = useState<MCPConnection[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [connecting, setConnecting] = useState<Record<string, boolean>>({})
  const [form, setForm] = useState({
    name: '', type: 'sse', host: '', port: '', url: '', command: '', args: '',
  })

  const loadConnections = useCallback(async () => {
    try {
      const data = await api.get<MCPConnection[]>('/mcp')
      setConnections(data)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadConnections() }, [loadConnections])

  const handleAdd = async () => {
    if (!form.name.trim()) return
    await api.post('/mcp', {
      name: form.name,
      type: form.type,
      host: form.host,
      port: parseInt(form.port) || 0,
      url: form.url,
      command: form.command,
      args: form.args.split(' ').filter(Boolean),
      env: {},
    })
    setShowAdd(false)
    setForm({ name: '', type: 'sse', host: '', port: '', url: '', command: '', args: '' })
    loadConnections()
  }

  const handleToggle = async (name: string, enabled: boolean) => {
    await api.put(`/mcp/${encodeURIComponent(name)}/toggle`, { enabled })
    loadConnections()
  }

  const handleConnect = async (name: string) => {
    setConnecting((prev) => ({ ...prev, [name]: true }))
    try {
      await api.post(`/mcp/${encodeURIComponent(name)}/connect`)
      loadConnections()
    } finally {
      setConnecting((prev) => ({ ...prev, [name]: false }))
    }
  }

  const handleDisconnect = async (name: string) => {
    await api.post(`/mcp/${encodeURIComponent(name)}/disconnect`)
    loadConnections()
  }

  const handleDelete = async (name: string) => {
    await api.delete(`/mcp/${encodeURIComponent(name)}`)
    loadConnections()
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden p-6">
      <div className="shrink-0 flex items-center justify-between mb-4">
        <h2 className="text-lg font-medium text-foreground">MCP 连接</h2>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={loadConnections} className="rounded-xl">
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button onClick={() => setShowAdd(true)} className="rounded-xl">
            <Plus className="h-4 w-4 mr-1" />
            添加连接
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        {connections.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
            <Zap className="h-12 w-12 mb-3 opacity-30" />
            <p className="text-sm">暂无 MCP 连接</p>
            <p className="text-xs mt-1">添加 MCP 服务器以扩展 AI 能力</p>
          </div>
        ) : (
          <div className="grid gap-4 pr-1">
            {connections.map((conn) => {
              const status = statusMap[conn.status] || statusMap.disconnected
              return (
                <Card key={conn.name} className="rounded-2xl">
                  <CardContent className="p-4">
                    <div className="flex items-start gap-4">
                      <Avatar className="h-10 w-10 shrink-0 rounded-xl" style={{ background: 'linear-gradient(135deg, #5B9BD5, #2B4C7E)' }}>
                        <AvatarFallback className="bg-transparent text-white">
                          <Zap className="h-5 w-5" />
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-medium">{conn.name}</span>
                          <Badge variant="secondary" className="rounded-lg text-xs">{conn.type.toUpperCase()}</Badge>
                          <Badge variant={status.variant} className="rounded-lg text-xs">{status.label}</Badge>
                        </div>
                        <p className="text-sm text-muted-foreground font-mono mt-0.5 truncate">
                          {conn.type === 'sse' ? conn.display_url : conn.command}
                        </p>
                        {conn.error_msg && (
                          <p className="text-xs text-destructive mt-1 truncate">{conn.error_msg}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <Switch checked={conn.enabled} onCheckedChange={(v) => handleToggle(conn.name, v)} className="rounded-xl" />
                        {conn.status === 'connected' ? (
                          <Button variant="outline" size="sm" onClick={() => handleDisconnect(conn.name)} className="rounded-xl">断开</Button>
                        ) : (
                          <Button size="sm" onClick={() => handleConnect(conn.name)} disabled={connecting[conn.name]} className="rounded-xl">
                            {connecting[conn.name] ? '连接中...' : '连接'}
                          </Button>
                        )}
                        <Button variant="ghost" size="icon" onClick={() => handleDelete(conn.name)} className="rounded-xl text-muted-foreground hover:text-destructive">
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    {conn.tools.length > 0 && (
                      <Collapsible className="mt-3">
                        <CollapsibleTrigger asChild>
                          <Button variant="ghost" size="sm" className="text-xs text-muted-foreground -ml-2">
                            <Badge variant="outline" className="rounded-lg mr-2">{conn.tools.length} 个工具</Badge>
                            <ChevronDown className="h-3 w-3" />
                          </Button>
                        </CollapsibleTrigger>
                        <CollapsibleContent>
                          <div className="mt-2 space-y-1 pl-2">
                            {conn.tools.map((t) => (
                              <div key={t.name} className="text-xs text-muted-foreground">
                                <span className="font-mono font-medium text-foreground">{t.name}</span>
                                {t.description && <span className="ml-2">{t.description}</span>}
                              </div>
                            ))}
                          </div>
                        </CollapsibleContent>
                      </Collapsible>
                    )}
                  </CardContent>
                </Card>
              )
            })}
          </div>
        )}
      </ScrollArea>

      {/* Add MCP Dialog */}
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent className="sm:max-w-[520px] rounded-[20px]">
          <DialogHeader>
            <DialogTitle>添加 MCP 连接</DialogTitle>
            <DialogDescription>配置 MCP 服务器连接信息</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>连接名称</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="rounded-[10px]" placeholder="例如: Jira MCP" />
            </div>
            <div className="space-y-2">
              <Label>连接类型</Label>
              <Select value={form.type} onValueChange={(v) => setForm({ ...form, type: v })}>
                <SelectTrigger className="rounded-[10px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="sse">SSE</SelectItem>
                  <SelectItem value="stdio">Stdio</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {form.type === 'sse' ? (
              <div className="space-y-2">
                <Label>URL</Label>
                <Input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} className="rounded-[10px]" placeholder="http://localhost:8080/sse" />
              </div>
            ) : (
              <>
                <div className="space-y-2">
                  <Label>命令</Label>
                  <Input value={form.command} onChange={(e) => setForm({ ...form, command: e.target.value })} className="rounded-[10px]" placeholder="例如: npx" />
                </div>
                <div className="space-y-2">
                  <Label>参数（空格分隔）</Label>
                  <Input value={form.args} onChange={(e) => setForm({ ...form, args: e.target.value })} className="rounded-[10px]" placeholder="例如: -y @modelcontextprotocol/server-filesystem" />
                </div>
              </>
            )}
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
