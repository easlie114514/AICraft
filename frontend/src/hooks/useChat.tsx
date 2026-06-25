import { createContext, useContext, useReducer, useRef, useCallback, useEffect, useState, type ReactNode } from 'react'
import type { TokenStatsData } from '@/components/TokenPanel'
import type { PermissionRequest } from '@/components/PermissionDialog'

// ── Types ──

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'tool_call' | 'tool_result' | 'system' | 'inject' | 'divider'
  content: string
  timestamp: number
  toolName?: string
  toolArgs?: Record<string, unknown>
  toolResult?: string
  thinking?: string
  thinkingDuration?: number
  scene?: number
}

export interface ContextBudgetInfo {
  pct: number
  totalTokens: number
  inputBudget: number
  model: string
}

interface ChatState {
  messages: ChatMessage[]
  streaming: boolean
  error: string | null
  contextInfo: ContextBudgetInfo | null
  sceneCount: number
}

type ChatAction =
  | { type: 'ADD_USER'; content: string }
  | { type: 'APPEND_TEXT'; content: string }
  | { type: 'APPEND_THINKING'; content: string }
  | { type: 'END_THINKING'; durationMs: number }
  | { type: 'ADD_TOOL_CALL'; name: string; args: Record<string, unknown> }
  | { type: 'ADD_TOOL_RESULT'; name: string; result: string }
  | { type: 'ADD_INJECT'; items: string[] }
  | { type: 'ADD_SYSTEM'; content: string }
  | { type: 'SET_DONE' }
  | { type: 'SET_ERROR'; content: string }
  | { type: 'NEW_SCENE' }
  | { type: 'LOAD_CONVERSATION'; messages: Array<{ role: string; content: string; timestamp?: string }>; convId: string }

// ── Reducer (same logic, now at module level) ──

let msgId = 0
function nextId() {
  return `msg_${++msgId}_${Date.now()}`
}

function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'ADD_USER': {
      return {
        ...state,
        streaming: true,
        error: null,
        messages: [...state.messages, { id: nextId(), role: 'user', content: action.content, timestamp: Date.now() }],
      }
    }
    case 'APPEND_TEXT': {
      const msgs = [...state.messages]
      const last = msgs[msgs.length - 1]
      if (last && last.role === 'assistant') {
        msgs[msgs.length - 1] = { ...last, content: last.content + action.content }
      } else {
        msgs.push({ id: nextId(), role: 'assistant', content: action.content, timestamp: Date.now() })
      }
      return { ...state, messages: msgs }
    }
    case 'APPEND_THINKING': {
      const msgs = [...state.messages]
      const last = msgs[msgs.length - 1]
      // 如果最后一条是 assistant 消息且正在 thinking（thinkingDuration 未设置），追加到 thinking 字段
      if (last && last.role === 'assistant' && last.thinking !== undefined && last.thinkingDuration === undefined) {
        msgs[msgs.length - 1] = {
          ...last,
          thinking: (last.thinking || '') + action.content,
        }
      } else {
        // 新建一条 assistant 消息，只有 thinking，content 为空
        msgs.push({
          id: nextId(),
          role: 'assistant',
          content: '',
          timestamp: Date.now(),
          thinking: action.content,
        })
      }
      return { ...state, messages: msgs, streaming: true }
    }
    case 'END_THINKING': {
      const msgs = [...state.messages]
      const last = msgs[msgs.length - 1]
      if (last && last.role === 'assistant' && last.thinking !== undefined) {
        msgs[msgs.length - 1] = {
          ...last,
          thinkingDuration: action.durationMs,
        }
      }
      return { ...state, messages: msgs }
    }
    case 'ADD_TOOL_CALL': {
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: nextId(),
            role: 'tool_call',
            content: `调用工具: ${action.name}`,
            timestamp: Date.now(),
            toolName: action.name,
            toolArgs: action.args,
          },
        ],
      }
    }
    case 'ADD_TOOL_RESULT': {
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: nextId(),
            role: 'tool_result',
            content: action.result,
            timestamp: Date.now(),
            toolName: action.name,
            toolResult: action.result,
          },
        ],
      }
    }
    case 'ADD_INJECT': {
      // 解析上下文预算信息
      let contextInfo = state.contextInfo
      for (const item of action.items) {
        const match = item.match(/📊 上下文: (\d+)% \(([\d,]+)\/([\d,]+) tokens\)/)
        if (match) {
          contextInfo = {
            pct: parseInt(match[1]),
            totalTokens: parseInt(match[2].replace(/,/g, '')),
            inputBudget: parseInt(match[3].replace(/,/g, '')),
            model: '',
          }
        }
      }
      return {
        ...state,
        contextInfo,
        messages: [
          ...state.messages,
          {
            id: nextId(),
            role: 'system',
            content: `\u{1F4CE} ${action.items.join(' | ')}`,
            timestamp: Date.now(),
          },
        ],
      }
    }
    case 'ADD_SYSTEM': {
      return {
        ...state,
        messages: [...state.messages, { id: nextId(), role: 'system', content: action.content, timestamp: Date.now() }],
      }
    }
    case 'SET_DONE': {
      const msgs = [...state.messages]
      const last = msgs[msgs.length - 1]
      // 如果正在 thinking 但收到 done（用户停止/异常结束），结束 thinking
      if (last && last.role === 'assistant' && last.thinking && last.thinkingDuration === undefined) {
        msgs[msgs.length - 1] = { ...last, thinkingDuration: 0 }
      }
      return { ...state, messages: msgs, streaming: false }
    }
    case 'SET_ERROR': {
      return { ...state, streaming: false, error: action.content }
    }
    case 'NEW_SCENE': {
      const nextScene = state.sceneCount + 1
      return {
        ...state,
        sceneCount: nextScene,
        messages: [
          ...state.messages,
          {
            id: nextId(),
            role: 'divider' as const,
            content: `场景 ${nextScene} · ${new Date().toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}`,
            timestamp: Date.now(),
            scene: nextScene,
          },
        ],
      }
    }
    case 'LOAD_CONVERSATION': {
      const loadedMsgs = action.messages.map((m) => ({
        id: nextId(),
        role: m.role as ChatMessage['role'],
        content: m.content,
        timestamp: m.timestamp ? new Date(m.timestamp).getTime() : Date.now() - 1,
      }))
      return { ...state, messages: loadedMsgs, streaming: false, error: null }
    }
    default:
      return state
  }
}

