import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Puzzle, FolderOpen, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { InputGroup, InputGroupInput, InputGroupAddon, InputGroupButton } from '@/components/ui/input-group'
import { api } from '@/lib/api'

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

  const loadSkills = useCallback(async () => {
    try {
      const data = await api.get<Skill[]>('/skills')
      setSkills(data)
    } catch { /* ignore */ }
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

  const handleBrowseDir = async () => {
    try {
      const res = await api.get<{ ok: boolean; path?: string; detail?: string }>('/skills/browse-dir')
      if (res.ok && res.path) {
        setDirInput(res.path)
        // 自动应用新目录
        const applyRes = await api.put<{ ok: boolean; path?: string; detail?: string }>('/skills/dir', { path: res.path })
        if (applyRes.ok) {
          setSkillDir(applyRes.path || res.path)
          loadSkills()
        } else {
          alert(applyRes.detail || '设置失败')
        }
      }
    } catch (e: any) {
      alert(e?.message || '打开目录失败')
    }
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden p-6">
      <div className="shrink-0 flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-text-primary">Skill 管理</h2>
        <Button variant="outline" size="icon" onClick={() => { loadSkills(); loadDir() }}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {/* 根目录设置 */}
      <div className="shrink-0 flex items-center gap-2 mb-4">
        <InputGroup className="flex-1 rounded-lg">
          <InputGroupInput
            value={dirInput}
            onChange={(e) => setDirInput(e.target.value)}
            placeholder="Skills 根目录路径，例如: skills (相对项目根)"
            className="font-mono text-sm"
          />
          <InputGroupAddon align="inline-end">
            <InputGroupButton onClick={handleBrowseDir} title="浏览文件夹" size="icon-sm">
              <FolderOpen className="h-4 w-4" />
            </InputGroupButton>
          </InputGroupAddon>
        </InputGroup>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        {skills.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
            <Zap className="w-16 h-16 text-text-disabled mb-4" />
            <p className="text-sm text-text-secondary">暂无 Skill</p>
            <p className="text-xs text-text-tertiary mt-1">设置根目录后，每个一级子目录（含 SKILL.md）即为一个技能</p>
          </div>
        ) : (
          <div className="grid gap-4 pr-1">
            {skills.map((s) => (
              <Card key={s.name} className="hover:shadow-card-hover transition-shadow duration-200">
                <CardContent className="p-4">
                  <div className="flex items-center gap-4">
                    <Avatar className="h-10 w-10 shrink-0 rounded-full bg-primary/15">
                      <AvatarFallback className="bg-transparent text-primary">
                        <Puzzle className="h-5 w-5" />
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium">{s.name}</p>
                      <p className="text-sm text-text-secondary truncate">{s.description || '无描述'}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Switch checked={s.enabled} onCheckedChange={(v) => handleToggle(s.name, v)} />
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  )
}
