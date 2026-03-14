import { Bot, Check, Copy, GitBranch, Pencil, RefreshCw, Trash2, User } from 'lucide-react'
import { type KeyboardEvent, useCallback, useEffect, useRef, useState } from 'react'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import { ReasoningIndicator } from '@/components/ReasoningIndicator'
import { ToolCallIndicator } from '@/components/ToolCallIndicator'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { WeatherToolResults } from '@/components/WeatherCard'
import { cn } from '@/lib/utils'
import type { ChatMessage } from '@/types/chat'

interface ChatMessageItemProps {
  message: ChatMessage
  compact?: boolean
  isLoading?: boolean
  onEditUser?: (messageId: string, newContent: string) => void
  onEditAssistant?: (messageId: string, newContent: string) => void
  onRegenerateAssistant?: (messageId: string) => void
  onDelete?: (messageId: string) => void
  onBranch?: () => void
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [text])

  return (
    <Button
      variant="ghost"
      size="icon"
      className="h-6 w-6 text-muted-foreground hover:text-foreground"
      onClick={handleCopy}
      aria-label="Copy message">
      {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
    </Button>
  )
}

export function ChatMessageItem({
  message,
  compact,
  isLoading,
  onEditUser,
  onEditAssistant,
  onRegenerateAssistant,
  onDelete,
  onBranch,
}: ChatMessageItemProps) {
  const isUser = message.role === 'user'
  const isWaiting = !isUser && isLoading && !message.content
  const [editing, setEditing] = useState(false)
  const [editValue, setEditValue] = useState('')
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const editRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (editing) editRef.current?.focus()
  }, [editing])

  const handleStartEdit = useCallback(() => {
    setEditValue(message.content)
    setEditing(true)
  }, [message.content])

  const handleSubmitEdit = useCallback(() => {
    const trimmed = editValue.trim()
    if (!trimmed || trimmed === message.content) {
      setEditing(false)
      return
    }
    if (isUser && onEditUser) {
      onEditUser(message.id, trimmed)
    } else if (!isUser && onEditAssistant) {
      onEditAssistant(message.id, trimmed)
    }
    setEditing(false)
  }, [editValue, message.content, message.id, isUser, onEditUser, onEditAssistant])

  const handleEditKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSubmitEdit()
      }
      if (e.key === 'Escape') {
        setEditing(false)
      }
    },
    [handleSubmitEdit],
  )

  const handleRegenerate = useCallback(() => {
    onRegenerateAssistant?.(message.id)
  }, [onRegenerateAssistant, message.id])

  const renderEditForm = () => (
    <div className="flex flex-col gap-2">
      <textarea
        ref={editRef}
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onKeyDown={handleEditKeyDown}
        className="w-full resize-none rounded-lg border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        rows={3}
      />
      <div className="flex gap-2">
        <Button size="sm" onClick={handleSubmitEdit}>
          Submit
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
          Cancel
        </Button>
      </div>
    </div>
  )

  return (
    <div className={cn('group/msg flex gap-3', compact ? 'px-3 py-2' : 'px-4 py-2')}>
      <Avatar className={cn('mt-0.5 shrink-0', compact ? 'h-6 w-6' : 'h-7 w-7')}>
        <AvatarFallback className={cn(isUser ? 'bg-primary text-primary-foreground' : 'bg-muted')}>
          {isUser ? (
            <User className={cn(compact ? 'h-3 w-3' : 'h-3.5 w-3.5')} />
          ) : (
            <Bot className={cn(compact ? 'h-3 w-3' : 'h-3.5 w-3.5')} />
          )}
        </AvatarFallback>
      </Avatar>
      <div className={cn('min-w-0 flex-1 text-sm leading-relaxed')}>
        {editing ? (
          renderEditForm()
        ) : isUser ? (
          <div>
            {message.images && message.images.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-2">
                {message.images.map((img) => (
                  <img
                    key={img.uri}
                    src={img.uri}
                    alt="Attached"
                    className="max-h-48 max-w-xs rounded-lg border object-contain"
                  />
                ))}
              </div>
            )}
            <div className="whitespace-pre-wrap">{message.content}</div>
          </div>
        ) : (
          <>
            {message.reasoningBlocks && message.reasoningBlocks.length > 0 && (
              <ReasoningIndicator reasoningBlocks={message.reasoningBlocks} />
            )}
            <ToolCallIndicator toolCalls={message.toolCalls} isWaiting={isWaiting} />
            {message.toolCalls && message.toolCalls.length > 0 && <WeatherToolResults toolCalls={message.toolCalls} />}
            {message.content ? (
              <MarkdownRenderer content={message.content} />
            ) : (
              !isWaiting && <span className="inline-block h-4 w-1 animate-pulse bg-current" />
            )}
          </>
        )}

        {!isLoading && !editing && message.content && (
          <div className="mt-0.5 flex gap-0.5 opacity-0 transition-opacity group-hover/msg:opacity-100">
            <CopyButton text={message.content} />
            {(isUser ? onEditUser : onEditAssistant) && (
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground hover:text-foreground"
                onClick={handleStartEdit}
                aria-label="Edit message">
                <Pencil className="h-3 w-3" />
              </Button>
            )}
            {!isUser && onRegenerateAssistant && (
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground hover:text-foreground"
                onClick={handleRegenerate}
                aria-label="Regenerate response">
                <RefreshCw className="h-3 w-3" />
              </Button>
            )}
            {!isUser && onBranch && (
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground hover:text-foreground"
                onClick={onBranch}
                aria-label="Branch in new chat">
                <GitBranch className="h-3 w-3" />
              </Button>
            )}
            {onDelete && (
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground hover:text-destructive"
                onClick={() => setDeleteConfirmOpen(true)}
                aria-label="Delete message">
                <Trash2 className="h-3 w-3" />
              </Button>
            )}
            {!isUser && message.usage && (
              <span className="ml-1 text-[11px] tabular-nums text-muted-foreground/60">
                {message.usage.input_token_count?.toLocaleString() ?? '?'}in /{' '}
                {message.usage.output_token_count?.toLocaleString() ?? '?'}out
              </span>
            )}
          </div>
        )}

        <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete this message?</AlertDialogTitle>
              <AlertDialogDescription>This action cannot be undone.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                onClick={() => onDelete?.(message.id)}>
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  )
}
