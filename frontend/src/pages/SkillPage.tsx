import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, FolderOpen, Zap, FileText, Puzzle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { ScrollArea } from '@/components/ui/scroll-area'
import { InputGroup, InputGroupInput, InputGroupAddon, InputGroupButton } from '@/components/ui/input-group'
import { api } from '@/lib/api'
import { getSkillIcon, getSkillCategory } from './skill-icons'

interface Skill {
  name: string
  description: string
  enabled: boolean
  path: string
}

export default function SkillPage() {
  const [skills, setSkills] = useState<Skill[]>([])
  const [skillDir, setSkillDir] = useState('')
  const [dirInput, setDirInput] = useState('')
  const [loading, setLoading] = useState(true)

  const loadSkills = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.get<Skill[]>('/skills')
      setSkills(data)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [])

  const loadDir = useCallback(async () => {
    try {
      const data = await api.get<{ path: string }>('/skills/dir')
      setSkillDir(data.path)
      setDirInput(data.path)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadSkills(); loadDir() }, [loadSkills, loadDir])

  const handleToggle = async (name: string, enabled: boolean) => {
    await api.put(`/skills/${encodeURIComponent(name)}/toggle`, { enabled })
    loadSkills()
  }

  const handleOpenDir = async () => {
    try {
      const res = await api.get<{ ok: boolean; detail?: string }>('/skills/open-dir')
      if (!res.ok) {
        alert(res.detail || '打开目录失败')
      }
    } catch (e: any) {
      alert(e?.message || '打开目录失败')
    }
  }

  const enabledCount = skills.filter(s => s.enabled).length

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden p-6 animate-in fade-in duration-200">
      <div className="shrink-0 flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/15 to-primary/5 ring-1 ring-primary/10 flex items-center justify-center shrink-0">
            <Puzzle className="w-5 h-5 text-primary" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-text-primary">Skill 管理</h2>
              {!loading && skills.length > 0 && (
                <span className="inline-flex items-center gap-1.5 text-[11px] text-text-tertiary ml-1">
                  <span className="flex gap-0.5">
                    {skills.map((s, i) => (
                      <span key={i} className={`inline-block w-1.5 h-1.5 rounded-full ${s.enabled ? 'bg-primary/70' : 'bg-muted-foreground/25'}`} />
                    ))}
                  </span>
                  <span className="font-medium text-text-secondary">{enabledCount}/{skills.length}</span>
                  <span className="text-text-tertiary/70">已启用</span>
                </span>
              )}
            </div>
            <p className="text-xs text-text-tertiary">配置和启用 AI 技能模块</p>
          </div>
        </div>
        <Button variant="outline" size="icon" onClick={() => { loadSkills(); loadDir() }}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {/* 根目录设置 */}
      <div className="shrink-0 flex items-center gap-2 mb-4">
        <InputGroup className="flex-1 rounded-lg">
          <InputGroupInput
            value={dirInput}
            readOnly
            placeholder="Skills 目录路径"
            className="font-mono text-sm bg-card cursor-default"
          />
          <InputGroupAddon align="inline-end">
            <InputGroupButton onClick={handleOpenDir} title="在资源管理器中打开 Skills 文件夹" size="icon-sm">
              <FolderOpen className="h-4 w-4" />
            </InputGroupButton>
          </InputGroupAddon>
        </InputGroup>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        {/* 加载骨架屏 */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 pr-1">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <Card key={i}>
                <CardContent className="p-5 pt-6 flex flex-col items-center text-center animate-pulse">
                  <div className="w-16 h-16 rounded-2xl bg-muted/70 mb-3" />
                  <div className="h-4 w-20 bg-muted/70 rounded mb-2" />
                  <div className="h-4 w-12 bg-muted/50 rounded-full mb-3" />
                  <div className="h-3.5 w-full bg-muted/50 rounded" />
                  <div className="h-3.5 w-3/4 bg-muted/50 rounded mt-1.5 mb-4" />
                  <div className="h-5 w-16 bg-muted/70 rounded-full" />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : skills.length === 0 ? (
          /* 空状态 */
          <div className="flex flex-col items-center justify-center h-80 text-center">
            <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-primary/10 to-primary/5 flex items-center justify-center mb-6 ring-1 ring-primary/10">
              <Zap className="w-10 h-10 text-primary/40" />
            </div>
            <h3 className="text-lg font-medium text-text-primary mb-2">暂无 Skill</h3>
            <p className="text-sm text-text-secondary max-w-md mb-6">
              将技能文件夹放入 Skills 目录后，点击刷新即可加载。每个技能文件夹需包含 SKILL.md 文件。
            </p>
            <Button onClick={handleOpenDir} variant="outline">
              <FolderOpen className="h-4 w-4 mr-1.5" />
              打开 Skills 目录
            </Button>
          </div>
        ) : (
          /* 技能卡片网格 */
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 pr-1">
            {skills.map((s) => {
              const SkillIcon = getSkillIcon(s.name)
              const category = getSkillCategory(s.name)
              return (
                <Card key={s.name} className="relative hover:shadow-card-hover transition-all duration-200 overflow-hidden group">
                  {/* 顶部强调色条 */}
                  <div className={`absolute top-0 left-0 right-0 h-[3px] bg-gradient-to-r transition-opacity duration-200 ${s.enabled ? 'from-transparent via-primary/45 to-transparent' : 'from-transparent via-muted/30 to-transparent'}`} />

                  <CardContent className="px-5 pt-[calc(1.25rem+3px)] pb-1 flex flex-col items-center text-center">
                    {/* 大图标 */}
                    <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mb-3 transition-all duration-200 ${
                      s.enabled
                        ? 'bg-gradient-to-br from-primary/15 to-primary/5 ring-1 ring-primary/15'
                        : 'bg-muted/50 ring-1 ring-border'
                    }`}>
                      <SkillIcon className={`w-8 h-8 transition-colors duration-200 ${s.enabled ? 'text-primary' : 'text-text-disabled'}`} />
                    </div>

                    {/* 名称 */}
                    <span className={`font-semibold truncate max-w-full ${s.enabled ? 'text-foreground' : 'text-text-tertiary'}`}>
                      {s.name}
                    </span>

                    {/* 分类标签 */}
                    <Badge variant={s.enabled ? 'outline' : 'secondary'} className="rounded-full text-[11px] px-2 py-0 mt-1.5">
                      {category}
                    </Badge>

                    {/* 描述 */}
                    <p className="text-sm text-text-secondary line-clamp-2 leading-relaxed mt-2.5 min-h-[2.75rem]">
                      {s.description || '无描述'}
                    </p>

                    {/* 路径（小字） */}
                    <div className="flex items-center gap-1 mt-2 text-[11px] text-text-tertiary/70 w-full justify-center">
                      <FileText className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate font-mono max-w-[180px]">{s.path}</span>
                    </div>

                    {/* 分隔 + 开关 */}
                    <div className="w-full mt-3 pt-3 border-t border-border/60">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-text-tertiary select-none">
                          {s.enabled ? '已启用' : '已禁用'}
                        </span>
                        <Switch checked={s.enabled} onCheckedChange={(v) => handleToggle(s.name, v)} />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )})}
            </div>
          )
        }
      </ScrollArea>
    </div>
  )
}