// ── Context ──

export interface ChatToggles {
  rag: boolean
  memory: boolean
  thinking: boolean
}

interface ChatContextValue {
  state: ChatState
  toggles: ChatToggles
  setToggles: (toggles: ChatToggles) => void
  sendMessage: (content: string, modelId: string, role: string, toggles: ChatToggles) => void
  stopStreaming: () => void
  newScene: () => void
  tokenStats: TokenStatsData | null
  permissionRequest: PermissionRequest | null
  respondPermission: (id: string, action: 'allow_once' | 'allow_always' | 'allow_session' | 'deny' | 'deny_always') => void
}

const ChatContext = createContext<ChatContextValue | null>(null)

// ── Provider ──

export function ChatProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(chatReducer, { messages: [], streaming: false, error: null, contextInfo: null, sceneCount: 1 })
  const [toggles, setToggles] = useState<ChatToggles>({ rag: false, memory: true, thinking: false })
  const [tokenStats, setTokenStats] = useState<TokenStatsData | null>(null)
  const [permissionRequest, setPermissionRequest] = useState<PermissionRequest | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const convIdRef = useRef<string>(localStorage.getItem('aicraft_last_conv_id') || '')
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    // Clean up existing
    if (wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.onerror = null
      wsRef.current.onmessage = null
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/api/chat/ws`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        switch (data.type) {
          case 'thinking':
            dispatch({ type: 'APPEND_THINKING', content: data.content })
            break
          case 'thinking_end':
            dispatch({ type: 'END_THINKING', durationMs: data.duration_ms })
            break
          case 'search_status':
            if (data.status === 'searching') {
              dispatch({ type: 'ADD_INJECT', items: ['🔍 正在搜索...'] })
            } else if (data.status === 'done' && data.sources) {
              dispatch({ type: 'ADD_INJECT', items: [`✅ 搜索完成，找到 ${data.sources.length} 个来源`] })
            }
            break
          case 'text':
            dispatch({ type: 'APPEND_TEXT', content: data.content })
            break
          case 'tool_call':
            dispatch({ type: 'ADD_TOOL_CALL', name: data.name, args: data.args })
            break
          case 'tool_result':
            dispatch({ type: 'ADD_TOOL_RESULT', name: data.name, result: data.result })
            break
          case 'inject_info':
            dispatch({ type: 'ADD_INJECT', items: data.items })
            break
          case 'done':
            dispatch({ type: 'SET_DONE' })
            break
          case 'conv_id':
            if (data.id) {
              convIdRef.current = data.id
              localStorage.setItem('aicraft_last_conv_id', data.id)
            }
            break
          case 'conv_loaded':
            if (data.messages && Array.isArray(data.messages)) {
              convIdRef.current = data.conv_id || ''
              localStorage.setItem('aicraft_last_conv_id', data.conv_id || '')
              dispatch({ type: 'LOAD_CONVERSATION', messages: data.messages, convId: data.conv_id || '' })
            }
            break
          case 'token_stats':
            if (data.data) {
              setTokenStats(data.data)
            }
            break
          case 'permission_request':
            // AI 请求权限 → 弹出确认框
            setPermissionRequest({
              id: data.id,
              tool: data.tool,
              tool_label: data.tool_label || '',
              conn_name: data.conn_name || '',
              paths: data.paths || [],
              operation: data.operation || 'read',
              risk: data.risk || 'low',
              preview: data.preview || '',
            })
            break
          case 'error':
            dispatch({ type: 'SET_ERROR', content: data.content })
            // 如果对话文件不存在，清除本地缓存的 convId
            if (data.content && data.content.includes('不存在')) {
              convIdRef.current = ''
              localStorage.removeItem('aicraft_last_conv_id')
            }
            break
        }
      } catch {
        /* ignore malformed */
      }
    }

    ws.onopen = () => {
      // 启动时获取 token 统计
      ws.send(JSON.stringify({ type: 'get_token_stats' }))
      // 启动时自动恢复上一次对话（无 convId 时后端自动找最近对话）
      ws.send(JSON.stringify({ type: 'load_conv', conv_id: convIdRef.current }))
    }

    ws.onerror = () => {
      dispatch({ type: 'SET_ERROR', content: 'WebSocket 连接失败' })
    }

    ws.onclose = () => {
      // Auto-reconnect after 2s unless component is unmounted
      reconnectTimerRef.current = setTimeout(() => {
        connect()
      }, 2000)
    }

    return ws
  }, [])

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
      const ws = wsRef.current
      if (ws) {
        ws.onclose = null  // prevent reconnect
        ws.close()
      }
    }
  }, [connect])

  const sendMessage = useCallback(
    (content: string, modelId: string, role: string, toggles: ChatToggles) => {
      const ws = wsRef.current
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        // Reconnect and send
        const newWs = connect()
        newWs.onopen = () => {
          dispatch({ type: 'ADD_USER', content })
          newWs.send(
            JSON.stringify({
              type: 'message',
              content,
              model_id: modelId,
              role,
              toggles,
              conversation_id: convIdRef.current,
            })
          )
        }
        return
      }
      dispatch({ type: 'ADD_USER', content })
      ws.send(
        JSON.stringify({
          type: 'message',
          content,
          model_id: modelId,
          role,
          toggles,
          conversation_id: convIdRef.current,
        })
      )
    },
    [connect]
  )

  const stopStreaming = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'stop' }))
    }
    dispatch({ type: 'SET_DONE' })
  }, [])

  const newScene = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'new_scene' }))
    }
    dispatch({ type: 'NEW_SCENE' })
    convIdRef.current = ''
    localStorage.removeItem('aicraft_last_conv_id')
    // 重置当前场景的 token 统计（后端已重置，前端也清零等待推送）
    setTokenStats(null)
  }, [])

  const respondPermission = useCallback(
    (id: string, action: 'allow_once' | 'allow_always' | 'allow_session' | 'deny' | 'deny_always') => {
      setPermissionRequest(null)
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'permission_response',
          id,
          action,
        }))
      }
    },
    []
  )

  return (
    <ChatContext.Provider value={{
      state, toggles, setToggles, sendMessage, stopStreaming, newScene,
      tokenStats, permissionRequest, respondPermission,
    }}>
      {children}
    </ChatContext.Provider>
  )
}

// ── Hook ──

export function useChat() {
  const ctx = useContext(ChatContext)
  if (!ctx) {
    throw new Error('useChat must be used within <ChatProvider>')
  }
  return {
    messages: ctx.state.messages,
    streaming: ctx.state.streaming,
    error: ctx.state.error,
    contextInfo: ctx.state.contextInfo,
    sceneCount: ctx.state.sceneCount,
    toggles: ctx.toggles,
    setToggles: ctx.setToggles,
    sendMessage: ctx.sendMessage,
    stopStreaming: ctx.stopStreaming,
    newScene: ctx.newScene,
    tokenStats: ctx.tokenStats,
    permissionRequest: ctx.permissionRequest,
    respondPermission: ctx.respondPermission,
  }
}
