import WindowControls from '@/components/WindowControls'
import ThemeSwitcher from '@/components/ThemeSwitcher'
import { cn } from '@/lib/utils'

interface TabItem {
  key: string
  label: string
}

interface NavBarProps {
  tabs: TabItem[]
  activeTab: string
  onTabChange: (key: string) => void
}

export default function NavBar({ tabs, activeTab, onTabChange }: NavBarProps) {
  return (
    <div className="flex items-center justify-between h-14 select-none shrink-0 bg-nav-bg border-b border-white/5 pl-3 pr-1">
      {/* 左侧：Logo + 品牌名 */}
      <div className="flex items-center gap-2 mr-4">
        <img src="/logo_craft.png" alt="AICraft" className="h-9 w-auto" />
      </div>

      {/* 中间：Tab 列表 + 主题切换 */}
      <div className="flex items-center h-full">
        <nav className="flex items-center h-full">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => onTabChange(tab.key)}
              className={cn(
                'px-4 h-full text-sm font-medium transition-all duration-200 border-b-2',
                activeTab === tab.key
                  ? 'text-white border-white'
                  : 'text-white/60 hover:text-white/80 border-transparent'
              )}
            >
              {tab.label}
            </button>
          ))}
        </nav>
        <div className="ml-3">
          <ThemeSwitcher />
        </div>
      </div>

      {/* 右侧：窗口控制 */}
      <WindowControls />
    </div>
  )
}
