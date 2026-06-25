import { useEffect, useState, useRef, useCallback } from 'react'
import { Shield, FileText, FolderOpen, Trash2, Clock, AlertTriangle } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

export interface PermissionRequest {
  id: string
  tool: string
  tool_label?: string
  conn_name?: string
  paths: string[]
  operation: 'read' | 'write' | 'delete' | 'execute'
  risk: 'low' | 'medium' | 'high'
  preview: string
}

interface PermissionDialogProps {
  request: PermissionRequest | null
  onResponse: (id: string, action: 'allow_once' | 'allow_always' | 'allow_session' | 'deny' | 'deny_always') => void
  timeoutSeconds?: number
}

const RISK_COLORS: Record<string, string> = {
  low: 'bg-success/20 text-success border-success/30',
  medium: 'bg-warning/20 text-warning border-warning/30',
  high: 'bg-danger/20 text-danger border-danger/30',
}

const RISK_LABELS: Record<string, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
}

const OP_ICONS: Record<string, typeof FileText> = {
  read: FileText,
  write: FolderOpen,
  delete: Trash2,
  execute: Shield,
}

const OP_LABELS: Record<string, string> = {
  read: '读取',
  write: '写入',
  delete: '删除',
  execute: '代码执行',
}

const TOOL_LABELS: Record<string, string> = {
  execute_python: 'Python 代码',
  execute_shell: 'Shell 命令',
}

export default function PermissionDialog({
  request,
  onResponse,
  timeoutSeconds = 60,
}: PermissionDialogProps) {
  const [remaining, setRemaining] = useState(timeoutSeconds)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const respondedRef = useRef(false)

  // Reset timer when a new request comes in
  useEffect(() => {
    if (!request) {
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
      setRemaining(timeoutSeconds)
      respondedRef.current = false
      return
    }

    setRemaining(timeoutSeconds)
    respondedRef.current = false

    timerRef.current = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          // Timeout → auto deny
          if (!respondedRef.current && timerRef.current) {
            respondedRef.current = true
            clearInterval(timerRef.current)
            timerRef.current = null
            // Use setTimeout to avoid state update during render
            setTimeout(() => onResponse(request.id, 'deny'), 0)
          }
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
  }, [request?.id, timeoutSeconds]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleAction = useCallback(
    (action: 'allow_once' | 'allow_always' | 'allow_session' | 'deny' | 'deny_always') => {
      if (!request || respondedRef.current) return
      respondedRef.current = true
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
      onResponse(request.id, action)
    },
    [request, onResponse]
  )

  const isOpen = request !== null

  if (!request) return null

  const OpIcon = OP_ICONS[request.operation] || FileText
  const isCodeExec = request.operation === 'execute'
  const toolLabel = request.tool_label || TOOL_LABELS[request.tool] || request.tool

  return (
    <Dialog open={isOpen} onOpenChange={(open) => {
      if (!open && !respondedRef.current) {
        handleAction('deny')
      }
    }}>
      <DialogContent
        className="sm:max-w-md"
        showCloseButton={false}
      >
        <DialogHeader>
          <div className="flex items-center gap-2">
            <div className={`p-1.5 rounded-lg ${
              request.risk === 'high' ? 'bg-danger/10' :
              request.risk === 'medium' ? 'bg-warning/10' :
              'bg-success/10'
            }`}>
              <Shield className={`h-4 w-4 ${
                request.risk === 'high' ? 'text-danger' :
                request.risk === 'medium' ? 'text-warning' :
                'text-success'
              }`} />
            </div>
            <DialogTitle>
              {isCodeExec ? `AI 请求执行 ${toolLabel}` : 'AI 请求文件操作权限'}
            </DialogTitle>
          </div>
          <DialogDescription>
            {isCodeExec
              ? `AI 正在尝试执行 ${toolLabel}，需要你的批准`
              : 'AI 正在尝试执行文件操作，需要你的批准'}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          {/* 操作类型和风险等级 */}
          <div className="flex items-center gap-2">
            <OpIcon className="h-4 w-4 text-text-secondary" />
            <span className="text-sm font-medium">
              {isCodeExec ? toolLabel : (OP_LABELS[request.operation] || request.tool)}
            </span>
            <Badge className={`text-[10px] border ${RISK_COLORS[request.risk]}`}>
              {RISK_LABELS[request.risk]}
            </Badge>
          </div>

          {/* 代码执行：显示代码/命令内容 */}
          {isCodeExec ? (
            <div className="space-y-1">
              <span className="text-[10px] text-text-tertiary uppercase tracking-wide">
                {request.tool === 'execute_shell' ? 'Shell 命令' : 'Python 代码'}
              </span>
              <div className="text-xs font-mono bg-muted px-2 py-1.5 rounded border border-border/50 max-h-44 overflow-y-auto whitespace-pre-wrap break-all">
                {request.preview || request.paths[0] || '(无内容)'}
              </div>
            </div>
          ) : (
            <>
              {/* 文件操作：目标路径 */}
              <div className="space-y-1">
                <span className="text-[10px] text-text-tertiary uppercase tracking-wide">
                  目标路径
                </span>
                {request.paths.map((p, i) => (
                  <div
                    key={i}
                    className="text-xs font-mono bg-muted/50 px-2 py-1.5 rounded border border-border/50 break-all"
                  >
                    {p}
                  </div>
                ))}
              </div>

              {/* 内容预览 */}
              {request.preview && (
                <div className="space-y-1">
                  <span className="text-[10px] text-text-tertiary uppercase tracking-wide">
                    内容预览
                  </span>
                  <div className="text-xs font-mono bg-muted/50 px-2 py-1.5 rounded border border-border/50 max-h-24 overflow-y-auto whitespace-pre-wrap break-all">
                    {request.preview}
                  </div>
                </div>
              )}
            </>
          )}

          {/* 超时倒计时 */}
          <div className="flex items-center gap-1.5 text-[10px] text-text-tertiary">
            <Clock className="h-3 w-3" />
            <span>
              剩余 {remaining} 秒 · 超时自动拒绝
            </span>
            {/* 进度条 */}
            <div className="flex-1 h-1 bg-muted rounded-full overflow-hidden ml-1">
              <div
                className={`h-full rounded-full transition-all duration-1000 ${
                  remaining > 30 ? 'bg-success' :
                  remaining > 10 ? 'bg-warning' :
                  'bg-danger'
                }`}
                style={{ width: `${(remaining / timeoutSeconds) * 100}%` }}
              />
            </div>
          </div>

          {/* 高风险警告 */}
          {request.risk === 'high' && (
            <div className="flex items-start gap-1.5 text-[11px] text-danger bg-danger/5 px-2 py-1.5 rounded">
              <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              <span>
                {isCodeExec
                  ? '此操作会在你的电脑上执行代码，请确认代码来源可信。'
                  : '此操作会删除文件或目录，无法撤销。请仔细确认。'}
              </span>
            </div>
          )}
        </div>

        <DialogFooter>
          {isCodeExec ? (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAction('deny')}
                className="text-xs"
              >
                拒绝
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAction('allow_session')}
                className="text-xs"
              >
                本次会话允许
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={() => handleAction('allow_once')}
                className="text-xs"
              >
                允许一次
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => handleAction('deny_always')}
                className="text-xs"
              >
                始终拒绝
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAction('deny')}
                className="text-xs"
              >
                拒绝
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAction('allow_always')}
                className="text-xs"
              >
                始终允许
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={() => handleAction('allow_once')}
                className="text-xs"
              >
                允许一次
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
