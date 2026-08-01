import request from './request'
import type { LoginForm, LoginResponse, ApiResponse, UserInfo } from '@/types'

export function login(data: LoginForm): Promise<ApiResponse<LoginResponse>> {
  return request.post('/auth/login', data)
}

export function getUserInfo(): Promise<ApiResponse<UserInfo>> {
  return request.get('/auth/me')
}

export function logout(): Promise<ApiResponse<null>> {
  return request.post('/auth/logout')
}

export function refreshToken(refreshToken: string): Promise<ApiResponse<LoginResponse>> {
  return request.post('/auth/refresh', { refresh_token: refreshToken })
}

export function changePassword(data: { old_password: string; new_password: string }) {
  return request.post('/auth/password/change', data)
}
