import { Archive, MoreHorizontal, Pencil, Pin, PinOff, Plus, Search, Trash2, X } from 'lucide-react'
import { type KeyboardEvent, useCallback, useEffect, useRef, useState } from 'react'
import { SessionSearchDialog } from '@/components/SessionSearchDialog'
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
import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'
import type { SessionSummary } from '@/types/chat'

interface SessionSidebarProps {
  sessions: SessionSummary[]
  currentThreadId: string
  onSwitch: (threadId: string) => void
  onDelete: (threadId: string) => void
  onRename: (threadId: string, title: string) => void
  onArchive: (threadId: string) => void
  onPin: (threadId: string, pinned: boolean) => void
  onCreate: () => void
  onClose: () => void
}

function formatDateTime(iso: string): string {
  if (!iso) return ''
  const date = new Date(iso)
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function sortSessions(sessions: SessionSummary[]): SessionSummary[] {
  const pinned = sessions
    .filter((s) => s.pinned_at)
    .sort((a, b) => ((a.pinned_at ?? '') < (b.pinned_at ?? '') ? -1 : 1))
  const unpinned = sessions.filter((s) => !s.pinned_at).sort((a, b) => (a.updated_at > b.updated_at ? -1 : 1))
  return [...pinned, ...unpinned]
}

export function SessionSidebar({
  sessions,
  currentThreadId,
  onSwitch,
  onDelete,
  onRename,
  onArchive,
  onPin,
  onCreate,
  onClose,
}: SessionSidebarProps) {
  const sorted = sortSessions(sessions)
  const [deleteTarget, setDeleteTarget] = useState<SessionSummary | null>(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const renameRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (renamingId) renameRef.current?.focus()
  }, [renamingId])

  const startRename = useCallback((session: SessionSummary) => {
    setRenamingId(session.thread_id)
    setRenameValue(session.title || '')
  }, [])

  const commitRename = useCallback(() => {
    if (!renamingId) return
    const trimmed = renameValue.trim()
    if (trimmed) {
      onRename(renamingId, trimmed)
    }
    setRenamingId(null)
    setRenameValue('')
  }, [renamingId, renameValue, onRename])

  const cancelRename = useCallback(() => {
    setRenamingId(null)
    setRenameValue('')
  }, [])

  const handleRenameKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault()
        commitRename()
      }
      if (e.key === 'Escape') {
        e.preventDefault()
        cancelRename()
      }
    },
    [commitRename, cancelRename],
  )

  return (
    <aside className="flex h-full w-[307px] shrink-0 flex-col border-r bg-muted/30">
      <div className="flex h-12 shrink-0 items-center justify-between border-b px-3">
        <div className="flex items-center gap-2">
          <img src="/favicon.svg" alt="OpenChatCi" className="h-5 w-5" />
          <span className="text-sm font-medium">OpenChatCi</span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setSearchOpen(true)}
            aria-label="Search sessions">
            <Search className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onCreate} aria-label="New session">
            <Plus className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose} aria-label="Close sidebar">
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {sorted.length === 0 && (
          <div className="flex items-center justify-center p-4 text-xs text-muted-foreground">No sessions yet</div>
        )}
        {sorted.map((session) => {
          const isActive = session.thread_id === currentThreadId
          const isRenaming = renamingId === session.thread_id
          return (
            <div
              key={session.thread_id}
              className={cn(
                'group flex w-full items-start gap-2 border-b border-border/30 px-3 py-2.5 transition-colors hover:bg-muted/50',
                isActive && 'bg-muted',
              )}>
              <button
                type="button"
                className="min-w-0 flex-1 cursor-pointer text-left"
                onClick={() => !isRenaming && onSwitch(session.thread_id)}>
                {isRenaming ? (
                  <input
                    ref={renameRef}
                    type="text"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={handleRenameKeyDown}
                    onBlur={commitRename}
                    className="w-full rounded border bg-background px-1.5 py-0.5 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  />
                ) : (
                  <>
                    <p className="flex items-center gap-1 truncate text-sm">
                      {session.pinned_at && <Pin className="h-3 w-3 shrink-0 text-muted-foreground" />}
                      {session.title || 'New session'}
                    </p>
                    <p className="flex items-center gap-1 text-xs text-muted-foreground">
                      <span className="truncate">
                        {formatDateTime(session.updated_at)}
                        {session.message_count > 0 && ` · ${session.message_count} msgs`}
                        {session.image_count > 0 && ` · ${session.image_count} imgs`}
                      </span>
                      {session.source === 'openai-api' && (
                        <span className="inline-block shrink-0 rounded px-1 py-0.5 text-[10px] font-medium leading-none bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300">
                          API
                        </span>
                      )}
                    </p>
                  </>
                )}
              </button>
              {!isRenaming && (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    {/* biome-ignore lint/a11y/useSemanticElements: nested interactive, span is intentional */}
                    <span
                      role="button"
                      tabIndex={-1}
                      className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md opacity-0 transition-opacity hover:bg-accent group-hover:opacity-100"
                      aria-label="Session options">
                      <MoreHorizontal className="h-3 w-3" />
                    </span>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-36">
                    <DropdownMenuItem onClick={() => onPin(session.thread_id, !session.pinned_at)}>
                      {session.pinned_at ? (
                        <>
                          <PinOff className="mr-2 h-3.5 w-3.5" />
                          Unpin
                        </>
                      ) : (
                        <>
                          <Pin className="mr-2 h-3.5 w-3.5" />
                          Pin
                        </>
                      )}
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => startRename(session)}>
                      <Pencil className="mr-2 h-3.5 w-3.5" />
                      Rename
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => onArchive(session.thread_id)}>
                      <Archive className="mr-2 h-3.5 w-3.5" />
                      Archive
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={() => setDeleteTarget(session)}>
                      <Trash2 className="mr-2 h-3.5 w-3.5" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          )
        })}
      </div>

      <AlertDialog open={deleteTarget !== null} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete session?</AlertDialogTitle>
            <AlertDialogDescription>
              &quot;{deleteTarget?.title || 'New session'}&quot; will be permanently deleted. This action cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (deleteTarget) {
                  onDelete(deleteTarget.thread_id)
                  setDeleteTarget(null)
                }
              }}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <SessionSearchDialog sessions={sessions} open={searchOpen} onOpenChange={setSearchOpen} onSelect={onSwitch} />
    </aside>
  )
}
