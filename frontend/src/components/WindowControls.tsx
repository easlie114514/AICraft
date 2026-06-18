import { Minus, Square, X } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function WindowControls() {
  const isPywebview = typeof window !== 'undefined' && (window as any).pywebview !== undefined

  const handleMinimize = () => {
    if (isPywebview) (window as any).pywebview.api.minimize()
  }
  const handleMaximize = () => {
    if (isPywebview) (window as any).pywebview.api.toggle_fullscreen()
  }
  const handleClose = () => {
    if (isPywebview) (window as any).pywebview.api.close()
  }

  return (
    <div className="flex items-center gap-0.5">
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-nav-text hover:bg-white/20 rounded-lg"
        onClick={handleMinimize}
      >
        <Minus className="h-4 w-4" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-nav-text hover:bg-white/20 rounded-lg"
        onClick={handleMaximize}
      >
        <Square className="h-3.5 w-3.5" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-nav-text hover:bg-red-500 hover:text-white rounded-lg"
        onClick={handleClose}
      >
        <X className="h-4 w-4" />
      </Button>
    </div>
  )
}
