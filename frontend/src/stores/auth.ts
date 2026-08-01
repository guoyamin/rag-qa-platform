import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, getUserInfo } from '@/api/auth'
import router from '@/router'
import type { LoginForm, UserInfo } from '@/types'

export const useAuthStore = defineStore(
  'auth',
  () => {
    // State
    const token = ref<string>('')
    const refreshToken = ref<string>('')
    const userInfo = ref<UserInfo | null>(null)

    // Getters
    const isLoggedIn = computed(() => !!token.value)
    const isAdmin = computed(() => {
      const roles = ['super_admin', 'admin']
      return userInfo.value ? roles.includes(userInfo.value.role) : false
    })
    const displayName = computed(() => {
      return userInfo.value?.display_name || userInfo.value?.username || '用户'
    })

    // Actions
    async function login(form: LoginForm) {
      const res = await loginApi(form)
      if (res.code === 'SUCCESS') {
        token.value = res.data.access_token
        refreshToken.value = res.data.refresh_token
        // 获取用户信息
        await fetchUserInfo()
        return true
      }
      return false
    }

    async function fetchUserInfo() {
      const res = await getUserInfo()
      if (res.code === 'SUCCESS') {
        userInfo.value = res.data
        return true
      }
      return false
    }

    function logout() {
      token.value = ''
      refreshToken.value = ''
      userInfo.value = null
      router.push('/login')
    }

    return {
      token,
      refreshToken,
      userInfo,
      isLoggedIn,
      isAdmin,
      displayName,
      login,
      fetchUserInfo,
      logout,
    }
  },
  {
    persist: {
      key: 'rag_qa_auth',
      paths: ['token', 'refreshToken', 'userInfo'],
    },
  },
)
