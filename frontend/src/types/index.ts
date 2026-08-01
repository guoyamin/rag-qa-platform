// ==================== 通用类型 ====================

export interface ApiResponse<T = any> {
  code: string
  message: string
  data: T
}

export interface ListResponse<T = any> {
  code: string
  message: string
  data: T[]
  total: number
  page: number
  page_size: number
}

export interface PaginationParams {
  page?: number
  page_size?: number
}

// ==================== 认证相关 ====================

export interface LoginForm {
  username: string
  password: string
  auth_type?: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface UserInfo {
  id: string
  username: string
  email?: string
  phone?: string
  display_name?: string
  avatar?: string
  role: string
  auth_type: string
  status: string
  department?: string
  position?: string
  last_login_at?: string
  login_count: number
  created_at: string
}

// ==================== 聊天相关 ====================

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  sources?: SourceInfo[]
  created_at: string
  tokens_used?: number
  latency_ms?: number
  is_liked?: boolean | null
}

export interface SourceInfo {
  document_id: string
  chunk_index: number
  score: number
  content_preview: string
}

export interface ChatRequest {
  message: string
  session_id?: string
  kb_ids?: string[]
  stream?: boolean
}

export interface ChatSession {
  id: string
  title?: string
  kb_ids?: string
  message_count: number
  created_at: string
  updated_at: string
}

// ==================== 知识库相关 ====================

export interface KnowledgeBase {
  id: string
  name: string
  description?: string
  document_count: number
  chunk_count: number
  created_by: string
  created_at: string
  updated_at: string
}

export interface DocumentInfo {
  id: string
  kb_id: string
  title: string
  doc_type: string
  file_size?: number
  status: string
  chunk_count: number
  vector_count: number
  error_message?: string
  processed_at?: string
  created_at: string
}
