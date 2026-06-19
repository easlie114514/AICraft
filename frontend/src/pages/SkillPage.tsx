import { useState, useEffect, useCallback } from 'react'
import { FolderOpen, RefreshCw, Puzzle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { api } from '@/lib/api'

interface Skill {
  name: string
  description: string
  enabled: boolean
  path: string
}

export default function SkillPage() {
  const [skills, setSkills] = useState<Skill[]>([])

  const loadSkills = useCallback(async () => {
    try {
      const data = await api.get<Skill[]>('/skills')
      setSkills(data)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadSkills() }, [loadSkills])

  const handleToggle = async (name: string, enabled: boolean) => {
    await api.put(`/skills/${encodeURIComponent(name)}/toggle`, { enabled })
    loadSkills()
  }

  const handleOpenDir = async (name: string) => {
    await api.post(`/skills/${encodeURIComponent(name)}/open`)
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden p-6">
      <div className="shrink-0 flex items-center justify-between mb-4">
        <h2 className="text-lg font-medium text-foreground">Skill 管理</h2>
        <Button variant="outline" size="icon" onClick={loadSkills} className="rounded-xl">
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        {skills.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
            <Puzzle className="h-12 w-12 mb-3 opacity-30" />
            <p className="text-sm">暂无 Skill</p>
            <p className="text-xs mt-1">在 skills/ 目录下创建 SKILL.md 即可添加</p>
          </div>
        ) : (
          <div className="grid gap-4 pr-1">
            {skills.map((s) => (
              <Card key={s.name} className="rounded-2xl">
                <CardContent className="p-4">
                  <div className="flex items-center gap-4">
                    <Avatar className="h-10 w-10 shrink-0 rounded-xl" style={{ background: 'linear-gradient(135deg, #5B9BD5, #2B4C7E)' }}>
                      <AvatarFallback className="bg-transparent text-white">
                        <Puzzle className="h-5 w-5" />
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium">{s.name}</p>
                      <p className="text-sm text-muted-foreground truncate">{s.description || '无描述'}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Switch checked={s.enabled} onCheckedChange={(v) => handleToggle(s.name, v)} className="rounded-xl" />
                      <Button variant="outline" size="sm" onClick={() => handleOpenDir(s.name)} className="rounded-xl">
                        <FolderOpen className="h-4 w-4 mr-1" />
                        打开目录
                      </Button>
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
