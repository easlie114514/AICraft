import { useState, useEffect, type ComponentType } from 'react'
import NavBar from '@/components/NavBar'
import ResizeHandles from '@/components/ResizeHandles'
import ChatPage from '@/pages/ChatPage'
import ModelPage from '@/pages/ModelPage'
import RolePage from '@/pages/RolePage'
import SkillPage from '@/pages/SkillPage'
import MCPPage from '@/pages/MCPPage'
import RAGPage from '@/pages/RAGPage'
import MemoryPage from '@/pages/MemoryPage'
import SettingsPage from '@/pages/SettingsPage'
import UpdateDialog, { type UpdateInfo } from '@/components/UpdateDialog'
import { api } from '@/lib/api'
import { ChatProvider } from '@/hooks/useChat'

const PAGES = [
  { key: 'chat', label: '对话', component: ChatPage },
  { key: 'skill', label: 'Skill', component: SkillPage },
  { key: 'mcp', label: 'MCP', component: MCPPage },
  { key: 'rag', label: 'RAG', component: RAGPage },
  { key: 'memory', label: '记忆', component: MemoryPage },
  { key: 'role', label: '角色', component: RolePage },
  { key: 'model', label: '模型', component: ModelPage },
  { key: 'settings', label: '设置', component: SettingsPage },
] as const

type TabKey = (typeof PAGES)[number]['key']

function App() {
  const [activeTab, setActiveTab] = useState<TabKey>('chat')
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null)

  // 挂载时静默检查更新
  useEffect(() => {
    api.get<UpdateInfo>('/update/check')
      .then((data) => {
        if (data.has_update) setUpdateInfo(data)
      })
      .catch(() => {}) // 静默失败
  }, [])

  return (
    <ChatProvider>
      <div className="flex flex-col fixed inset-0">
        <ResizeHandles />
        <NavBar
          tabs={PAGES.map((p) => ({ key: p.key, label: p.label }))}
          activeTab={activeTab}
          onTabChange={(key) => setActiveTab(key as TabKey)}
        />
        <main className="flex-1 overflow-hidden bg-background flex flex-col">
          {PAGES.map(({ key, component }) => {
            const Page = component as ComponentType<{ isActive?: boolean }>
            return (
              <div key={key} className={key === activeTab ? 'flex-1 flex flex-col min-h-0 overflow-hidden' : 'hidden'}>
                <Page isActive={key === activeTab} />
              </div>
            )
          })}
        </main>
      </div>
      {updateInfo && (
        <UpdateDialog
          open={true}
          onClose={() => setUpdateInfo(null)}
          info={updateInfo}
        />
      )}
    </ChatProvider>
  )
}

export default App
