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
    <div className="flex items-center justify-between h-14 select-none shrink-0 bg-nav-bg border-b border-white/5 pl-3 pr-1 app-region-drag relative z-40">
      {/* 导航栏水平渐变覆盖：左侧微亮增强层次 */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'linear-gradient(to right, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.02) 15%, transparent 40%)',
        }}
      />

      {/* 左侧：Logo + 品牌名 */}
      <div className="flex items-center gap-2 mr-4 app-region-drag relative">
        {/* 背衬光晕 — 让暗色 Logo 在深色导航栏上可见 */}
        <div
          className="absolute inset-0 w-28 -left-3 h-full pointer-events-none"
          style={{
            background: 'radial-gradient(ellipse at 30% 50%, rgba(255,255,255,0.10) 0%, transparent 70%)',
          }}
        />
        <img
          src="/logo_craft.png"
          alt="AICraft"
          className="h-9 w-auto relative"
          style={{
            filter: 'drop-shadow(0 0 5px rgba(255,255,255,0.30)) drop-shadow(0 0 2px rgba(255,255,255,0.15))',
          }}
        />
      </div>

      {/* 中间：Tab 列表 + 主题切换 */}
      <div className="flex items-center h-full relative">
        <nav className="flex items-center h-full">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => onTabChange(tab.key)}
              className={cn(
                'px-4 h-full text-sm font-medium transition-all duration-200 border-b-2 app-region-no-drag',
                activeTab === tab.key
                  ? 'text-white bg-[linear-gradient(to_top,rgba(255,255,255,0.12)_0%,rgba(255,255,255,0.04)_40%,transparent_60%)]'
                  : 'text-white/60 hover:text-white/80 border-transparent'
              )}
              style={activeTab === tab.key ? { borderBottomColor: 'var(--color-secondary-accent)' } : undefined}
            >
              {tab.label}
            </button>
          ))}
        </nav>
        <div className="ml-3 app-region-no-drag">
          <ThemeSwitcher />
        </div>
      </div>

      {/* 右侧：窗口控制 */}
      <div className="app-region-no-drag relative">
        <WindowControls />
      </div>
    </div>
  )
}
