"use client"

import { useState, useRef, useEffect } from "react"
import { Download, Upload, HardDrive, FolderOpen, CheckCircle2, AlertTriangle, Loader2, RefreshCw } from "lucide-react"
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

interface MigrationResponse {
  ok: boolean
  old_version?: string
  migrated_count?: number
  skipped_count?: number
  error_count?: number
  migrated?: string[]
  skipped?: string[]
  errors?: string[]
  summary?: string
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

  // ── 迁移状态 ──
  const [migrating, setMigrating] = useState(false)
  const [migrationResult, setMigrationResult] = useState<MigrationResponse | null>(null)
  const [migrationError, setMigrationError] = useState<string | null>(null)
  const [fallbackPath, setFallbackPath] = useState("")
  const [usingPywebview, setUsingPywebview] = useState(true)

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

  useEffect(() => {
    if (!migrationError) return
    const timer = setTimeout(() => setMigrationError(null), 8000)
    return () => clearTimeout(timer)
  }, [migrationError])

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

  // ── 从旧版迁移 ──

  const handleMigrate = async (dirPath: string) => {
    setMigrating(true)
    setMigrationResult(null)
    setMigrationError(null)

    try {
      const res = await fetch("/api/data/migrate-from-old-version", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_dir: dirPath }),
      })
      const data: MigrationResponse = await res.json()

      if (!res.ok) {
        setMigrationError(data.detail || "迁移失败")
      } else {
        setMigrationResult(data)
      }
    } catch {
      setMigrationError("网络错误，迁移失败")
    } finally {
      setMigrating(false)
    }
  }

  const handlePickDirectory = async () => {
    const api = (window as any).pywebview?.api
    if (api?.pick_directory) {
      setUsingPywebview(true)
      try {
        const path = await api.pick_directory()
        if (path) {
          await handleMigrate(path)
        }
      } catch {
        // pywebview 调用失败，回退到文本输入
        setUsingPywebview(false)
      }
    } else {
      setUsingPywebview(false)
    }
  }

  const handleFallbackSubmit = () => {
    if (fallbackPath.trim()) {
      handleMigrate(fallbackPath.trim())
    }
  }

  // ── 重启应用 ──

  const handleRestart = () => {
    const api = (window as any).pywebview?.api
    if (api?.restart) {
      api.restart()
    } else {
      // 回退：浏览器开发模式下刷新页面
      window.location.reload()
    }
  }

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
                  <div className="flex flex-col gap-2">
                    <span className="leading-relaxed">
                      导入完成：新增 {importResult.extracted ?? 0} 项，覆盖还原 {importResult.overwritten ?? importResult.skipped ?? 0} 项
                      {importResult.failed?.length ? `，${importResult.failed.length} 项失败` : ""}
                      。部分数据需重启后生效。
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleRestart}
                      className="self-start"
                    >
                      <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
                      重启应用
                    </Button>
                  </div>
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

        <Separator />

        {/* ── 从旧版迁移 ── */}
        <SettingRow
          title="从旧版迁移"
          description="选择旧版 AICraft 根目录，将用户数据（配置、模型、对话、记忆、知识库等）迁移到当前版本"
        >
          {usingPywebview ? (
            <Button
              variant="outline"
              size="sm"
              onClick={handlePickDirectory}
              disabled={migrating}
            >
              {migrating ? (
                <span className="inline-flex items-center gap-1">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  迁移中...
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5">
                  <FolderOpen className="h-3.5 w-3.5" />
                  选择目录
                </span>
              )}
            </Button>
          ) : (
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="输入旧版目录路径..."
                value={fallbackPath}
                onChange={(e) => setFallbackPath(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleFallbackSubmit()}
                className="h-8 w-56 text-xs border border-border rounded-lg bg-background text-text-primary px-2.5 placeholder:text-text-tertiary"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={handleFallbackSubmit}
                disabled={migrating || !fallbackPath.trim()}
              >
                {migrating ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  "迁移"
                )}
              </Button>
            </div>
          )}
        </SettingRow>

        {/* 迁移结果通知 */}
        {(migrationResult || migrationError) && (
          <>
            <Separator />
            <div className="px-4 py-3">
              {migrationResult?.ok ? (
                <div className="flex items-start gap-2 text-xs animate-in fade-in duration-200">
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0 mt-0.5 text-green-600 dark:text-green-400" />
                  <div className="flex flex-col gap-2">
                    <span className="leading-relaxed text-green-600 dark:text-green-400">
                      {migrationResult.summary}
                    </span>
                    {migrationResult.old_version && (
                      <span className="text-text-tertiary">
                        来源版本：v{migrationResult.old_version}
                      </span>
                    )}
                    {migrationResult.migrated && migrationResult.migrated.length > 0 && (
                      <details className="text-text-tertiary">
                        <summary className="cursor-pointer hover:text-text-primary text-[11px]">
                          查看详情（{migrationResult.migrated_count} 项已迁移{migrationResult.skipped_count ? `，${migrationResult.skipped_count} 项已跳过` : ""}）
                        </summary>
                        <ul className="mt-1 ml-2 space-y-0.5 list-disc list-inside max-h-32 overflow-y-auto text-[11px]">
                          {migrationResult.migrated.map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </details>
                    )}
                    {migrationResult.errors && migrationResult.errors.length > 0 && (
                      <div className="text-red-500 dark:text-red-400">
                        {migrationResult.errors.length} 项错误：
                        <ul className="ml-2 list-disc list-inside">
                          {migrationResult.errors.slice(0, 5).map((e, i) => (
                            <li key={i}>{e}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleRestart}
                      className="self-start"
                    >
                      <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
                      重启应用
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex items-start gap-2 text-xs text-red-600 dark:text-red-400 animate-in fade-in duration-200">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                  <span className="leading-relaxed">{migrationError}</span>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </>
  )
}
