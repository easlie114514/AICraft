import { useState, useEffect, useCallback } from 'react'
import { Plus, Eye, Pencil, Star, Trash2, RefreshCw, User, Users } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Switch } from '@/components/ui/switch'
import { Separator } from '@/components/ui/separator'
import EmotionSlotGrid, { type EmotionKey } from '@/components/EmotionSlotGrid'
import EmotionCropModal from '@/components/EmotionCropModal'
import { api } from '@/lib/api'

interface Role {
  name: string
  content: string
  is_current?: boolean
}

export default function RolePage({ isActive }: { isActive?: boolean }) {
  const [roles, setRoles] = useState<Role[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [showView, setShowView] = useState<Role | null>(null)
  const [showEdit, setShowEdit] = useState<Role | null>(null)
  const [form, setForm] = useState({ name: '', content: '' })
  const [editForm, setEditForm] = useState({ name: '', content: '' })
  // 情绪画像状态
  const [emotionEnabled, setEmotionEnabled] = useState(false)
  const [emotionAvailable, setEmotionAvailable] = useState<string[]>([])
  const [emotionVersion, setEmotionVersion] = useState(0)
  const [showCropModal, setShowCropModal] = useState(false)
  const [cropEmotionKey, setCropEmotionKey] = useState<EmotionKey>('neutral')

  const loadRoles = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.get<Role[]>('/roles')
      setRoles(data)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [])

  const notify = () => window.dispatchEvent(new CustomEvent('roles-changed'))

  useEffect(() => {
    if (isActive) {
      loadRoles()
      notify()
    }
  }, [isActive, loadRoles])

  const handleAdd = async () => {
    if (!form.name.trim()) return
    await api.post('/roles', form)
    setShowAdd(false)
    setForm({ name: '', content: '' })
    loadRoles()
    notify()
  }

  const handleDelete = async (name: string) => {
    await api.delete(`/roles/${encodeURIComponent(name)}`)
    loadRoles()
    notify()
  }

  const handleEdit = async () => {
    if (!editForm.name.trim() || !showEdit) return
    if (editForm.name !== showEdit.name) {
      // Name changed - delete old, create new
      await api.delete(`/roles/${encodeURIComponent(showEdit.name)}`)
      await api.post('/roles', { name: editForm.name, content: editForm.content })
    } else {
      // Only content changed
      await api.put(`/roles/${encodeURIComponent(showEdit.name)}`, { content: editForm.content })
    }
    setShowEdit(null)
    loadRoles()
    notify()
  }

  const handleSetCurrent = async (name: string) => {
    await api.put('/roles/current', { name })
    loadRoles()
    notify()
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden p-6 animate-in fade-in duration-200">
      <div className="shrink-0 flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/15 to-primary/5 ring-1 ring-primary/10 flex items-center justify-center shrink-0">
            <Users className="w-5 h-5 text-primary" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-text-primary">角色管理</h2>
              {!loading && roles.length > 0 && (
                <span className="text-[11px] text-text-tertiary ml-1">
                  <span className="font-medium text-text-secondary">{roles.length}</span> 个角色
                </span>
              )}
            </div>
            <p className="text-xs text-text-tertiary">创建和管理 AI 角色</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => { loadRoles(); notify() }}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button onClick={() => setShowAdd(true)}>
            <Plus className="h-4 w-4 mr-1" />
            创建角色
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        {/* 加载骨架屏 */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pr-1">
            {[1, 2, 3, 4].map((i) => (
              <Card key={i}>
                <CardContent className="px-5 pt-[calc(1.25rem+3px)] pb-1 flex flex-col items-center text-center animate-pulse">
                  <div className="w-16 h-16 rounded-2xl bg-muted/70 mb-3" />
                  <div className="h-4 w-20 bg-muted/70 rounded mb-2" />
                  <div className="h-4 w-12 bg-muted/50 rounded-full mb-3" />
                  <div className="h-3.5 w-full bg-muted/50 rounded" />
                  <div className="h-3.5 w-3/4 bg-muted/50 rounded mt-1.5 mb-4" />
                  <div className="h-8 w-full bg-muted/50 rounded" />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : roles.length === 0 ? (
          /* 空状态 */
          <div className="flex flex-col items-center justify-center h-80 text-center">
            <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-primary/10 to-primary/5 flex items-center justify-center mb-6 ring-1 ring-primary/10">
              <User className="w-10 h-10 text-primary/40" />
            </div>
            <h3 className="text-lg font-medium text-text-primary mb-2">暂无角色</h3>
            <p className="text-sm text-text-secondary max-w-md mb-6">
              创建角色来定义 AI 的行为和个性，每个角色可以设置独立的 System Prompt。
            </p>
            <Button onClick={() => setShowAdd(true)}>
              <Plus className="h-4 w-4 mr-1.5" />
              创建角色
            </Button>
          </div>
        ) : (
          /* 角色卡片网格 */
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pr-1">
            {roles.map((r) => (
              <Card key={r.name} className="relative hover:shadow-card-hover transition-all duration-200 overflow-hidden group">
                {/* 顶部强调色条 */}
                <div className={`absolute top-0 left-0 right-0 h-[3px] bg-gradient-to-r transition-opacity duration-200 ${r.is_current ? 'from-transparent via-primary/45 to-transparent' : 'from-transparent via-muted/30 to-transparent'}`} />

                <CardContent className="px-5 pt-[calc(1.25rem+3px)] pb-1 flex flex-col items-center text-center">
                  {/* 角色头像 */}
                  <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mb-3 transition-all duration-200 ${
                    r.is_current
                      ? 'bg-gradient-to-br from-primary/15 to-primary/5 ring-1 ring-primary/15'
                      : 'bg-muted/50 ring-1 ring-border'
                  }`}>
                    <span className={`text-2xl font-bold transition-colors duration-200 ${r.is_current ? 'text-primary' : 'text-text-disabled'}`}>
                      {r.name[0]}
                    </span>
                  </div>

                  {/* 名称 */}
                  <span className={`font-semibold truncate max-w-full ${r.is_current ? 'text-foreground' : 'text-text-primary'}`}>
                    {r.name}
                  </span>

                  {/* 当前角色标记 */}
                  {r.is_current && (
                    <Badge variant="outline" className="rounded-full text-[11px] px-2 py-0 mt-1.5">当前</Badge>
                  )}
                  {!r.is_current && <div className="mt-1.5" />}

                  {/* 描述 */}
                  <p className="text-sm text-text-secondary line-clamp-2 leading-relaxed mt-2.5 min-h-[2.75rem]">
                    {r.content || '无描述'}
                  </p>

                  {/* 分隔 + 操作按钮 */}
                  <div className="w-full mt-3 pt-3 border-t border-border/60">
                    <div className="flex items-center justify-center gap-1">
                      <Button variant="outline" size="sm" onClick={() => setShowView(r)} title="查看">
                        <Eye className="h-4 w-4 mr-1" />
                        查看
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => {
                        setShowEdit(r)
                        setEditForm({ name: r.name, content: r.content })
                        setEmotionVersion(0)
                        api.get<{ enabled: boolean; available: string[] }>(`/roles/${encodeURIComponent(r.name)}/emotion`)
                          .then((data) => {
                            setEmotionEnabled(data.enabled)
                            setEmotionAvailable(data.available)
                          })
                          .catch(() => {
                            setEmotionEnabled(false)
                            setEmotionAvailable([])
                          })
                      }} title="编辑">
                        <Pencil className="h-4 w-4 mr-1" />
                        编辑
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => handleSetCurrent(r.name)} title="设为当前">
                        <Star className="h-4 w-4 mr-1" />
                        设为当前
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => handleDelete(r.name)} className="text-muted-foreground hover:text-destructive" title="删除">
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
        <DialogContent className="sm:max-w-[520px] max-h-[85vh] flex flex-col overflow-hidden">
          <DialogHeader className="shrink-0">
            <DialogTitle>创建角色</DialogTitle>
            <DialogDescription>定义 AI 的角色和行为</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4 overflow-y-auto flex-1 min-h-0">
            <div className="space-y-2">
              <Label>角色名称</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}  placeholder="例如: 代码助手" />
            </div>
            <div className="space-y-2">
              <Label>角色内容 (System Prompt)</Label>
              <Textarea
                value={form.content}
                onChange={(e) => setForm({ ...form, content: e.target.value })}
                rows={8}
                className="max-h-[300px]"
                placeholder="描述 AI 的角色和行为..."
              />
            </div>
          </div>
          <DialogFooter className="shrink-0">
            <Button variant="outline" onClick={() => setShowAdd(false)} >取消</Button>
            <Button onClick={handleAdd} >创建</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Role Dialog */}
      <Dialog open={!!showView} onOpenChange={() => setShowView(null)}>
        <DialogContent className="sm:max-w-[520px] max-h-[85vh] flex flex-col overflow-hidden">
          <DialogHeader className="shrink-0">
            <DialogTitle>{showView?.name}</DialogTitle>
            <DialogDescription>角色 System Prompt 内容</DialogDescription>
          </DialogHeader>
          <div className="flex-1 min-h-0 overflow-y-auto">
            <pre className="text-sm whitespace-pre-wrap bg-muted p-4 rounded-lg">{showView?.content}</pre>
          </div>
          <DialogFooter className="shrink-0">
            <Button variant="outline" onClick={() => {
              if (showView) {
                setShowEdit(showView)
                setEditForm({ name: showView.name, content: showView.content })
                setShowView(null)
              }
            }}>
              <Pencil className="h-4 w-4 mr-1" />
              编辑
            </Button>
            <Button variant="outline" onClick={() => setShowView(null)} >关闭</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Role Dialog */}
      <Dialog open={!!showEdit} onOpenChange={() => { setShowEdit(null); setEmotionEnabled(false); setEmotionAvailable([]) }}>
        <DialogContent className="sm:max-w-[640px] max-h-[90vh] flex flex-col overflow-hidden">
          <DialogHeader className="shrink-0">
            <DialogTitle>编辑角色</DialogTitle>
            <DialogDescription>修改角色名称和 System Prompt</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4 overflow-y-auto flex-1 min-h-0">
            <div className="space-y-2">
              <Label>角色名称</Label>
              <Input
                value={editForm.name}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                placeholder="角色名称"
              />
            </div>
            <div className="space-y-2">
              <Label>角色内容 (System Prompt)</Label>
              <Textarea
                value={editForm.content}
                onChange={(e) => setEditForm({ ...editForm, content: e.target.value })}
                rows={8}
                className="max-h-[300px]"
                placeholder="描述 AI 的角色和行为..."
              />
            </div>

            {/* ── 情绪画像配置 ── */}
            {showEdit && (
              <>
                <Separator className="my-2" />
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Label>情绪画像</Label>
                    <Switch
                      checked={emotionEnabled}
                      onCheckedChange={async (v) => {
                        setEmotionEnabled(v)
                        await api.put(`/roles/${encodeURIComponent(showEdit.name)}/emotion`, { enabled: v })
                        if (v) {
                          const data = await api.get<{ enabled: boolean; available: string[] }>(`/roles/${encodeURIComponent(showEdit.name)}/emotion`)
                          setEmotionAvailable(data.available)
                        }
                      }}
                    />
                  </div>

                  {emotionEnabled && (
                    <EmotionSlotGrid
                      roleName={showEdit.name}
                      available={emotionAvailable}
                      version={emotionVersion}
                      onSlotClick={(key) => {
                        setCropEmotionKey(key)
                        setShowCropModal(true)
                      }}
                    />
                  )}
                </div>
              </>
            )}
          </div>
          <DialogFooter className="shrink-0">
            <Button variant="outline" onClick={() => setShowEdit(null)} >取消</Button>
            <Button onClick={handleEdit} >保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Emotion Crop Modal */}
      {showEdit && (
        <EmotionCropModal
          open={showCropModal}
          onOpenChange={setShowCropModal}
          roleName={showEdit.name}
          emotionKey={cropEmotionKey}
          onSaved={async () => {
            // 刷新可用列表，同时 bump 版本号破坏浏览器缓存
            const data = await api.get<{ enabled: boolean; available: string[] }>(`/roles/${encodeURIComponent(showEdit.name)}/emotion`)
            setEmotionAvailable(data.available)
            setEmotionEnabled(data.enabled)
            setEmotionVersion(v => v + 1)
          }}
        />
      )}
    </div>
  )
}
