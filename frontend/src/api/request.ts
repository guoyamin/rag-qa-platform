import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

// 创建axios实例
const request: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
request.interceptors.request.use(
  config => {
    const authStore = useAuthStore()
    if (authStore.token) {
      config.headers.Authorization = `Bearer ${authStore.token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  },
)

// 防止并发刷新
let isRefreshing = false
const retriedConfigs = new WeakSet<AxiosRequestConfig>()

// 响应拦截器
request.interceptors.response.use(
  (response: AxiosResponse) => {
    const { data } = response
    // 业务错误处理
    if (data.code && data.code !== 'SUCCESS') {
      ElMessage.error(data.message || '请求失败')
      return Promise.reject(new Error(data.message))
    }
    return data
  },
  async error => {
    const { response, config } = error

    // 登录/刷新接口的 401 直接抛出，由调用方处理（避免循环 refresh）
    const isAuthRequest =
      config?.url?.includes('/auth/login') || config?.url?.includes('/auth/refresh')
    if (isAuthRequest) {
      return Promise.reject(error)
    }

    // 其他 401：尝试用 refreshToken 续期后重试一次（避免直接登出）
    if (response?.status === 401 && config && !retriedConfigs.has(config)) {
      const authStore = useAuthStore()
      if (authStore.refreshToken && !isRefreshing) {
        isRefreshing = true
        try {
          // 用裸 axios 调用，绕过自身拦截器避免循环
          const res = await axios.post(`${request.defaults.baseURL || '/api/v1'}/auth/refresh`, {
            refresh_token: authStore.refreshToken,
          })
          if (res.data?.code === 'SUCCESS') {
            authStore.token = res.data.data.access_token
            authStore.refreshToken = res.data.data.refresh_token
            retriedConfigs.add(config)
            config.headers.Authorization = `Bearer ${authStore.token}`
            return request(config)
          }
        } catch {
          // refresh 失败，走登出流程
        } finally {
          isRefreshing = false
        }
      }
      authStore.logout()
      ElMessage.error('登录已过期，请重新登录')
      return Promise.reject(error)
    }

    if (response) {
      switch (response.status) {
        case 403:
          ElMessage.error('权限不足')
          break
        case 404:
          ElMessage.error('请求的资源不存在')
          break
        case 500:
          ElMessage.error('服务器错误')
          break
        default:
          ElMessage.error(response.data?.message || '网络错误')
      }
    } else {
      ElMessage.error('网络连接失败')
    }
    return Promise.reject(error)
  },
)

// 响应拦截器已解包返回 response.data，故方法返回 Promise<T> 而非 Promise<AxiosResponse<T>>
interface UnwrappedAxios {
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>
  patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
}

export default request as unknown as UnwrappedAxios
