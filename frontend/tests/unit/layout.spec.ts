/**
 * 主布局组件 (LayoutView) 单元测试
 *
 * 生成信息:
 * - AI辅助生成: 是
 * - 生成日期: 2026-08-01
 * 版本: V1.0
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import Layout from '@/views/layout/index.vue'

// jsdom 缺少 ResizeObserver, 部分 Element Plus 组件依赖它, 提供空实现避免报错
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal('ResizeObserver', ResizeObserverStub)

// ---------- 外部依赖隔离 ----------

type MockRoute = { path: string; meta: Record<string, unknown> }

// 1) vue-router: 仅 mock useRoute, RouterView 通过 stub 提供
vi.mock('vue-router', () => ({
  useRoute: vi.fn((): MockRoute => ({ path: '/chat', meta: { title: '智能问答' } })),
}))

// 2) @vueuse/core: useDark 返回可控 ref, useToggle 返回可断言的 mock 函数
const themeMocks = vi.hoisted(() => ({
  toggleDark: vi.fn(),
  isDarkRef: null as { value: boolean } | null,
}))
vi.mock('@vueuse/core', async () => {
  const { ref } = await import('vue')
  themeMocks.isDarkRef = ref(false)
  return {
    useDark: vi.fn(() => themeMocks.isDarkRef),
    useToggle: vi.fn(() => themeMocks.toggleDark),
  }
})

// 3) auth store: useAuthStore 返回可控的假 store, 隔离真实 store / API / 路由
vi.mock('@/stores/auth', () => ({
  useAuthStore: vi.fn(),
}))

// 4) 路由表: 提供确定性的菜单数据, 隔离真实路由模块 (使用 hoisted 可变数组以支持边界用例)
const routerMocks = vi.hoisted(() => ({
  routes: [
    { path: '/login', name: 'Login', meta: { public: true } },
    {
      path: '/',
      name: 'Layout',
      redirect: '/chat',
      children: [
        { path: '/chat', name: 'Chat', meta: { title: '智能问答', icon: 'ChatDotRound' } },
        {
          path: '/knowledge',
          name: 'Knowledge',
          meta: { title: '知识库管理', icon: 'Collection', admin: true },
        },
        {
          path: '/documents',
          name: 'Documents',
          meta: { title: '文档管理', icon: 'Document', admin: true },
        },
        { path: '/hidden', name: 'Hidden', meta: { title: '隐藏菜单', hidden: true } },
      ],
    },
    { path: '/:pathMatch(.*)*', name: 'NotFound', meta: { public: true } },
  ],
}))
vi.mock('@/router', () => ({
  routes: routerMocks.routes,
}))

// 5) element-plus: 保留真实组件 (ElMenu/ElDropdown 等), 仅 mock 命令式 API
vi.mock('element-plus', async importOriginal => {
  const actual = (await importOriginal()) as any
  return {
    ...actual,
    ElMessage: { info: vi.fn(), success: vi.fn(), error: vi.fn(), warning: vi.fn() },
    ElMessageBox: { confirm: vi.fn() },
  }
})

// ---------- 辅助函数 ----------

interface MockAuthStore {
  displayName: string
  isAdmin: boolean
  logout: ReturnType<typeof vi.fn>
}

function mockAuthStore(overrides: Partial<MockAuthStore> = {}): MockAuthStore {
  const store: MockAuthStore = {
    displayName: '测试用户',
    isAdmin: false,
    logout: vi.fn(),
    ...overrides,
  }
  vi.mocked(useAuthStore).mockReturnValue(store)
  return store
}

function mockRoute(path: string, meta: Record<string, unknown> = {}): void {
  vi.mocked(useRoute).mockReturnValue({ path, meta })
}

function mountLayout() {
  return mount(Layout, {
    global: {
      plugins: [ElementPlus],
      stubs: {
        RouterView: { name: 'RouterView', template: '<div class="mock-router-view" />' },
      },
    },
  })
}

// ---------- 测试用例 ----------

describe('LayoutView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockRoute('/chat', { title: '智能问答' })
    mockAuthStore()
    if (themeMocks.isDarkRef) themeMocks.isDarkRef.value = false
  })

  describe('渲染', () => {
    it('渲染主布局结构: 侧边栏、顶栏与主内容区', () => {
      const wrapper = mountLayout()

      expect(wrapper.find('.sidebar').exists()).toBe(true)
      expect(wrapper.find('.topbar').exists()).toBe(true)
      expect(wrapper.find('.main-content').exists()).toBe(true)
    })

    it('渲染 logo 文本 "知识问答"', () => {
      const wrapper = mountLayout()

      expect(wrapper.find('.logo-text').text()).toBe('知识问答')
    })

    it('显示当前登录用户的显示名', () => {
      mockAuthStore({ displayName: '张三' })
      const wrapper = mountLayout()

      expect(wrapper.find('.user-name').text()).toBe('张三')
    })

    it('面包屑展示当前路由标题', () => {
      mockRoute('/chat', { title: '智能问答' })
      const wrapper = mountLayout()

      expect(wrapper.find('.el-breadcrumb').text()).toContain('智能问答')
    })

    it('路由无 title 时面包屑回退为默认平台名', () => {
      mockRoute('/unknown', {})
      const wrapper = mountLayout()

      expect(wrapper.find('.el-breadcrumb').text()).toContain('智能问答平台')
    })
  })

  describe('菜单过滤', () => {
    it('普通用户仅可见非管理员菜单', () => {
      mockAuthStore({ isAdmin: false })
      const wrapper = mountLayout()
      const titles = wrapper.findAll('.el-menu-item').map(w => w.text())

      expect(titles).toContain('智能问答')
      expect(titles).not.toContain('知识库管理')
      expect(titles).not.toContain('文档管理')
    })

    it('管理员可见全部非隐藏菜单', () => {
      mockAuthStore({ isAdmin: true })
      const wrapper = mountLayout()
      const titles = wrapper.findAll('.el-menu-item').map(w => w.text())

      expect(titles).toContain('智能问答')
      expect(titles).toContain('知识库管理')
      expect(titles).toContain('文档管理')
    })

    it('meta.hidden 的路由不渲染为菜单项', () => {
      mockAuthStore({ isAdmin: true })
      const wrapper = mountLayout()
      const titles = wrapper.findAll('.el-menu-item').map(w => w.text())

      expect(titles).not.toContain('隐藏菜单')
    })

    it('当前路由对应的菜单项处于激活态', () => {
      mockRoute('/chat', { title: '智能问答' })
      const wrapper = mountLayout()
      const active = wrapper.find('.el-menu-item.is-active')

      expect(active.exists()).toBe(true)
      expect(active.text()).toContain('智能问答')
    })
  })

  describe('交互', () => {
    it('点击折叠按钮切换侧边栏折叠状态', async () => {
      const wrapper = mountLayout()

      expect(wrapper.find('.sidebar').classes()).not.toContain('collapsed')
      expect(wrapper.find('.logo-text').exists()).toBe(true)

      await wrapper.find('.collapse-btn').trigger('click')

      expect(wrapper.find('.sidebar').classes()).toContain('collapsed')
      expect(wrapper.find('.logo-text').exists()).toBe(false)

      await wrapper.find('.collapse-btn').trigger('click')

      expect(wrapper.find('.sidebar').classes()).not.toContain('collapsed')
      expect(wrapper.find('.logo-text').exists()).toBe(true)
    })

    it('点击主题切换按钮调用 toggleDark', async () => {
      const wrapper = mountLayout()

      await wrapper.find('.theme-btn').trigger('click')

      expect(themeMocks.toggleDark).toHaveBeenCalled()
    })

    it('暗色模式下渲染 Sunny 图标 (isDark 为真分支)', () => {
      themeMocks.isDarkRef.value = true
      const wrapper = mountLayout()

      expect(wrapper.findComponent({ name: 'Sunny' }).exists()).toBe(true)
      expect(wrapper.findComponent({ name: 'Moon' }).exists()).toBe(false)
    })

    it('亮色模式下渲染 Moon 图标 (isDark 为假分支)', () => {
      themeMocks.isDarkRef.value = false
      const wrapper = mountLayout()

      expect(wrapper.findComponent({ name: 'Moon' }).exists()).toBe(true)
      expect(wrapper.findComponent({ name: 'Sunny' }).exists()).toBe(false)
    })

    it('下拉命令 profile 提示功能开发中', async () => {
      const wrapper = mountLayout()
      const dropdown = wrapper.findComponent({ name: 'ElDropdown' })

      await dropdown.vm.$emit('command', 'profile')

      expect(ElMessage.info).toHaveBeenCalledWith('个人中心功能开发中')
    })

    it('下拉命令 password 不触发任何提示', async () => {
      const wrapper = mountLayout()
      const dropdown = wrapper.findComponent({ name: 'ElDropdown' })

      await dropdown.vm.$emit('command', 'password')

      expect(ElMessage.info).not.toHaveBeenCalled()
      expect(ElMessage.success).not.toHaveBeenCalled()
      expect(ElMessageBox.confirm).not.toHaveBeenCalled()
    })

    it('下拉命令 logout 确认后调用 store.logout 并提示成功', async () => {
      const authStore = mockAuthStore()
      vi.mocked(ElMessageBox.confirm).mockResolvedValueOnce('confirm')
      const wrapper = mountLayout()
      const dropdown = wrapper.findComponent({ name: 'ElDropdown' })

      dropdown.vm.$emit('command', 'logout')
      await flushPromises()

      expect(ElMessageBox.confirm).toHaveBeenCalled()
      expect(authStore.logout).toHaveBeenCalled()
      expect(ElMessage.success).toHaveBeenCalledWith('已退出登录')
    })

    it('下拉命令 logout 取消时不调用 store.logout', async () => {
      const authStore = mockAuthStore()
      // 模拟用户取消: confirm 不 settle, 避免组件未挂 catch 导致的 unhandled rejection
      vi.mocked(ElMessageBox.confirm).mockImplementationOnce(() => new Promise(() => {}))
      const wrapper = mountLayout()
      const dropdown = wrapper.findComponent({ name: 'ElDropdown' })

      dropdown.vm.$emit('command', 'logout')
      await flushPromises()

      expect(authStore.logout).not.toHaveBeenCalled()
      expect(ElMessage.success).not.toHaveBeenCalled()
    })
  })

  describe('边界路径', () => {
    it('Layout 路由无 children 时菜单为空', () => {
      const layoutRoute = routerMocks.routes.find(r => r.name === 'Layout') as {
        children?: unknown[]
      }
      const originalChildren = layoutRoute.children
      layoutRoute.children = undefined
      try {
        const wrapper = mountLayout()

        expect(wrapper.findAll('.el-menu-item')).toHaveLength(0)
      } finally {
        // 恢复, 避免影响其它用例
        layoutRoute.children = originalChildren
      }
    })
  })
})
