"use client"

import { useState, useRef, useEffect, useCallback, type MouseEvent as ReactMouseEvent, type WheelEvent as ReactWheelEvent, type ChangeEvent } from 'react'
import { Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import type { EmotionKey } from './EmotionSlotGrid'

const EMOTION_LABELS: Record<EmotionKey, string> = {
  neutral: '平静',
  happy: '开心',
  thinking: '思考',
  confused: '疑惑',
  working: '工作',
  concerned: '担心',
}

const CONTAINER_SIZE = 300   // CSS pixels for the crop area
const OUTPUT_SIZE = 128      // output PNG resolution
const MIN_CROP = 20          // min crop box display size
const MIN_SCALE = 0.5
const MAX_SCALE = 5
const HANDLE_SIZE = 10       // corner handle size in px

type DragMode = 'image' | 'cropbox' | 'resize' | null
type Corner = 'nw' | 'ne' | 'sw' | 'se'

function clamp(v: number, min: number, max: number) {
  return Math.min(max, Math.max(min, v))
}

interface EmotionCropModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  roleName: string
  emotionKey: EmotionKey
  onSaved?: () => void
}

export default function EmotionCropModal({
  open,
  onOpenChange,
  roleName,
  emotionKey,
  onSaved,
}: EmotionCropModalProps) {
  // ── Image state ──
  const [imageSrc, setImageSrc] = useState<string | null>(null)
  const [naturalSize, setNaturalSize] = useState({ w: 0, h: 0 })
  const [scale, setScale] = useState(1)
  const [offset, setOffset] = useState({ x: 0, y: 0 })

  // ── Crop box state ──
  const [cropBox, setCropBox] = useState({ x: 0, y: 0, size: OUTPUT_SIZE })

  // ── Drag / Resize state ──
  const [dragMode, setDragMode] = useState<DragMode>(null)
  const [dragStart, setDragStart] = useState({ mx: 0, my: 0, ox: 0, oy: 0 })
  const [resizeCorner, setResizeCorner] = useState<Corner | null>(null)
  const [resizeAnchor, setResizeAnchor] = useState({ x: 0, y: 0 })

  // ── UI state ──
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const containerRef = useRef<HTMLDivElement>(null)
  const previewCanvasRef = useRef<HTMLCanvasElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const sourceImageRef = useRef<HTMLImageElement | null>(null)

  // ── Compute initial crop box to cover visible image area ──
  const computeInitialCropBox = (iw: number, ih: number, s: number, ox: number, oy: number) => {
    // Image bounds in container coords
    const imgLeft = ox
    const imgTop = oy
    const imgRight = ox + iw * s
    const imgBottom = oy + ih * s

    // Crop box should cover the visible image area, clamped to container
    const cbLeft = clamp(imgLeft, 0, CONTAINER_SIZE - MIN_CROP)
    const cbTop = clamp(imgTop, 0, CONTAINER_SIZE - MIN_CROP)
    const cbRight = clamp(imgRight, MIN_CROP, CONTAINER_SIZE)
    const cbBottom = clamp(imgBottom, MIN_CROP, CONTAINER_SIZE)

    const cbSize = Math.min(cbRight - cbLeft, cbBottom - cbTop, CONTAINER_SIZE)
    return {
      x: cbLeft,
      y: cbTop,
      size: Math.max(MIN_CROP, cbSize),
    }
  }

  // ── Reset state when modal opens ──
  useEffect(() => {
    if (open) {
      setImageSrc(null)
      setScale(1)
      setOffset({ x: 0, y: 0 })
      setCropBox({ x: 0, y: 0, size: OUTPUT_SIZE })
      setDragMode(null)
      setError(null)
      // Try to load existing image (with cache busting)
      const img = new Image()
      img.onload = () => {
        setImageSrc(img.src)
        setNaturalSize({ w: img.naturalWidth, h: img.naturalHeight })
        sourceImageRef.current = img
        const s = fitScale(img.naturalWidth, img.naturalHeight)
        setScale(s)
        const ct = centerOffset(img.naturalWidth, img.naturalHeight, s)
        setOffset(ct)
        setCropBox(computeInitialCropBox(img.naturalWidth, img.naturalHeight, s, ct.x, ct.y))
      }
      img.onerror = () => {
        // No existing image — that's fine
      }
      img.src = `/api/roles/${encodeURIComponent(roleName)}/emotion/${emotionKey}?t=${Date.now()}`
    }
  }, [open, roleName, emotionKey])

  const fitScale = (iw: number, ih: number) => {
    return Math.min(CONTAINER_SIZE / iw, CONTAINER_SIZE / ih, 2)
  }

  const centerOffset = (iw: number, ih: number, s: number) => {
    return {
      x: (CONTAINER_SIZE - iw * s) / 2,
      y: (CONTAINER_SIZE - ih * s) / 2,
    }
  }

  // ── Image import ──
  const handleFileSelect = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setError('请选择图片文件')
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      const url = reader.result as string
      const img = new Image()
      img.onload = () => {
        setImageSrc(url)
        setNaturalSize({ w: img.naturalWidth, h: img.naturalHeight })
        sourceImageRef.current = img
        const s = fitScale(img.naturalWidth, img.naturalHeight)
        setScale(s)
        const ct = centerOffset(img.naturalWidth, img.naturalHeight, s)
        setOffset(ct)
        setCropBox(computeInitialCropBox(img.naturalWidth, img.naturalHeight, s, ct.x, ct.y))
        setError(null)
      }
      img.src = url
    }
    reader.readAsDataURL(file)
  }, [])

  // ── Mouse handlers ──

  const handleImageMouseDown = (e: ReactMouseEvent) => {
    if (dragMode) return
    setDragMode('image')
    setDragStart({ mx: e.clientX, my: e.clientY, ox: offset.x, oy: offset.y })
  }

  const handleCropBoxMouseDown = (e: ReactMouseEvent) => {
    e.stopPropagation()
    if (dragMode) return
    setDragMode('cropbox')
    setDragStart({ mx: e.clientX, my: e.clientY, ox: cropBox.x, oy: cropBox.y })
  }

  const handleResizeStart = (corner: Corner) => (e: ReactMouseEvent) => {
    e.stopPropagation()
    e.preventDefault()
    setDragMode('resize')
    setResizeCorner(corner)

    // Anchor = opposite corner
    let ax: number, ay: number
    switch (corner) {
      case 'nw': ax = cropBox.x + cropBox.size; ay = cropBox.y + cropBox.size; break
      case 'ne': ax = cropBox.x; ay = cropBox.y + cropBox.size; break
      case 'sw': ax = cropBox.x + cropBox.size; ay = cropBox.y; break
      case 'se': ax = cropBox.x; ay = cropBox.y; break
    }
    setResizeAnchor({ x: ax, y: ay })
  }

  // ── Window-level move/up for reliable drag ──

  useEffect(() => {
    if (!dragMode) return

    const handleMove = (e: globalThis.MouseEvent) => {
      if (dragMode === 'image') {
        setOffset({
          x: dragStart.ox + (e.clientX - dragStart.mx),
          y: dragStart.oy + (e.clientY - dragStart.my),
        })
      } else if (dragMode === 'cropbox') {
        const newX = dragStart.ox + (e.clientX - dragStart.mx)
        const newY = dragStart.oy + (e.clientY - dragStart.my)
        setCropBox(prev => ({
          ...prev,
          x: clamp(newX, 0, CONTAINER_SIZE - prev.size),
          y: clamp(newY, 0, CONTAINER_SIZE - prev.size),
        }))
      } else if (dragMode === 'resize' && resizeCorner) {
        const rect = containerRef.current?.getBoundingClientRect()
        if (!rect) return
        const mx = clamp(e.clientX - rect.left, 0, CONTAINER_SIZE)
        const my = clamp(e.clientY - rect.top, 0, CONTAINER_SIZE)

        const dx = Math.abs(mx - resizeAnchor.x)
        const dy = Math.abs(my - resizeAnchor.y)
        const rawSize = Math.max(dx, dy)

        let newX: number, newY: number
        switch (resizeCorner) {
          case 'nw':
            newX = resizeAnchor.x - rawSize
            newY = resizeAnchor.y - rawSize
            break
          case 'ne':
            newX = resizeAnchor.x
            newY = resizeAnchor.y - rawSize
            break
          case 'sw':
            newX = resizeAnchor.x - rawSize
            newY = resizeAnchor.y
            break
          case 'se':
            newX = resizeAnchor.x
            newY = resizeAnchor.y
            break
        }

        // Clamp to container and min size
        const clampedSize = clamp(rawSize, MIN_CROP, CONTAINER_SIZE)
        newX = clamp(newX, 0, CONTAINER_SIZE - clampedSize)
        newY = clamp(newY, 0, CONTAINER_SIZE - clampedSize)

        setCropBox({ x: newX, y: newY, size: clampedSize })
      }
    }

    const handleUp = () => {
      setDragMode(null)
      setResizeCorner(null)
    }

    window.addEventListener('mousemove', handleMove)
    window.addEventListener('mouseup', handleUp)
    return () => {
      window.removeEventListener('mousemove', handleMove)
      window.removeEventListener('mouseup', handleUp)
    }
  }, [dragMode, dragStart, resizeCorner, resizeAnchor, offset, cropBox])

  // ── Zoom ──
  const handleWheel = useCallback((e: ReactWheelEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const delta = e.deltaY > 0 ? 0.9 : 1.1
    const newScale = clamp(scale * delta, MIN_SCALE, MAX_SCALE)

    const rect = containerRef.current?.getBoundingClientRect()
    if (rect) {
      const mx = e.clientX - rect.left
      const my = e.clientY - rect.top
      const ratio = newScale / scale
      setOffset(prev => ({
        x: mx - ratio * (mx - prev.x),
        y: my - ratio * (my - prev.y),
      }))
    }
    setScale(newScale)
  }, [scale])

  // ── Preview: redraw canvas whenever params change ──
  useEffect(() => {
    const canvas = previewCanvasRef.current
    const img = sourceImageRef.current
    if (!canvas || !img || !imageSrc) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    canvas.width = OUTPUT_SIZE
    canvas.height = OUTPUT_SIZE
    // Source image pixel coordinates under the crop box
    const srcX = (cropBox.x - offset.x) / scale
    const srcY = (cropBox.y - offset.y) / scale
    const srcW = cropBox.size / scale
    const srcH = cropBox.size / scale

    ctx.clearRect(0, 0, OUTPUT_SIZE, OUTPUT_SIZE)
    ctx.drawImage(img, srcX, srcY, srcW, srcH, 0, 0, OUTPUT_SIZE, OUTPUT_SIZE)
  }, [imageSrc, scale, offset, cropBox])

  // ── Save ──
  const handleSave = async () => {
    const canvas = previewCanvasRef.current
    const img = sourceImageRef.current
    if (!canvas || !img || !imageSrc) return

    setSaving(true)
    setError(null)
    try {
      const outCanvas = document.createElement('canvas')
      outCanvas.width = OUTPUT_SIZE
      outCanvas.height = OUTPUT_SIZE
      const ctx = outCanvas.getContext('2d')!
      const srcX = (cropBox.x - offset.x) / scale
      const srcY = (cropBox.y - offset.y) / scale
      const srcW = cropBox.size / scale
      const srcH = cropBox.size / scale

      ctx.drawImage(img, srcX, srcY, srcW, srcH, 0, 0, OUTPUT_SIZE, OUTPUT_SIZE)

      const blob = await new Promise<Blob>((resolve, reject) => {
        outCanvas.toBlob((b) => {
          if (b) resolve(b)
          else reject(new Error('Canvas export failed'))
        }, 'image/png')
      })

      const formData = new FormData()
      formData.append('file', blob, `emotion_${emotionKey}.png`)

      const res = await fetch(
        `/api/roles/${encodeURIComponent(roleName)}/emotion/${emotionKey}`,
        { method: 'PUT', body: formData },
      )
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(detail.detail || `上传失败 (${res.status})`)
      }

      onSaved?.()
      onOpenChange(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  // ── Corner positions ──
  const corners: { key: Corner; left: number; top: number; cursor: string }[] = [
    { key: 'nw', left: cropBox.x - HANDLE_SIZE / 2, top: cropBox.y - HANDLE_SIZE / 2, cursor: 'nw-resize' },
    { key: 'ne', left: cropBox.x + cropBox.size - HANDLE_SIZE / 2, top: cropBox.y - HANDLE_SIZE / 2, cursor: 'ne-resize' },
    { key: 'sw', left: cropBox.x - HANDLE_SIZE / 2, top: cropBox.y + cropBox.size - HANDLE_SIZE / 2, cursor: 'sw-resize' },
    { key: 'se', left: cropBox.x + cropBox.size - HANDLE_SIZE / 2, top: cropBox.y + cropBox.size - HANDLE_SIZE / 2, cursor: 'se-resize' },
  ]

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px] max-h-[92vh] flex flex-col overflow-hidden">
        <DialogHeader className="shrink-0">
          <DialogTitle>配置 {EMOTION_LABELS[emotionKey]} 表情</DialogTitle>
        </DialogHeader>

        <div className="flex-1 min-h-0 overflow-y-auto space-y-4 py-2 px-0.5">
          {/* Import */}
          <div className="flex items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileSelect}
              className="hidden"
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="h-4 w-4 mr-1" />选择图片
            </Button>
            <span className="text-xs text-muted-foreground">从本地导入任意尺寸图片</span>
          </div>

          {error && (
            <p className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded">{error}</p>
          )}

          {/* Crop Area */}
          <div className="flex flex-col items-center gap-3">
            <div
              ref={containerRef}
              className="relative overflow-hidden border border-border rounded-lg select-none bg-muted/30"
              style={{ width: CONTAINER_SIZE, height: CONTAINER_SIZE }}
              onWheel={handleWheel}
            >
              {imageSrc ? (
                <>
                  {/* Layer 0: Transparent drag surface for image panning */}
                  <div
                    className="absolute inset-0 z-0"
                    style={{ cursor: dragMode === 'image' ? 'grabbing' : 'grab' }}
                    onMouseDown={handleImageMouseDown}
                  />

                  {/* Layer 1: Background image (visual only, click-through) */}
                  <img
                    src={imageSrc}
                    alt="crop source"
                    draggable={false}
                    className="absolute z-10 pointer-events-none"
                    style={{
                      left: offset.x,
                      top: offset.y,
                      width: naturalSize.w * scale,
                      height: naturalSize.h * scale,
                    }}
                  />

                  {/* Layer 2: Dim overlay + crop box (above image and drag surface) */}
                  <div className="absolute inset-0 z-20 pointer-events-none">
                    {/* Crop box with massive box-shadow to dim the rest */}
                    <div
                      className={cn(
                        'absolute border-2 border-white shadow-[0_0_0_9999px_rgba(0,0,0,0.5)] pointer-events-auto',
                        dragMode === 'cropbox' ? 'cursor-move' : 'cursor-move',
                      )}
                      style={{
                        left: cropBox.x,
                        top: cropBox.y,
                        width: cropBox.size,
                        height: cropBox.size,
                      }}
                      onMouseDown={handleCropBoxMouseDown}
                    >
                      {/* Inner grid lines for composition guide */}
                      <div className="absolute inset-0 pointer-events-none">
                        <div className="absolute left-1/3 top-0 bottom-0 border-l border-white/30" />
                        <div className="absolute left-2/3 top-0 bottom-0 border-l border-white/30" />
                        <div className="absolute top-1/3 left-0 right-0 border-t border-white/30" />
                        <div className="absolute top-2/3 left-0 right-0 border-t border-white/30" />
                      </div>
                    </div>

                    {/* Corner handles (above the crop box shadow) */}
                    {corners.map(({ key, left, top, cursor }) => (
                      <div
                        key={key}
                        className="absolute bg-white border-2 border-primary rounded-sm pointer-events-auto"
                        style={{
                          left,
                          top,
                          width: HANDLE_SIZE,
                          height: HANDLE_SIZE,
                          cursor,
                        }}
                        onMouseDown={handleResizeStart(key)}
                      />
                    ))}
                  </div>
                </>
              ) : (
                <div className="w-full h-full flex items-center justify-center text-muted-foreground text-sm">
                  点击"选择图片"导入
                </div>
              )}
            </div>

            <p className="text-xs text-muted-foreground">
              拖拽图片移动 · 滚轮缩放 ({scale.toFixed(1)}×) · 拖拽框角调整选区
            </p>
          </div>

          {/* Preview */}
          <div className="flex flex-col items-center gap-2">
            <p className="text-xs font-medium text-text-secondary">
              实时预览 ({OUTPUT_SIZE}×{OUTPUT_SIZE}) — 选区 {Math.round(cropBox.size / scale)}×{Math.round(cropBox.size / scale)}px
            </p>
            <canvas
              ref={previewCanvasRef}
              className="border border-border rounded"
              style={{
                width: OUTPUT_SIZE * 2,
                height: OUTPUT_SIZE * 2,
              }}
            />
          </div>
        </div>

        <DialogFooter className="shrink-0">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
            取消
          </Button>
          <Button onClick={handleSave} disabled={!imageSrc || saving}>
            {saving ? '保存中...' : '确认保存'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
