"use client"

import { useState, useEffect } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { SparklesIcon, Loader2Icon, CheckCircleIcon, AlertCircleIcon } from "lucide-react"
import { api } from "@/lib/api"

export interface UpdateInfo {
  has_update: boolean
  current_version: string
  latest_version: string | null
  page_url: string | null
  download_url: string | null
  notes: string | null
  error: string | null
}

type UpgradeState = "idle" | "downloading" | "extracting" | "ready" | "restarting" | "error"

interface DownloadProgress {
  task_id: string
  status: "downloading" | "extracting" | "done" | "error"
  progress: number | null
  downloaded_bytes: number
  total_bytes: number | null
  message: string
  error: string | null
  result: {
    staging_dir: string
    file_count: number
    new_version: string | null
  } | null
}

interface UpdateDialogProps {
  open: boolean
  onClose: () => void
  info: UpdateInfo
}

export default function UpdateDialog({ open, onClose, info }: UpdateDialogProps) {
  const [state, setState] = useState<UpgradeState>("idle")
  const [errorMsg, setErrorMsg] = useState("")
  const [stagingDir, setStagingDir] = useState("")
  const [taskId, setTaskId] = useState("")
  const [downloadProgress, setDownloadProgress] = useState<{
    downloaded: number
    total: number | null
  } | null>(null)

  const isBusy = state === "downloading" || state === "extracting" || state === "restarting"

  const getApi = () => (typeof window !== "undefined" ? (window as any).pywebview?.api : null)

  // 跳转 GitHub（降级路径：没有 download_url 时）
  const handleOpenPage = () => {
    if (info.page_url) {
      window.open(info.page_url, "_blank")
    }
  }

  // 一键升级：启动后台下载任务
  const handleUpgrade = async () => {
    setState("downloading")
    setErrorMsg("")
    setDownloadProgress(null)
    try {
      const { task_id } = await api.post<{ task_id: string }>("/update/download", {
        download_url: info.download_url || "",
      })
      setTaskId(task_id)
    } catch (err: any) {
      setState("error")
      setErrorMsg(err.message || "无法启动下载，请稍后重试")
    }
  }

  // 触发重启（解压完成后调用）
  const restartSoon = () => {
    setTimeout(() => {
      setState("restarting")
      const pyApi = getApi()
      if (pyApi?.upgrade_restart) {
        // 打包模式：bat + win.destroy()
        pyApi.upgrade_restart(stagingDir)
      } else {
        // 开发模式降级：调后端 + 手动关窗口
        api.post("/update/upgrade", { staging_dir: stagingDir }).then(() => {
          if (pyApi?.close) pyApi.close()
        })
      }
    }, 300)
  }

  // 轮询下载进度
  useEffect(() => {
    if (state !== "downloading" && state !== "extracting") return
    if (!taskId) return

    const timer = setInterval(async () => {
      try {
        const p = await api.get<DownloadProgress>(`/update/download/${taskId}`)
        if (p.status === "downloading") {
          setState("downloading")
          setDownloadProgress({
            downloaded: p.downloaded_bytes,
            total: p.total_bytes,
          })
        } else if (p.status === "extracting") {
          setState("extracting")
        } else if (p.status === "done") {
          setStagingDir(p.result!.staging_dir)
          setState("ready")
          setDownloadProgress({
            downloaded: p.downloaded_bytes ?? 0,
            total: p.total_bytes,
          })
          restartSoon()
        } else if (p.status === "error") {
          setState("error")
          setErrorMsg(p.error || "下载失败，请稍后重试")
        }
      } catch {
        // 瞬时轮询失败：静默跳过，下一拍重试
      }
    }, 500)
    return () => clearInterval(timer)
  }, [state, taskId]) // eslint-disable-line react-hooks/exhaustive-deps

  // 每次打开时重置状态
  useEffect(() => {
    if (open) {
      setState("idle")
      setErrorMsg("")
      setStagingDir("")
      setTaskId("")
      setDownloadProgress(null)
    }
  }, [open])

  const hasDownloadUrl = info.download_url && info.download_url.length > 0

  const progressPercent =
    downloadProgress?.total
      ? Math.min(99, (downloadProgress.downloaded / downloadProgress.total) * 100)
      : null

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o && isBusy) return // 忙碌中禁止关闭
        if (!o) onClose()
      }}
    >
      <DialogContent showCloseButton={!isBusy}>
        <DialogHeader>
          <div className="flex items-center gap-2">
            {state === "downloading" ? (
              <Loader2Icon className="w-5 h-5 text-blue-400 animate-spin" />
            ) : state === "extracting" ? (
              <Loader2Icon className="w-5 h-5 text-blue-400 animate-spin" />
            ) : state === "ready" || state === "restarting" ? (
              <CheckCircleIcon className="w-5 h-5 text-green-400" />
            ) : state === "error" ? (
              <AlertCircleIcon className="w-5 h-5 text-red-400" />
            ) : (
              <SparklesIcon className="w-5 h-5 text-amber-400" />
            )}
            <DialogTitle>
              {state === "downloading"
                ? "正在下载更新..."
                : state === "extracting"
                  ? "正在解压..."
                  : state === "ready"
                    ? "准备重启"
                    : state === "restarting"
                      ? "正在重启..."
                      : state === "error"
                        ? "升级失败"
                        : "发现新版本"}
            </DialogTitle>
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

        {info.notes && state === "idle" && (
          <div className="text-sm text-muted-foreground">
            <p className="font-medium mb-1.5 text-foreground">更新内容：</p>
            <pre className="whitespace-pre-wrap font-sans text-xs leading-relaxed">
              {info.notes}
            </pre>
          </div>
        )}

        {state === "downloading" && (
          <div className="flex flex-col items-center gap-3 py-4">
            <Progress
              value={progressPercent}
              className="w-full max-w-xs"
            />
            <p className="text-sm text-muted-foreground">
              {downloadProgress?.total
                ? `正在下载 ${(downloadProgress.downloaded / 1e6).toFixed(1)} MB / ${(downloadProgress.total / 1e6).toFixed(1)} MB (${Math.floor(progressPercent ?? 0)}%)`
                : `正在下载 ${downloadProgress ? (downloadProgress.downloaded / 1e6).toFixed(1) : "0.0"} MB...`}
            </p>
          </div>
        )}

        {state === "extracting" && (
          <div className="flex flex-col items-center gap-3 py-4">
            <Loader2Icon className="w-8 h-8 text-blue-400 animate-spin" />
            <p className="text-sm text-muted-foreground">正在解压新版本，请稍候...</p>
          </div>
        )}

        {state === "ready" && (
          <div className="flex flex-col items-center gap-3 py-4">
            <CheckCircleIcon className="w-8 h-8 text-green-400" />
            <p className="text-sm text-muted-foreground">新版本已准备就绪，即将重启应用...</p>
          </div>
        )}

        {state === "restarting" && (
          <div className="flex flex-col items-center gap-3 py-4">
            <Loader2Icon className="w-8 h-8 text-blue-400 animate-spin" />
            <p className="text-sm text-muted-foreground">正在重启应用...</p>
          </div>
        )}

        {state === "error" && (
          <div className="flex flex-col items-center gap-3 py-4">
            <AlertCircleIcon className="w-8 h-8 text-red-400" />
            <p className="text-sm text-red-500">{errorMsg}</p>
          </div>
        )}

        <DialogFooter>
          {state === "idle" && (
            <>
              <Button variant="outline" onClick={onClose}>
                稍后再说
              </Button>
              {hasDownloadUrl ? (
                <Button onClick={handleUpgrade}>
                  一键升级
                </Button>
              ) : (
                <Button onClick={handleOpenPage}>
                  前往更新
                </Button>
              )}
            </>
          )}
          {state === "error" && (
            <>
              <Button variant="outline" onClick={onClose}>
                关闭
              </Button>
              <Button onClick={handleUpgrade}>
                重试
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
