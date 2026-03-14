import { Loader2, Mic, Paperclip, Plus, SendHorizonal, Square } from 'lucide-react'
import { type KeyboardEvent, useCallback, useRef, useState } from 'react'
import { ImageThumbnails } from '@/components/ImageThumbnails'
import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { WaveformVisualizer } from '@/components/WaveformVisualizer'
import type { ImageAttachment } from '@/hooks/useImageAttachment'
import { useVoiceInput } from '@/hooks/useVoiceInput'
import { cn } from '@/lib/utils'
import type { ImageRef } from '@/types/chat'

interface ChatInputProps {
  onSend: (message: string, images?: ImageRef[]) => void
  onStop: () => void
  isLoading: boolean
  attachments?: ImageAttachment[]
  onAddFiles?: (files: FileList) => void
  onRemoveAttachment?: (id: string) => void
  getImageRefs?: () => ImageRef[]
  isUploading?: boolean
}

export function ChatInput({
  onSend,
  onStop,
  isLoading,
  attachments = [],
  onAddFiles,
  onRemoveAttachment,
  getImageRefs,
  isUploading,
}: ChatInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleTranscribed = useCallback((text: string) => {
    setValue((prev) => {
      const separator = prev && !prev.endsWith(' ') ? ' ' : ''
      return prev + separator + text
    })
    requestAnimationFrame(() => {
      const textarea = textareaRef.current
      if (textarea) {
        textarea.style.height = 'auto'
        textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`
        textarea.focus()
      }
    })
  }, [])

  const {
    voiceState,
    waveformData,
    startRecording,
    stopRecording,
    error: voiceError,
  } = useVoiceInput(handleTranscribed)

  const handleSend = () => {
    if ((!value.trim() && attachments.length === 0) || isLoading || isUploading) return
    const images = getImageRefs?.()
    onSend(value, images && images.length > 0 ? images : undefined)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = () => {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`
  }

  const handleFileSelect = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0 && onAddFiles) {
      onAddFiles(files)
    }
    // Reset so the same file can be selected again
    e.target.value = ''
  }

  const isRecording = voiceState === 'recording'
  const isTranscribing = voiceState === 'transcribing'

  return (
    <div className="p-4 pb-5">
      <div className="mx-auto max-w-3xl">
        {isRecording ? (
          <WaveformVisualizer data={waveformData} onStop={stopRecording} />
        ) : (
          <div
            className={cn(
              'flex flex-col rounded-lg border bg-background',
              'ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2',
            )}>
            {onRemoveAttachment && <ImageThumbnails attachments={attachments} onRemove={onRemoveAttachment} />}
            <div className="flex items-end">
              {onAddFiles && (
                <>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/gif,image/webp"
                    multiple
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  <div className="flex shrink-0 items-center p-1">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button
                          type="button"
                          className={cn(
                            'inline-flex h-8 w-8 items-center justify-center rounded-md',
                            'text-muted-foreground hover:text-foreground',
                            'transition-colors',
                          )}
                          aria-label="Attach file">
                          <Plus className="h-4 w-4" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="start">
                        <DropdownMenuItem onClick={handleFileSelect}>
                          <Paperclip className="mr-2 h-4 w-4" />
                          Attach image
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </>
              )}
              <textarea
                ref={textareaRef}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                onKeyDown={handleKeyDown}
                onInput={handleInput}
                placeholder={isTranscribing ? 'Transcribing...' : 'Type a message...'}
                rows={1}
                className={cn(
                  'flex-1 resize-none bg-transparent px-3 py-2 text-sm',
                  'placeholder:text-muted-foreground',
                  'focus-visible:outline-none',
                  'disabled:cursor-not-allowed disabled:opacity-50',
                  !onAddFiles && 'pl-3',
                )}
                disabled={isLoading || isTranscribing}
              />
              <div className="flex shrink-0 items-center gap-0.5 p-1">
                {isLoading ? (
                  <Button
                    variant="destructive"
                    size="icon"
                    className="h-8 w-8"
                    onClick={onStop}
                    aria-label="Stop generation">
                    <Square className="h-4 w-4" />
                  </Button>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={startRecording}
                      disabled={isTranscribing}
                      className={cn(
                        'inline-flex h-8 w-8 items-center justify-center rounded-md',
                        'text-muted-foreground hover:text-foreground',
                        'disabled:pointer-events-none disabled:opacity-50',
                        'transition-colors',
                      )}
                      aria-label={isTranscribing ? 'Transcribing' : 'Voice input'}>
                      {isTranscribing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mic className="h-4 w-4" />}
                    </button>
                    <Button
                      size="icon"
                      className="h-8 w-8"
                      onClick={handleSend}
                      disabled={(!value.trim() && attachments.length === 0) || isTranscribing || isUploading}
                      aria-label="Send message">
                      <SendHorizonal className="h-4 w-4" />
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
        {voiceError && <p className="mt-1 text-xs text-destructive">{voiceError}</p>}
      </div>
    </div>
  )
}
