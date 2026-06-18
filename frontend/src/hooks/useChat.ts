import { useReducer, useRef, useCallback, useEffect } from 'react'

interface ToolCall {
  name: string
  args: Record<string, unknown>
}

interface ToolResult {
  name: string
  result: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'tool_call' | 'tool_result' | 'system' | 'inject'
  content: string
  toolName?: string
  toolArgs?: Record<string, unknown>
  toolResult?: string
}

interface ChatState {
  messages: ChatMessage[]
  streaming: boolean
  error: string | null
}

type ChatAction =
  | { type: 'ADD_USER'; content: string }
  | { type: 'APPEND_TEXT'; content: string }
  | { type: 'ADD_TOOL_CALL'; name: string; args: Record<string, unknown> }
  | { type: 'ADD_TOOL_RESULT'; name: string; result: string }
  | { type: 'ADD_INJECT'; items: string[] }
  | { type: 'ADD_SYSTEM'; content: string }
  | { type: 'SET_DONE' }
  | { type: 'SET_ERROR'; content: string }
  | { type: 'RESET' }

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
        messages: [...state.messages, { id: nextId(), role: 'user', content: action.content }],
      }
    }
    case 'APPEND_TEXT': {
      const msgs = [...state.messages]
      const last = msgs[msgs.length - 1]
      if (last && last.role === 'assistant') {
        msgs[msgs.length - 1] = { ...last, content: last.content + action.content }
      } else {
        msgs.push({ id: nextId(), role: 'assistant', content: action.content })
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
            toolName: action.name,
            toolResult: action.result,
          },
        ],
      }
    }
    case 'ADD_INJECT': {
      const infoIcon = '\u{1F4CE}'
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: nextId(),
            role: 'system',
            content: `${infoIcon} ${action.items.join(' | ')}`,
          },
        ],
      }
    }
    case 'ADD_SYSTEM': {
      return {
        ...state,
        messages: [...state.messages, { id: nextId(), role: 'system', content: action.content }],
      }
    }
    case 'SET_DONE': {
      return { ...state, streaming: false }
    }
    case 'SET_ERROR': {
      return { ...state, streaming: false, error: action.content }
    }
    case 'RESET': {
      return { messages: [], streaming: false, error: null }
    }
    default:
      return state
  }
}

export function useChat() {
  const [state, dispatch] = useReducer(chatReducer, { messages: [], streaming: false, error: null })
  const wsRef = useRef<WebSocket | null>(null)
  const convIdRef = useRef<string>('')

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/api/chat/ws`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        switch (data.type) {
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
          case 'error':
            dispatch({ type: 'SET_ERROR', content: data.content })
            break
        }
      } catch {
        /* ignore malformed */
      }
    }

    ws.onerror = () => {
      dispatch({ type: 'SET_ERROR', content: 'WebSocket 连接失败' })
    }

    ws.onclose = () => {
      if (state.streaming) {
        dispatch({ type: 'SET_DONE' })
      }
    }

    return ws
  }, [])

  useEffect(() => {
    const ws = connect()
    return () => {
      ws.close()
    }
  }, [connect])

  const sendMessage = useCallback(
    (content: string, modelId: string, role: string, toggles: Record<string, boolean>) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        // Reconnect
        const ws = connect()
        ws.onopen = () => {
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
        }
        return
      }
      dispatch({ type: 'ADD_USER', content })
      wsRef.current.send(
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

  const resetChat = useCallback(() => {
    dispatch({ type: 'RESET' })
    convIdRef.current = ''
  }, [])

  return {
    messages: state.messages,
    streaming: state.streaming,
    error: state.error,
    sendMessage,
    stopStreaming,
    resetChat,
  }
}
