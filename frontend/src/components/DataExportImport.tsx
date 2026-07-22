"use client"

import { useState, useRef, useEffect } from "react"
import { Download, Upload, HardDrive, CheckCircle2, AlertTriangle, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { SettingRow, SectionLabel } from "@/components/settings-ui"

interface ExportResponse {
  ok: boolean
  path?: string
  file_count?: number
  size_mb?: number
  error?: string
  warnings?: string[] | null
}

interface ImportResponse {
  ok: boolean
  extracted?: number
  overwritten?: number
  skipped?: number    // 兼容旧版 API
  failed?: string[]
  detail?: string
}

export default function DataExportImport() {
  // ── 导出状态 ──
  const [exporting, setExporting] = useState(false)
  const [exportResult, setExportResult] = useState<ExportResponse | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)

  // ── 导入状态 ──
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<ImportResponse | null>(null)
  const [importError, setImportError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ── 错误消息自动清除，成功结果保持到页面切换 ──
  useEffect(() => {
    if (!exportError) return
    const timer = setTimeout(() => setExportError(null), 8000)
    return () => clearTimeout(timer)
  }, [exportError])

  useEffect(() => {
    if (!importError) return
    const timer = setTimeout(() => setImportError(null), 8000)
    return () => clearTimeout(timer)
  }, [importError])

  // ── 导出 ──

  const handleExport = async () => {
    setExporting(true)
    setExportResult(null)
    setExportError(null)

    try {
      const res = await fetch("/api/data/export", { method: "POST" })
      const data: ExportResponse = await res.json()
      if (data.ok) {
        setExportResult(data)
      } else {
        setExportError(data.error || "导出失败")
      }
    } catch {
      setExportError("网络错误，导出失败")
    } finally {
      setExporting(false)
    }
  }

  // ── 导入 ──

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setImporting(true)
    setImportResult(null)
    setImportError(null)

    try {
      const formData = new FormData()
      formData.append("file", file)

      const res = await fetch("/api/data/import", {
        method: "POST",
        body: formData,
      })
      const data: ImportResponse = await res.json()

      if (!res.ok) {
        setImportError(data.detail || "导入失败")
      } else {
        setImportResult(data)
      }
    } catch {
      setImportError("网络错误，导入失败")
    } finally {
      setImporting(false)
      // 重置 file input 以便重新选择同一文件
      if (fileInputRef.current) {
        fileInputRef.current.value = ""
      }
    }
  }

  // ── UI ──

  return (
    <>
      <SectionLabel icon={HardDrive} title="数据管理" description="导出/导入用户数据，用于备份或迁移" />

      <div className="rounded-xl border border-border bg-card overflow-hidden mb-6">
        {/* 导出 */}
        <SettingRow
          title="导出数据"
          description="将配置、模型、对话记录、记忆、知识库等打包为 ZIP 保存到本地"
        >
          <Button
            variant="outline"
            size="sm"
            onClick={handleExport}
            disabled={exporting}
          >
            {exporting ? (
              <span className="inline-flex items-center gap-1">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                导出中...
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5">
                <Download className="h-3.5 w-3.5" />
                导出数据
              </span>
            )}
          </Button>
        </SettingRow>

        <Separator />

        {/* 导入 */}
        <SettingRow
          title="导入数据"
          description="从备份 ZIP 文件恢复数据（不覆盖已有文件）"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".zip"
            onChange={handleFileSelect}
            className="hidden"
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
          >
            {importing ? (
              <span className="inline-flex items-center gap-1">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                导入中...
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5">
                <Upload className="h-3.5 w-3.5" />
                导入数据
              </span>
            )}
          </Button>
        </SettingRow>

        {/* 导出结果通知 */}
        {(exportResult || exportError) && (
          <>
            <Separator />
            <div className="px-4 py-3">
              {exportResult?.ok ? (
                <div className="flex items-start gap-2 text-xs text-green-600 dark:text-green-400 animate-in fade-in duration-200">
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                  <span className="leading-relaxed">
                    备份已保存：
                    <code className="mx-0.5 px-1 py-0.5 rounded bg-muted text-[11px] break-all">
                      {exportResult.path}
                    </code>
                    {exportResult.file_count !== undefined && (
                      <span className="ml-1">
                        （{exportResult.file_count} 个文件，{exportResult.size_mb} MB）
                      </span>
                    )}
                  </span>
                </div>
              ) : (
                <div className="flex items-start gap-2 text-xs text-red-600 dark:text-red-400 animate-in fade-in duration-200">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                  <span className="leading-relaxed">{exportError}</span>
                </div>
              )}
            </div>
          </>
        )}

        {/* 导入结果通知 */}
        {(importResult || importError) && (
          <>
            {/* 如果导出通知也在显示，再加一条分隔线；否则如果没有导出通知区域，我们已经在上面判断过了 */}
            {!exportResult && !exportError && <Separator />}
            <div className="px-4 py-3">
              {importResult?.ok ? (
                <div className="flex items-start gap-2 text-xs text-green-600 dark:text-green-400 animate-in fade-in duration-200">
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                  <span className="leading-relaxed">
                    导入完成：新增 {importResult.extracted ?? 0} 项，覆盖还原 {importResult.overwritten ?? importResult.skipped ?? 0} 项
                    {importResult.failed?.length ? `，${importResult.failed.length} 项失败` : ""}
                    。建议重启应用以确保数据生效。
                  </span>
                </div>
              ) : (
                <div className="flex items-start gap-2 text-xs text-red-600 dark:text-red-400 animate-in fade-in duration-200">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                  <span className="leading-relaxed">{importError}</span>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </>
  )
}
