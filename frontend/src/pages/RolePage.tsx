import { useState, useEffect, useCallback } from 'react'
import { Plus, Eye, Star, Trash2, RefreshCw, User } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { api } from '@/lib/api'

interface Role {
  name: string
  content: string
  is_current?: boolean
}

export default function RolePage() {
  const [roles, setRoles] = useState<Role[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [showView, setShowView] = useState<Role | null>(null)
  const [form, setForm] = useState({ name: '', content: '' })

  const loadRoles = useCallback(async () => {
    try {
      const data = await api.get<Role[]>('/roles')
      setRoles(data)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadRoles() }, [loadRoles])

  const handleAdd = async () => {
    if (!form.name.trim()) return
    await api.post('/roles', form)
    setShowAdd(false)
    setForm({ name: '', content: '' })
    loadRoles()
  }

  const handleDelete = async (name: string) => {
    await api.delete(`/roles/${encodeURIComponent(name)}`)
    loadRoles()
  }

  const handleSetCurrent = async (name: string) => {
    await api.put('/roles/current', { name })
    loadRoles()
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden p-6">
      <div className="shrink-0 flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-text-primary">角色管理</h2>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={loadRoles}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button onClick={() => setShowAdd(true)}>
            <Plus className="h-4 w-4 mr-1" />
            创建角色
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        {roles.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
            <User className="w-16 h-16 text-text-disabled mb-4" />
            <p className="text-sm text-text-secondary">暂无角色</p>
          </div>
        ) : (
          <div className="grid gap-4 pr-1">
            {roles.map((r) => (
              <Card key={r.name} className="hover:shadow-card-hover transition-shadow duration-200">
                <CardContent className="p-4">
                  <div className="flex items-center gap-4">
                    <Avatar className="h-10 w-10 shrink-0 rounded-full bg-primary/15">
                      <AvatarFallback className="bg-transparent text-primary text-sm font-medium">
                        {r.name[0]}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{r.name}</span>
                        {r.is_current && <Badge className="rounded-lg">当前</Badge>}
                      </div>
                      <p className="text-sm text-text-secondary truncate mt-0.5">
                        {r.content.slice(0, 80)}{r.content.length > 80 ? '...' : ''}
                      </p>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Button variant="outline" size="sm" onClick={() => setShowView(r)} >
                        <Eye className="h-4 w-4 mr-1" />
                        查看
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => handleSetCurrent(r.name)} >
                        <Star className="h-4 w-4 mr-1" />
                        设为当前
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => handleDelete(r.name)} className="text-muted-foreground hover:text-destructive">
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

      {/* Add Role Dialog */}
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent className="sm:max-w-[520px]">
          <DialogHeader>
            <DialogTitle>创建角色</DialogTitle>
            <DialogDescription>定义 AI 的角色和行为</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>角色名称</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}  placeholder="例如: 代码助手" />
            </div>
            <div className="space-y-2">
              <Label>角色内容 (System Prompt)</Label>
              <Textarea value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} rows={8}  placeholder="描述 AI 的角色和行为..." />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAdd(false)} >取消</Button>
            <Button onClick={handleAdd} >创建</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Role Dialog */}
      <Dialog open={!!showView} onOpenChange={() => setShowView(null)}>
        <DialogContent className="sm:max-w-[520px]">
          <DialogHeader>
            <DialogTitle>{showView?.name}</DialogTitle>
            <DialogDescription>角色 System Prompt 内容</DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[300px]">
            <pre className="text-sm whitespace-pre-wrap bg-muted p-4 rounded-lg">{showView?.content}</pre>
          </ScrollArea>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowView(null)} >关闭</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
