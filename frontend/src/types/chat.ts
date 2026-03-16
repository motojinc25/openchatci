export interface ToolCall {
  id: string
  name: string
  status: 'running' | 'completed'
  args?: string
  result?: string
}

export interface ReasoningBlock {
  id: string
  content: string
  status: 'thinking' | 'done'
}

export interface ImageRef {
  uri: string
  media_type: string
}

export interface UsageInfo {
  input_token_count?: number
  output_token_count?: number
  total_token_count?: number
  max_context_tokens?: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  createdAt: string
  toolCalls?: ToolCall[]
  reasoningBlocks?: ReasoningBlock[]
  images?: ImageRef[]
  usage?: UsageInfo
}

export interface PromptTemplate {
  id: string
  name: string
  description: string
  category: string
  body: string
  created_at: string
  updated_at: string
}

export interface SessionSummary {
  thread_id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
  image_count: number
  pinned_at: string | null
}
