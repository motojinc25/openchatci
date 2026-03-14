import { ImageIcon } from 'lucide-react'
import { type DragEvent, useCallback, useRef, useState } from 'react'
import { ChatInput } from '@/components/ChatInput'
import { ChatMessageItem } from '@/components/ChatMessageItem'
import { useChat } from '@/hooks/useChat'
import { useImageAttachment } from '@/hooks/useImageAttachment'
import { cn } from '@/lib/utils'
import type { ChatMessage, ImageRef } from '@/types/chat'

interface ChatPanelProps {
  compact?: boolean
  emptyMessage?: string
  className?: string
  threadId?: string
  initialMessages?: ChatMessage[]
  onStreamComplete?: () => void
  onBranchFromMessage?: (messageIndex: number) => void
}

function useAutoScroll(messages: ChatMessage[], isLoading: boolean) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const prevKey = useRef('')

  const lastMsg = messages.at(-1)
  const toolCallCount = lastMsg?.toolCalls?.length ?? 0
  const lastToolStatus = lastMsg?.toolCalls?.at(-1)?.status ?? ''
  const key = `${messages.length}:${lastMsg?.content?.length ?? 0}:${toolCallCount}:${lastToolStatus}:${lastMsg?.reasoningBlocks?.length ?? 0}:${isLoading}`

  if (prevKey.current !== key) {
    prevKey.current = key
    requestAnimationFrame(() => {
      const el = scrollRef.current
      if (el) el.scrollTop = el.scrollHeight
    })
  }
  return scrollRef
}

export function ChatPanel({
  compact,
  emptyMessage = 'How can I help you today?',
  className,
  threadId,
  initialMessages,
  onStreamComplete,
  onBranchFromMessage,
}: ChatPanelProps) {
  const {
    messages,
    isLoading,
    sendMessage,
    stopGeneration,
    editUserMessage,
    regenerateAssistantMessage,
    editAssistantMessage,
    deleteMessage,
  } = useChat({
    threadId,
    initialMessages,
    onStreamComplete,
  })

  const { attachments, addFiles, removeAttachment, clearAttachments, getImageRefs, isUploading } = useImageAttachment()

  const [isDragging, setIsDragging] = useState(false)
  const dragCountRef = useRef(0)

  const scrollRef = useAutoScroll(messages, isLoading)

  const handleSend = useCallback(
    (content: string, images?: ImageRef[]) => {
      sendMessage(content, images)
      clearAttachments()
    },
    [sendMessage, clearAttachments],
  )

  const handleAddFiles = useCallback(
    (files: FileList) => {
      if (threadId) addFiles(files, threadId)
    },
    [addFiles, threadId],
  )

  const handleDragEnter = useCallback((e: DragEvent) => {
    e.preventDefault()
    dragCountRef.current++
    if (e.dataTransfer.types.includes('Files')) {
      setIsDragging(true)
    }
  }, [])

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault()
    dragCountRef.current--
    if (dragCountRef.current === 0) {
      setIsDragging(false)
    }
  }, [])

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault()
  }, [])

  const handleDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault()
      dragCountRef.current = 0
      setIsDragging(false)
      const files = e.dataTransfer.files
      if (files.length > 0 && threadId) {
        addFiles(files, threadId)
      }
    },
    [addFiles, threadId],
  )

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: drag-and-drop drop zone requires drag events on container div
    <div
      className={cn('relative flex flex-1 flex-col overflow-hidden', className)}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}>
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className={cn('mx-auto px-4 pt-4', compact ? 'max-w-full pb-4' : 'max-w-3xl pb-36')}>
          {messages.length === 0 && (
            <div
              className={cn('flex items-center justify-center text-muted-foreground', compact ? 'h-40' : 'h-[60vh]')}>
              <p className={cn(compact ? 'text-xs' : 'text-sm')}>{emptyMessage}</p>
            </div>
          )}
          {messages.map((msg, i) => (
            <ChatMessageItem
              key={msg.id}
              message={msg}
              compact={compact}
              isLoading={isLoading && i === messages.length - 1}
              onEditUser={editUserMessage}
              onEditAssistant={editAssistantMessage}
              onRegenerateAssistant={regenerateAssistantMessage}
              onDelete={deleteMessage}
              onBranch={onBranchFromMessage ? () => onBranchFromMessage(i) : undefined}
            />
          ))}
        </div>
      </div>

      {compact ? (
        <ChatInput
          onSend={handleSend}
          onStop={stopGeneration}
          isLoading={isLoading}
          attachments={attachments}
          onAddFiles={handleAddFiles}
          onRemoveAttachment={removeAttachment}
          getImageRefs={getImageRefs}
          isUploading={isUploading}
        />
      ) : (
        <div className="absolute inset-x-0 bottom-0 z-20">
          <div className="pointer-events-none bg-gradient-to-t from-background from-60% to-transparent pt-6" />
          <div className="relative bg-background">
            <ChatInput
              onSend={handleSend}
              onStop={stopGeneration}
              isLoading={isLoading}
              attachments={attachments}
              onAddFiles={handleAddFiles}
              onRemoveAttachment={removeAttachment}
              getImageRefs={getImageRefs}
              isUploading={isUploading}
            />
          </div>
        </div>
      )}

      {isDragging && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-3 rounded-xl border-2 border-dashed border-primary p-12">
            <ImageIcon className="h-10 w-10 text-primary" />
            <p className="text-sm font-medium text-primary">Drop images here to attach</p>
          </div>
        </div>
      )}
    </div>
  )
}
