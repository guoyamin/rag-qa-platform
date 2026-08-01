/**
 * 模型管理 API
 */
import request from './request'

// ========== API Key ==========

export interface ApiKeyItem {
  id: string
  name: string
  provider: string
  usage: 'llm' | 'embedding' | 'both'
  status: 'active' | 'inactive' | 'expired'
  key_preview: string
  expires_at: string | null
  description: string | null
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface CreateApiKeyRequest {
  name: string
  provider: string
  api_key: string
  usage: 'llm' | 'embedding' | 'both'
  expires_at?: string
  description?: string
}

export interface CreateApiKeyResponse extends ApiKeyItem {
  api_key: string // 明文，仅创建时返回
}

export const createApiKey = (data: CreateApiKeyRequest) =>
  request.post<CreateApiKeyResponse>('/models/keys', data)

export const listApiKeys = (params?: {
  page?: number
  page_size?: number
  provider?: string
  usage?: string
  status?: string
}) => request.get<{ items: ApiKeyItem[]; total: number }>('/models/keys', { params })

export const getApiKey = (id: string) => request.get<ApiKeyItem>(`/models/keys/${id}`)

export const updateApiKey = (id: string, data: Partial<CreateApiKeyRequest>) =>
  request.put<ApiKeyItem>(`/models/keys/${id}`, data)

export const deleteApiKey = (id: string) => request.delete(`/models/keys/${id}`)

export const rotateApiKey = (id: string) =>
  request.post<CreateApiKeyResponse>(`/models/keys/${id}/rotate`)

export const checkVaultHealth = () => request.get('/models/vault/health')

// ========== 模型实例 ==========

export interface ModelConfig {
  model: string
  api_base?: string
  temperature: number
  max_tokens: number
  top_p?: number
  timeout: number
}

export interface ModelInstance {
  id: string
  name: string
  provider: string
  api_key_id: string | null
  model_type: string
  config: ModelConfig
  status: 'active' | 'inactive' | 'maintenance'
  description: string | null
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface CreateModelRequest {
  name: string
  provider: string
  api_key_id?: string
  model_type?: string
  config: ModelConfig
  description?: string
}

export const createModel = (data: CreateModelRequest) =>
  request.post<ModelInstance>('/models', data)

export const listModels = (params?: {
  page?: number
  page_size?: number
  provider?: string
  model_type?: string
  status?: string
}) =>
  request.get<{ items: ModelInstance[]; total: number; page: number; page_size: number }>(
    '/models',
    { params },
  )

export const getModel = (id: string) => request.get<ModelInstance>(`/models/${id}`)

export const updateModel = (id: string, data: Partial<CreateModelRequest>) =>
  request.put<ModelInstance>(`/models/${id}`, data)

export const toggleModel = (id: string) => request.post<ModelInstance>(`/models/${id}/toggle`)

export const deleteModel = (id: string) => request.delete(`/models/${id}`)

export interface CompareRequest {
  question: string
  model_ids: string[]
}

export interface CompareResult {
  model_id: string
  model_name: string
  response: string
  latency_ms: number
  input_tokens: number
  output_tokens: number
  success: boolean
  error: string | null
}

export const compareModels = (data: CompareRequest) =>
  request.post<{ question: string; results: CompareResult[] }>('/models/compare', data)

// ========== 健康检查 ==========

export interface ModelHealth {
  model_id: string
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
  latency_ms: number | null
  error_message: string | null
  checked_at: string | null
}

export const getModelsHealth = () => request.get<ModelHealth[]>('/health/models')

export const getHealthSummary = () =>
  request.get<{
    total_models: number
    healthy_count: number
    degraded_count: number
    unhealthy_count: number
    unknown_count: number
  }>('/health/summary')

// ========== 用量统计 ==========

export const getUsageStats = (params?: { model_id?: string; days?: number }) =>
  request.get<{
    total_tokens: number
    input_tokens: number
    output_tokens: number
    total_cost: number
    total_calls: number
    success_calls: number
    failed_calls: number
  }>('/stats/usage', { params })

export const getModelRanking = (params?: { days?: number; limit?: number }) =>
  request.get<{
    items: { model_id: string; total_tokens: number; total_cost: number; total_calls: number }[]
  }>('/stats/models/ranking', { params })

// ========== 模板管理 ==========

export interface Template {
  id: string
  name: string
  template_type: string
  description: string | null
  template: Record<string, any>
  is_default: boolean
  is_active: boolean
  tags: string[]
  category: string | null
  version: string
  created_by: string | null
  created_at: string
}

export const listTemplates = (params?: {
  template_type?: string
  category?: string
  is_active?: boolean
  page?: number
  page_size?: number
}) =>
  request.get<{ items: Template[]; total: number; page: number; page_size: number }>(
    '/models/templates',
    { params },
  )

export const createTemplate = (data: {
  name: string
  template_type: string
  template: Record<string, any>
  description?: string
  is_default?: boolean
  tags?: string[]
  category?: string
}) => request.post<Template>('/models/templates', data)

export const updateTemplate = (
  id: string,
  data: Partial<{
    name: string
    template: Record<string, any>
    description: string
    is_default: boolean
    is_active: boolean
    tags: string[]
    category: string
  }>,
) => request.put<Template>(`/models/templates/${id}`, data)

export const deleteTemplate = (id: string) => request.delete(`/models/templates/${id}`)
