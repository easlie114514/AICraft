import { Button } from '@/components/ui/button'
import WindowControls from '@/components/WindowControls'
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
    <div
      className="flex items-center justify-between px-2 h-12 select-none shrink-0"
      style={{ backgroundColor: '#2B4C7E' }}
    >
      <div className="flex items-center gap-1.5">
        {tabs.map((tab) => (
          <Button
            key={tab.key}
            variant="ghost"
            size="sm"
            className={cn(
              'h-8 px-3 text-sm font-medium rounded-lg transition-colors',
              activeTab === tab.key
                ? 'bg-white text-primary hover:bg-white/90'
                : 'bg-white/20 text-white hover:bg-white/30'
            )}
            onClick={() => onTabChange(tab.key)}
          >
            {tab.label}
          </Button>
        ))}
      </div>
      <WindowControls />
    </div>
  )
}
