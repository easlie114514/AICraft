import { useState } from 'react'
import NavBar from '@/components/NavBar'
import ResizeHandles from '@/components/ResizeHandles'
import ChatPage from '@/pages/ChatPage'
import ModelPage from '@/pages/ModelPage'
import RolePage from '@/pages/RolePage'
import SkillPage from '@/pages/SkillPage'
import MCPPage from '@/pages/MCPPage'
import RAGPage from '@/pages/RAGPage'
import MemoryPage from '@/pages/MemoryPage'
import { ChatProvider } from '@/hooks/useChat'

const PAGES = [
  { key: 'chat', label: '对话', component: ChatPage },
  { key: 'skill', label: 'Skill', component: SkillPage },
  { key: 'mcp', label: 'MCP', component: MCPPage },
  { key: 'rag', label: 'RAG', component: RAGPage },
  { key: 'memory', label: '记忆', component: MemoryPage },
  { key: 'role', label: '角色', component: RolePage },
  { key: 'model', label: '模型', component: ModelPage },
] as const

type TabKey = (typeof PAGES)[number]['key']

function App() {
  const [activeTab, setActiveTab] = useState<TabKey>('chat')

  const ActivePage = PAGES.find((p) => p.key === activeTab)?.component ?? ChatPage

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
          <ActivePage />
        </main>
      </div>
    </ChatProvider>
  )
}

export default App
