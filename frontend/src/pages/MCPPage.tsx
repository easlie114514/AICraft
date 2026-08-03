import { useState, useEffect, useCallback } from 'react'
import { Plus, Trash2, Zap, ChevronDown, RefreshCw, Shield, Lock, CheckCircle2, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { api } from '@/lib/api'
import { themeCardGradient } from '@/lib/utils'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'

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
  auto_grant: boolean
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
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [envStatus, setEnvStatus] = useState<{ available: boolean; path: string | null; version: string | null } | null>(null)
  const [permConfig, setPermConfig] = useState<PermissionConfig | null>(null)
  const [newTrustedPath, setNewTrustedPath] = useState('')
  const [newDeniedPath, setNewDeniedPath] = useState('')
  const [form, setForm] = useState({
    name: '', type: 'sse', host: '', port: '', url: '', command: '', args: '',
  })

  const loadConnections = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.get<MCPConnection[]>('/mcp')
      setConnections(data)
    } catch { /* ignore */ }
    finally { setLoading(false) }
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

  const handleToggleApproval = async (name: string, auto_grant: boolean) => {
    await api.put(`/mcp/${encodeURIComponent(name)}/toggle-approval`, { auto_grant })
    loadConnections()
  }

  const handleDelete = async (name: string) => {
    await api.delete(`/mcp/${encodeURIComponent(name)}`)
    loadConnections()
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden p-6 animate-in fade-in duration-200">
      <div className="shrink-0 flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/15 to-primary/5 ring-1 ring-primary/10 flex items-center justify-center shrink-0">
            <Zap className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-text-primary">MCP 连接</h2>
            <p className="text-xs text-text-tertiary">管理 MCP 服务器连接与工具权限</p>
          </div>
        </div>
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
        {loading ? (
          <div className="grid gap-4 pr-1">
            {[1, 2].map((i) => (
              <Card key={i} className="border-0 text-white" style={themeCardGradient()}>
                <CardContent className="p-4">
                  <div className="flex items-start gap-4 animate-pulse">
                    <div className="h-10 w-10 rounded-full bg-white/10 shrink-0" />
                    <div className="flex-1 space-y-2.5 py-0.5">
                      <div className="flex items-center gap-2">
                        <div className="h-4 w-20 bg-white/15 rounded" />
                        <div className="h-4 w-10 bg-white/10 rounded-lg" />
                        <div className="h-4 w-12 bg-white/10 rounded-lg" />
                      </div>
                      <div className="h-3 w-48 bg-white/10 rounded font-mono" />
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <div className="h-5 w-10 bg-white/15 rounded-full" />
                      <div className="h-5 w-10 bg-white/15 rounded-full" />
                      <div className="h-8 w-8 bg-white/10 rounded" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : connections.length === 0 ? (
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
                <Card key={conn.name} className={`relative overflow-hidden group text-white transition-colors duration-300 ${conn.enabled ? 'border-0' : 'border border-white/5'}`} style={themeCardGradient(conn.enabled)}>
                  {/* 首字母丝印 */}
                  <div className={`absolute -bottom-3 -right-4 text-[130px] font-black leading-none select-none pointer-events-none transition-opacity duration-300 ${conn.enabled ? 'text-white/[0.05]' : 'text-white/[0.02]'}`}>
                    {(conn.name.trim()[0]?.toUpperCase() || 'M')}
                  </div>

                  <CardContent className="p-4 relative z-10">
                    <div className="flex items-start gap-4">
                      <div className={`w-10 h-10 shrink-0 rounded-full flex items-center justify-center transition-colors duration-300 ${
                        conn.enabled ? 'bg-white/12 backdrop-blur-sm ring-1 ring-white/10' : 'bg-white/5 ring-1 ring-white/5'
                      }`}>
                        <Zap className={`h-5 w-5 transition-colors duration-300 ${conn.enabled ? 'text-white/80' : 'text-white/30'}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`font-medium transition-colors duration-300 ${conn.enabled ? 'text-white/95' : 'text-white/50'}`}>{conn.name}</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-md transition-colors duration-300 ${conn.enabled ? 'bg-white/12 backdrop-blur-sm text-white/70' : 'bg-white/5 text-white/35'}`}>{conn.type.toUpperCase()}</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-md transition-colors duration-300 ${
                            conn.status === 'connected' ? 'bg-emerald-400/15 text-emerald-200/90' : conn.status === 'error' ? 'bg-red-400/15 text-red-200/90' : conn.enabled ? 'bg-white/8 text-white/50' : 'bg-white/5 text-white/30'
                          }`}>{status.label}</span>
                          {envStatus && FACTORY_MCP_NAMES.includes(conn.name) && (
                            envStatus.available ? (
                              <span className="text-[10px] bg-emerald-400/15 text-emerald-200/90 px-1.5 py-0.5 rounded-md">
                                <CheckCircle2 className="h-3 w-3 mr-0.5 inline" />
                                环境就绪
                              </span>
                            ) : (
                              <a href="https://nodejs.org/" target="_blank" rel="noopener noreferrer">
                                <span className="text-[10px] bg-red-400/15 text-red-200/90 px-1.5 py-0.5 rounded-md cursor-pointer">
                                  <AlertTriangle className="h-3 w-3 mr-0.5 inline" />
                                  需要Node.js
                                </span>
                              </a>
                            )
                          )}
                        </div>
                        <p className={`text-sm font-mono mt-0.5 truncate transition-colors duration-300 ${conn.enabled ? 'text-white/50' : 'text-white/25'}`}>
                          {conn.type === 'sse' ? conn.display_url : conn.command}
                        </p>
                        {conn.error_msg && (
                          <p className={`text-xs mt-1 truncate transition-colors duration-300 ${conn.enabled ? 'text-red-200/80' : 'text-red-300/50'}`}>{conn.error_msg}</p>
                        )}
                      </div>
                      <div className="flex items-start gap-3 shrink-0">
                        <div className="flex flex-col gap-2">
                          <div className="flex flex-col items-center gap-0.5">
                            <Switch checked={conn.enabled} onCheckedChange={(v) => handleToggle(conn.name, v)} />
                            <span className={`text-[10px] leading-none transition-colors duration-300 ${conn.enabled ? 'text-white/40' : 'text-white/20'}`}>启用</span>
                          </div>
                          <div className="flex flex-col items-center gap-0.5">
                            <Switch
                              checked={conn.auto_grant}
                              onCheckedChange={(v) => handleToggleApproval(conn.name, v)}
                              disabled={!conn.enabled}
                            />
                            <span className={`text-[10px] leading-none transition-colors duration-300 ${conn.enabled ? 'text-white/40' : 'text-white/20'}`}>自动授权</span>
                          </div>
                        </div>
                        <Button variant="ghost" size="icon" onClick={() => setDeleteTarget(conn.name)} className={`transition-colors duration-300 ${conn.enabled ? 'text-white/25 hover:text-red-200/80 hover:bg-white/8' : 'text-white/15 hover:text-red-200/60 hover:bg-white/5'}`}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    {conn.tools.length > 0 && (
                      <Collapsible className="mt-3">
                        <CollapsibleTrigger>
                          <Button variant="ghost" size="sm" className={`text-xs -ml-2 transition-colors duration-300 ${conn.enabled ? 'text-white/45 hover:text-white/70 hover:bg-white/8' : 'text-white/25 hover:text-white/40 hover:bg-white/5'}`}>
                            <span className={`text-[10px] px-1.5 py-0.5 rounded-md mr-2 transition-colors duration-300 ${conn.enabled ? 'bg-white/10' : 'bg-white/5'}`}>{conn.tools.length} 个工具</span>
                            <ChevronDown className="h-3 w-3" />
                          </Button>
                        </CollapsibleTrigger>
                        <CollapsibleContent>
                          <div className="mt-2 space-y-1 pl-2">
                            {conn.tools.map((t) => (
                              <div key={t.name} className={`text-xs transition-colors duration-300 ${conn.enabled ? 'text-white/55' : 'text-white/30'}`}>
                                <span className={`font-mono font-medium transition-colors duration-300 ${conn.enabled ? 'text-white/80' : 'text-white/40'}`}>{t.name}</span>
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
                          className="h-5 w-5 text-muted-foreground hover:text-destructive shrink-0"
                          onClick={() => {
                            const updated = { ...permConfig, trusted_paths: permConfig.trusted_paths.filter((x) => x !== p) }
                            savePermissions(updated)
                          }}
                        >
                          <Trash2 className="h-3 w-3" />
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
                      maxLength={500}
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
                          className="h-5 w-5 text-muted-foreground hover:text-destructive shrink-0"
                          onClick={() => {
                            const updated = { ...permConfig, denied_paths: permConfig.denied_paths.filter((x) => x !== p) }
                            savePermissions(updated)
                          }}
                        >
                          <Trash2 className="h-3 w-3" />
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
                      maxLength={500}
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
          <DialogHeader icon={Shield}>
            <DialogTitle>添加 MCP 连接</DialogTitle>
            <DialogDescription>配置 MCP 服务器连接信息</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-4">
            <div className="rounded-xl border border-border/50 bg-muted/20 p-4 space-y-3">
              <div className="space-y-1.5">
                <Label className="text-xs text-text-secondary">连接名称 <span className="text-red-500">*</span></Label>
                <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="例如: Jira MCP" maxLength={100} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs text-text-secondary">连接类型</Label>
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
                <div className="space-y-1.5">
                  <Label className="text-xs text-text-secondary">URL</Label>
                  <Input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="http://localhost:8080/sse" maxLength={500} />
                </div>
              ) : (
                <>
                  <div className="space-y-1.5">
                    <Label className="text-xs text-text-secondary">命令</Label>
                    <Input value={form.command} onChange={(e) => setForm({ ...form, command: e.target.value })} placeholder="例如: npx" maxLength={200} />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs text-text-secondary">参数（空格分隔）</Label>
                    <Input value={form.args} onChange={(e) => setForm({ ...form, args: e.target.value })} placeholder="例如: -y @modelcontextprotocol/server-filesystem" maxLength={500} />
                  </div>
                </>
              )}
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
        title="删除 MCP 服务器"
        description={`确定要删除 MCP 服务器 ${deleteTarget} 吗？此操作不可撤销。`}
        onConfirm={async () => {
          if (deleteTarget) await handleDelete(deleteTarget)
          setDeleteTarget(null)
        }}
      />
    </div>
  )
}
