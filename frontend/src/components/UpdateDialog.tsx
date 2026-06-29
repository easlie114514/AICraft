"use client"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { SparklesIcon } from "lucide-react"

export interface UpdateInfo {
  has_update: boolean
  current_version: string
  latest_version: string | null
  page_url: string | null
  download_url: string | null
  notes: string | null
  error: string | null
}

interface UpdateDialogProps {
  open: boolean
  onClose: () => void
  info: UpdateInfo
}

export default function UpdateDialog({ open, onClose, info }: UpdateDialogProps) {
  const handleUpdate = () => {
    if (info.page_url) {
      window.open(info.page_url, "_blank")
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent showCloseButton={false}>
        <DialogHeader>
          <div className="flex items-center gap-2">
            <SparklesIcon className="w-5 h-5 text-amber-400" />
            <DialogTitle>发现新版本</DialogTitle>
          </div>
          <DialogDescription>
            <div className="mt-2 space-y-1.5 text-sm">
              <p>
                当前版本：<code className="text-xs bg-muted px-1.5 py-0.5 rounded">v{info.current_version}</code>
              </p>
              <p>
                最新版本：<code className="text-xs bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 px-1.5 py-0.5 rounded">v{info.latest_version}</code>
              </p>
            </div>
          </DialogDescription>
        </DialogHeader>

        {info.notes && (
          <div className="text-sm text-muted-foreground">
            <p className="font-medium mb-1.5 text-foreground">更新内容：</p>
            <pre className="whitespace-pre-wrap font-sans text-xs leading-relaxed">
              {info.notes}
            </pre>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            稍后再说
          </Button>
          <Button onClick={handleUpdate}>
            前往更新
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
