/**
 * 聊天 API
 * 类型派生自 OpenAPI 生成（@/api/types）+ 本地补充 completions 返回结构。
 */
import type { components } from '@/api/types'
import type { ApiResponse, ChatRequest } from '@/types'
import request from './request'

export type ChatFeedbackRequest = components['schemas']['ChatFeedbackRequest']

/** /chat/completions 返回的 data 结构（含 message_id 供反馈使用） */
export interface ChatCompletionData {
  answer: string
  sources: Array<{
    document_id: string
    chunk_index: number
    score: number
    content_preview: string
  }>
  tokens_used: number
  latency_ms: number
  session_id: string
  message_id: string
}

/** 智能问答（非流式），返回含 message_id/session_id */
export function chatCompletion(data: ChatRequest): Promise<ApiResponse<ChatCompletionData>> {
  return request.post('/chat/completions', data)
}

/** 提交消息反馈（点赞/点踩 + 文字反馈） */
export function submitFeedback(data: ChatFeedbackRequest): Promise<ApiResponse<null>> {
  return request.post('/chat/feedback', data)
}
