import { useRef, useCallback } from 'react'

export default function ResizeHandles() {
  const isResizing = useRef(false)
  const lastPos = useRef({ x: 0, y: 0 })
  const edgeRef = useRef('')

  const onResizeStart = useCallback((edge: string) => (e: React.MouseEvent) => {
    e.stopPropagation()
    e.preventDefault()
    isResizing.current = true
    edgeRef.current = edge
    lastPos.current = { x: e.screenX, y: e.screenY }

    const onMouseMove = (ev: MouseEvent) => {
      if (!isResizing.current) return
      const dx = ev.screenX - lastPos.current.x
      const dy = ev.screenY - lastPos.current.y
      if (dx === 0 && dy === 0) return
      lastPos.current = { x: ev.screenX, y: ev.screenY }
      // 延迟读取 api，避免初次渲染时 pywebview 未就绪
      const api = (window as any).pywebview?.api
      if (api?.resize_window) api.resize_window(edgeRef.current, dx, dy)
    }

    const onMouseUp = () => {
      isResizing.current = false
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }, [])

  const edgeZ = 'fixed z-30'
  // 顶部手柄需高于 NavBar (z-40)，否则被遮盖
  const topZ = 'fixed z-50'

  return (
    <>
      {/* ── 四条边 ── */}
      <div className={`${topZ} top-0 left-1 right-1 h-[5px] cursor-n-resize`}
        onMouseDown={onResizeStart('top')} />
      <div className={`${edgeZ} bottom-0 left-1 right-1 h-[5px] cursor-s-resize`}
        onMouseDown={onResizeStart('bottom')} />
      <div className={`${edgeZ} left-0 top-1 bottom-1 w-[5px] cursor-w-resize`}
        onMouseDown={onResizeStart('left')} />
      <div className={`${edgeZ} right-0 top-1 bottom-1 w-[5px] cursor-e-resize`}
        onMouseDown={onResizeStart('right')} />

      {/* ── 四个角 ── */}
      <div className={`${topZ} top-0 left-0 w-[10px] h-[10px] cursor-nw-resize`}
        onMouseDown={onResizeStart('topleft')} />
      <div className={`${topZ} top-0 right-0 w-[10px] h-[10px] cursor-ne-resize`}
        onMouseDown={onResizeStart('topright')} />
      <div className={`${edgeZ} bottom-0 left-0 w-[10px] h-[10px] cursor-sw-resize`}
        onMouseDown={onResizeStart('bottomleft')} />
      <div className={`${edgeZ} bottom-0 right-0 w-[10px] h-[10px] cursor-se-resize`}
        onMouseDown={onResizeStart('bottomright')} />
    </>
  )
}
