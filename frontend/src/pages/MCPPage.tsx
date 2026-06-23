import { useState, useEffect, useCallback } from 'react'
import { Plus, Trash2, Zap, ChevronDown, RefreshCw, Shield, Lock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
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

const FACTORY_MCP_NAMES = ['文件管理', '代码执行']

const statusMap: Record<string, { variant: 'default' | 'secondary' | 'destructive'; label: string }> = {
  connected: { variant: 'default', label: '已连接' },
  disconnected: { variant: 'secondary', label: '未连接' },
  connecting: { variant: 'secondary', label: '连接中' },
  error: { variant: 'destructive', label: '错误' },
}

interface PermissionConfig {
  trusted_paths: string[]
  denied_paths: string[]
  prompt_timeout_seconds: number
}

export default function MCPPage() {
  const [connections, setConnections] = useState<MCPConnection[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [envStatus, setEnvStatus] = useState<{ available: boolean; path: string | null; version: string | null } | null>(null)
  const [connecting, setConnecting] = useState<Record<string, boolean>>({})
  const [permConfig, setPermConfig] = useState<PermissionConfig | null>(null)
  const [newTrustedPath, setNewTrustedPath] = useState('')
  const [newDeniedPath, setNewDeniedPath] = useState('')
  const [form, setForm] = useState({
    name: '', type: 'sse', host: '', port: '', url: '', command: '', args: '',
  })

  const loadConnections = useCallback(async () => {
    try {
      const data = await api.get<MCPConnection[]>('/mcp')
      setConnections(data)
    } catch { /* ignore */ }
  }, [])

  const loadEnvStatus = useCallback(async () => {
    try {
      const data = await api.get<{ available: boolean; path: string | null; version: string | null }>('/mcp/env-check')
      setEnvStatus(data)
    } catch { /* ignore */ }
  }, [])

  const loadPermissions = useCallback(async () => {
    try {
      const data = await api.get<PermissionConfig>('/mcp/permissions')
      setPermConfig(data)
    } catch { /* ignore */ }
  }, [])

  const savePermissions = useCallback(async (updated: PermissionConfig) => {
    if (!updated) return
    try {
      await api.put('/mcp/permissions', updated)
      setPermConfig(updated)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadConnections(); loadEnvStatus(); loadPermissions() }, [loadConnections, loadEnvStatus, loadPermissions])

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
        <h2 className="text-xl font-semibold text-text-primary">MCP 连接</h2>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={loadConnections}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button onClick={() => setShowAdd(true)}>
            <Plus className="h-4 w-4 mr-1" />
            添加连接
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        {connections.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
            <Zap className="w-16 h-16 text-text-disabled mb-4" />
            <p className="text-sm text-text-secondary">暂无 MCP 连接</p>
            <p className="text-xs text-text-tertiary mt-1">添加 MCP 服务器以扩展 AI 能力</p>
          </div>
        ) : (
          <div className="grid gap-4 pr-1">
            {connections.map((conn) => {
              const status = statusMap[conn.status] || statusMap.disconnected
              return (
                <Card key={conn.name} className="hover:shadow-card-hover transition-shadow duration-200">
                  <CardContent className="p-4">
                    <div className="flex items-start gap-4">
                      <Avatar className="h-10 w-10 shrink-0 rounded-full bg-primary/15">
                        <AvatarFallback className="bg-transparent text-primary">
                          <Zap className="h-5 w-5" />
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-medium">{conn.name}</span>
                          <Badge variant="secondary" className="rounded-lg text-xs">{conn.type.toUpperCase()}</Badge>
                          <Badge variant={status.variant} className="rounded-lg text-xs">{status.label}</Badge>
                          {envStatus && FACTORY_MCP_NAMES.includes(conn.name) && (
                            envStatus.available ? (
                              <Badge className="rounded-lg text-xs bg-success-light text-success border border-success/30 hover:bg-success-light">
                                {'✅'} 环境就绪
                              </Badge>
                            ) : (
                              <a href="https://nodejs.org/" target="_blank" rel="noopener noreferrer">
                                <Badge className="rounded-lg text-xs bg-danger-light text-danger border border-danger/30 hover:bg-danger-light cursor-pointer">
                                  {'⚠️'} 需要Node.js
                                </Badge>
                              </a>
                            )
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground font-mono mt-0.5 truncate">
                          {conn.type === 'sse' ? conn.display_url : conn.command}
                        </p>
                        {conn.error_msg && (
                          <p className="text-xs text-destructive mt-1 truncate">{conn.error_msg}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <Switch checked={conn.enabled} onCheckedChange={(v) => handleToggle(conn.name, v)} />
                        {conn.status === 'connected' ? (
                          <Button variant="outline" size="sm" onClick={() => handleDisconnect(conn.name)}>断开</Button>
                        ) : (
                          <Button size="sm" onClick={() => handleConnect(conn.name)} disabled={connecting[conn.name]}>
                            {connecting[conn.name] ? '连接中...' : '连接'}
                          </Button>
                        )}
                        <Button variant="ghost" size="icon" onClick={() => handleDelete(conn.name)} className="text-muted-foreground hover:text-destructive">
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    {conn.tools.length > 0 && (
                      <Collapsible className="mt-3">
                        <CollapsibleTrigger>
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
        {permConfig && (
          <div className="mt-6">
            <Separator className="mb-4" />
            <div className="flex items-center gap-2 mb-3">
              <Shield className="h-4 w-4 text-primary" />
              <h3 className="text-base font-semibold text-text-primary">文件访问权限</h3>
              <span className="text-xs text-text-tertiary">
                AI 访问文件前需要你的批准 · 超时 {permConfig.prompt_timeout_seconds} 秒自动拒绝
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {/* 信任路径 */}
              <Card>
                <CardContent className="p-3 space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-medium text-success">
                    <Lock className="h-3 w-3" />
                    信任路径（自动放行）
                  </div>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {permConfig.trusted_paths.length === 0 && (
                      <p className="text-xs text-text-disabled">无信任路径</p>
                    )}
                    {permConfig.trusted_paths.map((p) => (
                      <div key={p} className="flex items-center gap-1 text-xs font-mono bg-muted/50 px-1.5 py-0.5 rounded">
                        <span className="flex-1 truncate">{p}</span>
                        <Button
                          variant="ghost" size="icon"
                          className="h-4 w-4 text-muted-foreground hover:text-destructive shrink-0"
                          onClick={() => {
                            const updated = { ...permConfig, trusted_paths: permConfig.trusted_paths.filter((x) => x !== p) }
                            savePermissions(updated)
                          }}
                        >
                          <Trash2 className="h-2.5 w-2.5" />
                        </Button>
                      </div>
                    ))}
                  </div>
                  <div className="flex gap-1">
                    <Input
                      className="h-7 text-xs"
                      placeholder="添加路径..."
                      value={newTrustedPath}
                      onChange={(e) => setNewTrustedPath(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && newTrustedPath.trim()) {
                          savePermissions({ ...permConfig, trusted_paths: [...permConfig.trusted_paths, newTrustedPath.trim()] })
                          setNewTrustedPath('')
                        }
                      }}
                    />
                    <Button
                      variant="outline" size="sm" className="h-7 text-xs px-2 shrink-0"
                      onClick={() => {
                        if (newTrustedPath.trim()) {
                          savePermissions({ ...permConfig, trusted_paths: [...permConfig.trusted_paths, newTrustedPath.trim()] })
                          setNewTrustedPath('')
                        }
                      }}
                    >
                      <Plus className="h-3 w-3" />
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* 拒绝路径 */}
              <Card>
                <CardContent className="p-3 space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-medium text-danger">
                    <Shield className="h-3 w-3" />
                    拒绝路径（禁止访问）
                  </div>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {permConfig.denied_paths.length === 0 && (
                      <p className="text-xs text-text-disabled">无拒绝路径</p>
                    )}
                    {permConfig.denied_paths.map((p) => (
                      <div key={p} className="flex items-center gap-1 text-xs font-mono bg-danger/5 px-1.5 py-0.5 rounded">
                        <span className="flex-1 truncate">{p}</span>
                        <Button
                          variant="ghost" size="icon"
                          className="h-4 w-4 text-muted-foreground hover:text-destructive shrink-0"
                          onClick={() => {
                            const updated = { ...permConfig, denied_paths: permConfig.denied_paths.filter((x) => x !== p) }
                            savePermissions(updated)
                          }}
                        >
                          <Trash2 className="h-2.5 w-2.5" />
                        </Button>
                      </div>
                    ))}
                  </div>
                  <div className="flex gap-1">
                    <Input
                      className="h-7 text-xs"
                      placeholder="添加路径..."
                      value={newDeniedPath}
                      onChange={(e) => setNewDeniedPath(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && newDeniedPath.trim()) {
                          savePermissions({ ...permConfig, denied_paths: [...permConfig.denied_paths, newDeniedPath.trim()] })
                          setNewDeniedPath('')
                        }
                      }}
                    />
                    <Button
                      variant="outline" size="sm" className="h-7 text-xs px-2 shrink-0"
                      onClick={() => {
                        if (newDeniedPath.trim()) {
                          savePermissions({ ...permConfig, denied_paths: [...permConfig.denied_paths, newDeniedPath.trim()] })
                          setNewDeniedPath('')
                        }
                      }}
                    >
                      <Plus className="h-3 w-3" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </ScrollArea>

      {/* Add MCP Dialog */}
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent className="sm:max-w-[520px]">
          <DialogHeader>
            <DialogTitle>添加 MCP 连接</DialogTitle>
            <DialogDescription>配置 MCP 服务器连接信息</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>连接名称</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="例如: Jira MCP" />
            </div>
            <div className="space-y-2">
              <Label>连接类型</Label>
              <Select value={form.type} onValueChange={(v) => setForm({ ...form, type: v ?? 'sse' })}>
                <SelectTrigger>
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
                <Input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="http://localhost:8080/sse" />
              </div>
            ) : (
              <>
                <div className="space-y-2">
                  <Label>命令</Label>
                  <Input value={form.command} onChange={(e) => setForm({ ...form, command: e.target.value })} placeholder="例如: npx" />
                </div>
                <div className="space-y-2">
                  <Label>参数（空格分隔）</Label>
                  <Input value={form.args} onChange={(e) => setForm({ ...form, args: e.target.value })} placeholder="例如: -y @modelcontextprotocol/server-filesystem" />
                </div>
              </>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAdd(false)}>取消</Button>
            <Button onClick={handleAdd}>添加</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
