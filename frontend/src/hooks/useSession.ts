import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import type { ChatMessage, ImageRef, ReasoningBlock, SessionSummary, ToolCall, UsageInfo } from '@/types/chat'

const STORAGE_KEY = 'openchatci-thread-id'

/**
 * Convert MAF Message format to ChatMessage for display.
 * MAF stores: { role, contents: [{ type: "text", text: "..." }] }
 * Legacy sessions may use "text_content" / "reasoning_content" type names.
 */
function convertMafMessages(mafMessages: Record<string, unknown>[]): ChatMessage[] {
  const result: ChatMessage[] = []
  for (const msg of mafMessages) {
    const role = msg.role as string
    if (role !== 'user' && role !== 'assistant') continue

    const contents = msg.contents as Record<string, unknown>[] | undefined
    let text = ''
    const reasoningBlocks: ReasoningBlock[] = []
    const images: ImageRef[] = []
    if (contents) {
      for (const c of contents) {
        if ((c.type === 'text' || c.type === 'text_content') && typeof c.text === 'string') {
          text += c.text
        } else if ((c.type === 'text_reasoning' || c.type === 'reasoning_content') && typeof c.text === 'string') {
          reasoningBlocks.push({ id: crypto.randomUUID(), content: c.text, status: 'done' })
        } else if (c.type === 'image_url' && typeof c.uri === 'string') {
          images.push({ uri: c.uri as string, media_type: (c.media_type as string) || '' })
        }
      }
    }

    const rawToolCalls = msg.tool_calls as Record<string, unknown>[] | undefined
    const toolCalls: ToolCall[] = []
    if (rawToolCalls) {
      for (const tc of rawToolCalls) {
        toolCalls.push({
          id: (tc.id as string) ?? crypto.randomUUID(),
          name: (tc.name as string) ?? 'unknown',
          status: 'completed',
          ...(typeof tc.args === 'string' ? { args: tc.args } : {}),
          ...(typeof tc.result === 'string' ? { result: tc.result } : {}),
        })
      }
    }

    const rawUsage = msg.usage as Record<string, unknown> | undefined
    let usage: UsageInfo | undefined
    if (rawUsage && typeof rawUsage === 'object') {
      usage = rawUsage as UsageInfo
    }

    result.push({
      id: (msg.message_id as string) ?? crypto.randomUUID(),
      role: role as 'user' | 'assistant',
      content: text,
      createdAt: new Date().toISOString(),
      ...(reasoningBlocks.length > 0 ? { reasoningBlocks } : {}),
      ...(images.length > 0 ? { images } : {}),
      ...(toolCalls.length > 0 ? { toolCalls } : {}),
      ...(usage ? { usage } : {}),
    })
  }
  return result
}

