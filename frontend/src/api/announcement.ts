/**
 * 公告管理 API
 * 类型派生自 OpenAPI 生成（@/api/types），后端改 schema → vue-tsc 报错。
 */
import type { components } from '@/api/types'
import request from './request'

// 从生成契约派生类型（本模块为首个直接消费 types.d.ts 的 api 模块）
export type AnnouncementType = components['schemas']['AnnouncementType']
export type AnnouncementStatus = components['schemas']['AnnouncementStatus']
export type AnnouncementItem = components['schemas']['AnnouncementResponse']
export type AnnouncementListResponse = components['schemas']['AnnouncementListResponse']
export type CreateAnnouncementRequest = components['schemas']['AnnouncementCreate']
export type UpdateAnnouncementRequest = components['schemas']['AnnouncementUpdate']

export const listAnnouncements = (params?: {
  page?: number
  page_size?: number
  status?: AnnouncementStatus
  type?: AnnouncementType
}) => request.get<AnnouncementListResponse>('/announcements', { params })

export const getAnnouncement = (id: string) => request.get<AnnouncementItem>(`/announcements/${id}`)

export const createAnnouncement = (data: CreateAnnouncementRequest) =>
  request.post<AnnouncementItem>('/announcements', data)

export const updateAnnouncement = (id: string, data: UpdateAnnouncementRequest) =>
  request.put<AnnouncementItem>(`/announcements/${id}`, data)

export const deleteAnnouncement = (id: string) => request.delete(`/announcements/${id}`)

export const publishAnnouncement = (id: string) =>
  request.put<AnnouncementItem>(`/announcements/${id}/publish`)
