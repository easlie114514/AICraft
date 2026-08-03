import { useState, useEffect, useCallback } from 'react'
import { Plus, Eye, Pencil, Star, Trash2, RefreshCw, User, Users } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Switch } from '@/components/ui/switch'

import EmotionSlotGrid, { type EmotionKey } from '@/components/EmotionSlotGrid'
import EmotionCropModal from '@/components/EmotionCropModal'
import { api } from '@/lib/api'
import { themeCardGradient } from '@/lib/utils'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'

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
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [form, setForm] = useState({ name: '', content: '' })
  const [editForm, setEditForm] = useState({ name: '', content: '' })
  // 情绪画像状态
  const [emotionEnabled, setEmotionEnabled] = useState(false)
  const [emotionAvailable, setEmotionAvailable] = useState<string[]>([])
  const [emotionVersion, setEmotionVersion] = useState(0)
  const [showCropModal, setShowCropModal] = useState(false)
  const [cropEmotionKey, setCropEmotionKey] = useState<EmotionKey>('neutral')
  // 人味设置状态
  const [humanTouchEnabled, setHumanTouchEnabled] = useState(false)
  const [humanTouchLevel, setHumanTouchLevel] = useState(1)

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
    // 创建后保存人味配置
    if (humanTouchEnabled) {
      await api.put(`/roles/${encodeURIComponent(form.name.trim())}/human-touch`, {
        enabled: humanTouchEnabled,
        level: humanTouchLevel,
      }).catch(() => {})
    }
    setShowAdd(false)
    setForm({ name: '', content: '' })
    setHumanTouchEnabled(false)
    setHumanTouchLevel(1)
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
              <Card key={i} className="border-0 text-white" style={themeCardGradient()}>
                <CardContent className="px-5 pt-5 pb-1 flex flex-col items-center text-center animate-pulse">
                  <div className="w-16 h-16 rounded-2xl bg-white/10 mb-3" />
                  <div className="h-4 w-20 bg-white/15 rounded mb-2" />
                  <div className="h-3 w-12 bg-white/10 rounded-full mb-3" />
                  <div className="h-3.5 w-full bg-white/10 rounded" />
                  <div className="h-3.5 w-3/4 bg-white/10 rounded mt-1.5 mb-4" />
                  <div className="h-8 w-full bg-white/10 rounded" />
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
              <Card key={r.name} className="relative overflow-hidden group border-0 text-white" style={themeCardGradient()}>
                {/* 首字母丝印 */}
                <div className="absolute -bottom-3 -right-4 text-[130px] font-black text-white/[0.05] leading-none select-none pointer-events-none">
                  {(r.name.trim()[0]?.toUpperCase() || '?')}
                </div>

                <CardContent className="px-5 pt-5 pb-1 flex flex-col items-center text-center relative z-10">
                  {/* 角色头像 */}
                  <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mb-3 transition-all duration-200 ${
                    r.is_current
                      ? 'bg-white/15 ring-1 ring-white/25'
                      : 'bg-white/8 ring-1 ring-white/10'
                  }`}>
                    <span className={`text-2xl font-bold transition-colors duration-200 ${r.is_current ? 'text-white' : 'text-white/60'}`}>
                      {r.name[0]}
                    </span>
                  </div>

                  {/* 名称 */}
                  <span className="font-semibold truncate max-w-full text-white/95">
                    {r.name}
                  </span>

                  {/* 当前角色标记 */}
                  {r.is_current && (
                    <span className="text-[10px] bg-white/18 backdrop-blur-sm px-1.5 py-0.5 rounded-md text-white/80 mt-1.5">当前</span>
                  )}
                  {!r.is_current && <div className="mt-1.5" />}

                  {/* 描述 */}
                  <p className="text-sm text-white/55 line-clamp-2 leading-relaxed mt-2.5 min-h-[2.75rem]">
                    {r.content || '无描述'}
                  </p>

                  {/* 分隔 + 操作按钮 */}
                  <div className="w-full mt-3 pt-3 border-t border-white/8">
                    <div className="flex items-center justify-center gap-1">
                      <Button variant="ghost" size="sm" onClick={() => setShowView(r)} className="text-white/60 hover:text-white hover:bg-white/8 text-xs">
                        <Eye className="h-4 w-4 mr-1" />
                        查看
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => {
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
                        api.get<{ enabled: boolean; level: number }>(`/roles/${encodeURIComponent(r.name)}/human-touch`)
                          .then((data) => {
                            setHumanTouchEnabled(data.enabled)
                            setHumanTouchLevel(data.level)
                          })
                          .catch(() => {
                            setHumanTouchEnabled(false)
                            setHumanTouchLevel(1)
                          })
                      }} className="text-white/60 hover:text-white hover:bg-white/8 text-xs">
                        <Pencil className="h-4 w-4 mr-1" />
                        编辑
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleSetCurrent(r.name)} className="text-white/60 hover:text-white hover:bg-white/8 text-xs">
                        <Star className="h-4 w-4 mr-1" />
                        设为当前
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => setDeleteTarget(r.name)} className="text-white/25 hover:text-red-200/80 hover:bg-white/8" title="删除">
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
          <DialogHeader className="shrink-0" icon={User}>
            <DialogTitle>创建角色</DialogTitle>
            <DialogDescription>定义 AI 的角色和行为</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-4 overflow-y-auto overflow-x-hidden flex-1 min-h-0">
            {/* ── 基本信息 ── */}
            <div className="rounded-xl border border-border/50 bg-muted/20 p-4 space-y-3">
              <div className="space-y-1.5">
                <Label className="text-xs text-text-secondary">角色名称</Label>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/15 to-primary/5 ring-1 ring-primary/10 flex items-center justify-center shrink-0">
                    <span className="text-lg font-bold text-primary">
                      {form.name.trim() ? form.name.trim()[0].toUpperCase() : '?'}
                    </span>
                  </div>
                  <Input
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="例如: 代码助手"
                    className="flex-1 bg-card"
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs text-text-secondary">角色内容 (System Prompt)</Label>
                <Textarea
                  value={form.content}
                  onChange={(e) => setForm({ ...form, content: e.target.value })}
                  rows={8}
                  className="max-h-[300px] bg-card"
                  placeholder="描述 AI 的角色和行为..."
                />
                <p className="text-[11px] text-text-tertiary text-right">{form.content.length} 字符</p>
              </div>
            </div>

            {/* ── 人味（Human Touch）设定 ── */}
            <div className="rounded-xl border border-border/50 bg-muted/20 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium text-text-primary">人味设定</span>
                  <p className="text-xs text-text-tertiary mt-0.5">让对话更自然，像和真人聊天</p>
                </div>
                <Switch
                  checked={humanTouchEnabled}
                  onCheckedChange={(v) => setHumanTouchEnabled(v)}
                />
              </div>
              {humanTouchEnabled && (
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { lvl: 1, emoji: '💬', title: '轻度口语化', desc: '自然口语表达' },
                    { lvl: 2, emoji: '😄', title: '适度情绪化', desc: '带情绪和主见' },
                    { lvl: 3, emoji: '🤪', title: '完全拟人', desc: '有脾气能接梗' },
                  ].map((item) => (
                    <button
                      key={item.lvl}
                      type="button"
                      onClick={() => setHumanTouchLevel(item.lvl)}
                      className={`px-3 py-2.5 rounded-lg border text-left transition-colors ${
                        humanTouchLevel === item.lvl
                          ? 'border-primary bg-primary/10 text-primary ring-1 ring-primary/20'
                          : 'border-border bg-card text-text-secondary hover:border-primary/30 hover:bg-muted/50'
                      }`}
                    >
                      <div className="text-xs font-medium">{item.emoji} {item.title}</div>
                      <div className="text-[10px] opacity-55 mt-0.5">{item.desc}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          <DialogFooter className="shrink-0">
            <Button variant="outline" onClick={() => { setShowAdd(false); setHumanTouchEnabled(false); setHumanTouchLevel(1) }} >取消</Button>
            <Button onClick={handleAdd} >创建角色</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Role Dialog */}
      <Dialog open={!!showView} onOpenChange={() => setShowView(null)}>
        <DialogContent className="sm:max-w-[520px] max-h-[85vh] flex flex-col overflow-hidden">
          <DialogHeader className="shrink-0" icon={Eye}>
            <DialogTitle>{showView?.name}</DialogTitle>
            <DialogDescription>角色 System Prompt 内容</DialogDescription>
          </DialogHeader>
          <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden py-2">
            <div className="rounded-xl border border-border/50 bg-muted/30 p-4">
              <pre className="text-sm whitespace-pre-wrap leading-relaxed text-text-secondary">{showView?.content || '(空)'}</pre>
            </div>
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
      <Dialog open={!!showEdit} onOpenChange={() => { setShowEdit(null); setEmotionEnabled(false); setEmotionAvailable([]); setHumanTouchEnabled(false); setHumanTouchLevel(1) }}>
        <DialogContent className="sm:max-w-[1000px] max-h-[90vh] flex flex-col overflow-hidden">
          <DialogHeader className="shrink-0" icon={Pencil}>
            <DialogTitle>编辑角色</DialogTitle>
            <DialogDescription>修改角色名称和 System Prompt</DialogDescription>
          </DialogHeader>
          <div className="flex-1 min-h-0 relative">
            {/* ── 右列：配置面板（在文档流中，决定容器高度）── */}
            <div className="ml-[58%] w-[42%] py-4 space-y-3">
              {/* ── 情绪画像配置 ── */}
              {showEdit && (
                <div className="rounded-xl border border-border/50 bg-muted/20 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-sm font-medium text-text-primary">情绪画像</span>
                      <p className="text-xs text-text-tertiary mt-0.5">像素风情绪头像</p>
                    </div>
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
                  <EmotionSlotGrid
                    roleName={showEdit.name}
                    available={emotionAvailable}
                    version={emotionVersion}
                    onSlotClick={(key) => {
                      setCropEmotionKey(key)
                      setShowCropModal(true)
                    }}
                  />
                </div>
              )}

              {/* ── 人味（Human Touch）设定 ── */}
              {showEdit && (
                <div className="rounded-xl border border-border/50 bg-muted/20 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-sm font-medium text-text-primary">人味设定</span>
                      <p className="text-xs text-text-tertiary mt-0.5">表达方式控制</p>
                    </div>
                    <Switch
                      checked={humanTouchEnabled}
                      onCheckedChange={async (v) => {
                        setHumanTouchEnabled(v)
                        await api.put(`/roles/${encodeURIComponent(showEdit.name)}/human-touch`, {
                          enabled: v,
                          level: v ? humanTouchLevel : 1,
                        })
                      }}
                    />
                  </div>
                  {humanTouchEnabled && (
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { lvl: 1, emoji: '💬', title: '轻度口语化', desc: '自然口语表达' },
                        { lvl: 2, emoji: '😄', title: '适度情绪化', desc: '带情绪和主见' },
                        { lvl: 3, emoji: '🤪', title: '完全拟人', desc: '有脾气能接梗' },
                      ].map((item) => (
                        <button
                          key={item.lvl}
                          type="button"
                          onClick={async () => {
                            setHumanTouchLevel(item.lvl)
                            await api.put(`/roles/${encodeURIComponent(showEdit.name)}/human-touch`, {
                              enabled: true,
                              level: item.lvl,
                            })
                          }}
                          className={`px-3 py-2.5 rounded-lg border text-left transition-colors ${
                            humanTouchLevel === item.lvl
                              ? 'border-primary bg-primary/10 text-primary ring-1 ring-primary/20'
                              : 'border-border bg-card text-text-secondary hover:border-primary/30 hover:bg-muted/50'
                          }`}
                        >
                          <div className="text-xs font-medium">{item.emoji} {item.title}</div>
                          <div className="text-[10px] opacity-55 mt-0.5">{item.desc}</div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* ── 左列：基本信息（absolute 定位，高度由右列决定）── */}
            <div className="absolute inset-y-0 left-0 w-[58%] overflow-y-auto py-4 pr-2">
              <div className="rounded-xl border border-border/50 bg-muted/20 p-4 flex flex-col h-full">
                <div className="space-y-1.5 shrink-0">
                  <Label className="text-xs text-text-secondary">角色名称</Label>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/15 to-primary/5 ring-1 ring-primary/10 flex items-center justify-center shrink-0">
                      <span className="text-lg font-bold text-primary">
                        {editForm.name.trim() ? editForm.name.trim()[0].toUpperCase() : '?'}
                      </span>
                    </div>
                    <Input
                      value={editForm.name}
                      onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                      placeholder="角色名称"
                      className="flex-1 bg-card"
                    />
                  </div>
                </div>
                <div className="flex-1 flex flex-col min-h-0 space-y-1.5 mt-3">
                  <Label className="text-xs text-text-secondary shrink-0">角色内容 (System Prompt)</Label>
                  <Textarea
                    value={editForm.content}
                    onChange={(e) => setEditForm({ ...editForm, content: e.target.value })}
                    className="flex-1 min-h-[120px] bg-card"
                    placeholder="描述 AI 的角色和行为..."
                  />
                  <p className="text-[11px] text-text-tertiary text-right shrink-0">{editForm.content.length} 字符</p>
                </div>
              </div>
            </div>
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

      {/* ── 删除确认 ── */}
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}
        title="删除角色"
        description={`确定要删除角色 ${deleteTarget} 吗？此操作不可撤销。`}
        onConfirm={async () => {
          if (deleteTarget) await handleDelete(deleteTarget)
          setDeleteTarget(null)
        }}
      />
    </div>
  )
}