export function useSession() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const sessionParam = searchParams.get('session')

  // If URL has ?session=xxx, use it. Otherwise start fresh.
  const [threadId, setThreadId] = useState<string>(() => {
    if (sessionParam) return sessionParam
    const newId = crypto.randomUUID()
    localStorage.setItem(STORAGE_KEY, newId)
    return newId
  })
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [initialMessages, setInitialMessages] = useState<ChatMessage[]>([])
  const [isSwitching, setIsSwitching] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const abortRef = useRef<(() => void) | null>(null)

  // Persist threadId to localStorage and sync URL
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, threadId)
  }, [threadId])

  // Fetch session list
  const refreshSessions = useCallback(async () => {
    try {
      const res = await fetch('/api/sessions')
      if (res.ok) {
        setSessions(await res.json())
      }
    } catch {
      // ignore fetch errors
    }
  }, [])

  // Load session list on mount
  useEffect(() => {
    refreshSessions()
  }, [refreshSessions])

  // Load initial messages when URL has ?session= parameter
  useEffect(() => {
    if (!sessionParam) return
    let cancelled = false
    async function load() {
      try {
        const res = await fetch(`/api/sessions/${sessionParam}`)
        if (!res.ok || cancelled) return
        const data = await res.json()
        const msgs = convertMafMessages(data.messages ?? [])
        if (!cancelled) setInitialMessages(msgs)
      } catch {
        if (!cancelled) setInitialMessages([])
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [sessionParam])

  // Register abort function for mid-stream session switch
  const registerAbort = useCallback((abortFn: () => void) => {
    abortRef.current = abortFn
  }, [])

  const createSession = useCallback(() => {
    abortRef.current?.()
    const newId = crypto.randomUUID()
    setInitialMessages([])
    setThreadId(newId)
    navigate('/chat', { replace: true })
    setSidebarOpen(false)
  }, [navigate])

  const switchSession = useCallback(
    async (targetThreadId: string) => {
      if (targetThreadId === threadId) {
        setSidebarOpen(false)
        return
      }

      abortRef.current?.()
      setIsSwitching(true)

      try {
        const res = await fetch(`/api/sessions/${targetThreadId}`)
        if (res.ok) {
          const data = await res.json()
          const msgs = convertMafMessages(data.messages ?? [])
          setInitialMessages(msgs)
        } else {
          setInitialMessages([])
        }
      } catch {
        setInitialMessages([])
      }

      setThreadId(targetThreadId)
      navigate(`/chat?session=${targetThreadId}`, { replace: true })
      setIsSwitching(false)
      setSidebarOpen(false)
    },
    [threadId, navigate],
  )

  const deleteSession = useCallback(
    async (targetThreadId: string) => {
      try {
        const res = await fetch(`/api/sessions/${targetThreadId}`, { method: 'DELETE' })
        if (res.ok) {
          setSessions((prev) => prev.filter((s) => s.thread_id !== targetThreadId))
          if (targetThreadId === threadId) {
            createSession()
          }
        }
      } catch {
        // ignore
      }
    },
    [threadId, createSession],
  )

  const forkSession = useCallback(
    async (sourceThreadId: string, upToIndex: number) => {
      try {
        const res = await fetch(`/api/sessions/${sourceThreadId}/fork`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ up_to_index: upToIndex }),
        })
        if (!res.ok) return
        const data = await res.json()
        const newThreadId = data.new_thread_id as string
        await switchSession(newThreadId)
        await refreshSessions()
      } catch {
        // ignore
      }
    },
    [switchSession, refreshSessions],
  )

  const renameSession = useCallback(async (targetThreadId: string, title: string) => {
    try {
      const res = await fetch(`/api/sessions/${targetThreadId}/rename`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
      })
      if (res.ok) {
        const data = await res.json()
        setSessions((prev) =>
          prev.map((s) => (s.thread_id === targetThreadId ? { ...s, title: data.title as string } : s)),
        )
      }
    } catch {
      // ignore
    }
  }, [])

  const archiveSession = useCallback(
    async (targetThreadId: string) => {
      try {
        const res = await fetch(`/api/sessions/${targetThreadId}/archive`, { method: 'POST' })
        if (res.ok) {
          setSessions((prev) => prev.filter((s) => s.thread_id !== targetThreadId))
          if (targetThreadId === threadId) {
            createSession()
          }
        }
      } catch {
        // ignore
      }
    },
    [threadId, createSession],
  )

  const pinSession = useCallback(async (targetThreadId: string, pinned: boolean) => {
    try {
      const res = await fetch(`/api/sessions/${targetThreadId}/pin`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pinned }),
      })
      if (res.ok) {
        const data = await res.json()
        setSessions((prev) =>
          prev.map((s) =>
            s.thread_id === targetThreadId ? { ...s, pinned_at: (data.pinned_at as string | null) ?? null } : s,
          ),
        )
      }
    } catch {
      // ignore
    }
  }, [])

  return {
    threadId,
    sessions,
    initialMessages,
    isSwitching,
    sidebarOpen,
    setSidebarOpen,
    createSession,
    switchSession,
    deleteSession,
    forkSession,
    renameSession,
    archiveSession,
    pinSession,
    refreshSessions,
    registerAbort,
  }
}
