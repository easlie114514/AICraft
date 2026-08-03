"use client"

import { useState, useEffect, useCallback } from 'react'
import { FolderOpen, Plus, Trash2, Edit3, Check, X, Settings } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Popover, PopoverTrigger, PopoverContent, PopoverHeader, PopoverTitle } from '@/components/ui/popover'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'

export interface ProjectItem {
  id: string
  name: string
  content: string
  created_at: string
  updated_at: string
}

interface Props {
  enabled: boolean
  onToggle: (v: boolean) => void
}

export default function ProjectContextPopover({ enabled, onToggle }: Props) {
  const [open, setOpen] = useState(false)
  const [projects, setProjects] = useState<ProjectItem[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)

  // 编辑状态
  const [editing, setEditing] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)  // null = 新建
  const [editName, setEditName] = useState('')
  const [editContent, setEditContent] = useState('')
  const [saving, setSaving] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<ProjectItem | null>(null)

  // 加载项目列表
  const loadProjects = useCallback(() => {
    api.get<{ active_id: string | null; projects: ProjectItem[] }>('/projects')
      .then((data) => {
        setProjects(data.projects || [])
        setActiveId(data.active_id)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (open) loadProjects()
  }, [open, loadProjects])

  // 激活项目
  const handleActivate = async (id: string) => {
    await api.put(`/projects/${encodeURIComponent(id)}/activate`)
    setActiveId(id)
    if (!enabled) onToggle(true)
  }

  // 删除项目
  const handleDelete = async (id: string) => {
    await api.delete(`/projects/${encodeURIComponent(id)}`)
    if (activeId === id) setActiveId(null)
    loadProjects()
  }

  // 开始新建
  const handleNew = () => {
    setEditId(null)
    setEditName('')
    setEditContent('')
    setEditing(true)
  }

  // 开始编辑
  const handleEdit = (p: ProjectItem) => {
    setEditId(p.id)
    setEditName(p.name)
    setEditContent(p.content)
    setEditing(true)
  }

  // 取消编辑
  const handleCancelEdit = () => {
    setEditing(false)
    setEditId(null)
    setEditName('')
    setEditContent('')
  }

  // 保存
  const handleSave = async () => {
    if (!editName.trim()) return
    setSaving(true)
    try {
      const body: { id?: string; name: string; content: string } = {
        name: editName.trim(),
        content: editContent,
      }
      if (editId) body.id = editId
      const res = await api.post<{ ok: boolean; id: string }>('/projects', body)
      if (res.ok) {
        // 新建后自动激活
        if (!editId) {
          await api.put(`/projects/${encodeURIComponent(res.id)}/activate`)
          setActiveId(res.id)
          if (!enabled) onToggle(true)
        } else if (activeId === editId) {
          // 编辑的是当前活跃项目，刷新以更新内容
          // 内容已通过 API 保存，下次对话会读取最新
        }
        setEditing(false)
        loadProjects()
      }
    } catch {
      // 静默处理
    } finally {
      setSaving(false)
    }
  }

  const activeProject = projects.find((p) => p.id === activeId)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className={cn(
          'inline-flex items-center rounded-lg h-8 text-xs border border-border bg-background hover:bg-muted px-3 py-0 transition-colors',
          enabled && activeId && 'border-primary/50 bg-primary/10 text-primary ring-1 ring-primary/20'
        )}
      >
        {activeProject ? activeProject.name : '项目提示词注入'}
      </PopoverTrigger>

      <PopoverContent className="w-80" align="center" sideOffset={8}>
        <PopoverHeader>
          <PopoverTitle className="flex items-center gap-2">
            <FolderOpen className="h-4 w-4" />
            项目上下文
          </PopoverTitle>
        </PopoverHeader>

        {/* ── 启用开关 ── */}
        <div className="flex items-center justify-between bg-muted/50 rounded-lg px-3 py-2">
          <div>
            <Label className="text-xs font-medium">启用注入</Label>
            <p className="text-[10px] text-muted-foreground">
              {enabled ? '对话时注入项目背景' : '关闭后不注入项目信息'}
            </p>
          </div>
          <Switch checked={enabled} onCheckedChange={onToggle} />
        </div>

        {/* ── 编辑模式 ── */}
        {editing ? (
          <div className="space-y-2">
            <Input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              placeholder="项目名称"
              className="h-8 text-sm"
              autoFocus
              maxLength={100}
            />
            <Textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              placeholder="项目描述、工作重点、偏好等..."
              className="min-h-[120px] text-xs resize-y"
              maxLength={5000}
            />
            <div className="flex gap-2 justify-end">
              <Button variant="outline" size="sm" onClick={handleCancelEdit} className="h-7 text-xs">
                <X className="h-3 w-3 mr-1" />取消
              </Button>
              <Button
                size="sm"
                onClick={handleSave}
                disabled={!editName.trim() || saving}
                className="h-7 text-xs"
              >
                <Check className="h-3 w-3 mr-1" />
                {saving ? '保存中...' : '保存'}
              </Button>
            </div>
          </div>
        ) : (
          <>
            {/* ── 项目列表 ── */}
            {projects.length > 0 && (
              <div className="space-y-1 max-h-[200px] overflow-y-auto">
                {projects.map((p) => {
                  const isActive = p.id === activeId
                  return (
                    <div
                      key={p.id}
                      className={cn(
                        'flex items-center gap-1.5 rounded-lg px-2 py-1.5 group transition-colors',
                        isActive
                          ? 'bg-primary/10 border border-primary/20'
                          : 'hover:bg-muted/50 border border-transparent'
                      )}
                    >
                      {/* 激活按钮（名称区域） */}
                      <button
                        onClick={() => handleActivate(p.id)}
                        className={cn(
                          'flex-1 text-left text-xs truncate',
                          isActive ? 'font-medium text-primary' : 'text-text-secondary'
                        )}
                        title={p.name}
                      >
                        {p.name}
                      </button>

                      {/* 操作按钮 */}
                      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 text-muted-foreground hover:text-foreground"
                          onClick={() => handleEdit(p)}
                          title="编辑"
                        >
                          <Edit3 className="h-3 w-3" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 text-muted-foreground hover:text-destructive"
                          onClick={() => setDeleteTarget(p)}
                          title="删除"
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {/* ── 空状态 ── */}
            {projects.length === 0 && (
              <div className="text-center py-3">
                <Settings className="h-6 w-6 mx-auto text-muted-foreground/40 mb-1" />
                <p className="text-xs text-muted-foreground">暂无项目</p>
                <p className="text-[10px] text-muted-foreground/60 mt-0.5">
                  创建项目以注入背景信息
                </p>
              </div>
            )}

            {/* ── 新建按钮 ── */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleNew}
              className="w-full h-8 text-xs"
            >
              <Plus className="h-3.5 w-3.5 mr-1" />
              新建项目
            </Button>
          </>
        )}
      </PopoverContent>

      {/* ── 删除确认 ── */}
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}
        title="删除项目上下文"
        description={`确定要删除项目 ${deleteTarget?.name} 吗？此操作不可撤销。`}
        onConfirm={async () => {
          if (deleteTarget) await handleDelete(deleteTarget.id)
          setDeleteTarget(null)
        }}
      />
    </Popover>
  )
}
