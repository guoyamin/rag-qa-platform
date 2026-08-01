/**
 * 杂项视图单元测试
 *
 * 覆盖组件:
 * - src/views/documents/index.vue (文档管理占位页)
 * - src/views/knowledge/index.vue (知识库管理占位页)
 * - src/views/error/404.vue (404 错误页)
 *
 * 生成信息:
 * - AI辅助生成: 是
 * - 生成日期: 2026-08-01
 * 版本: V1.0
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import { Document, Collection } from '@element-plus/icons-vue'
import DocumentsPage from '@/views/documents/index.vue'
import KnowledgePage from '@/views/knowledge/index.vue'
import NotFoundPage from '@/views/error/404.vue'

// 隔离 vue-router 路由依赖
const { mockRouterPush } = vi.hoisted(() => ({
  mockRouterPush: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockRouterPush }),
  useRoute: () => ({ path: '/' }),
  createRouter: vi.fn(() => ({ beforeEach: vi.fn() })),
  createWebHistory: vi.fn(),
}))

// 公共挂载选项: 注册 ElementPlus / Pinia, 注入 mock $router
function mountComponent(component: any) {
  return mount(component, {
    global: {
      plugins: [createPinia(), ElementPlus],
      mocks: {
        $router: { push: mockRouterPush },
      },
    },
  })
}

beforeEach(() => {
  mockRouterPush.mockClear()
})

describe('DocumentsPage 文档管理占位页', () => {
  it('渲染页面标题"文档管理"', () => {
    // Arrange & Act
    const wrapper = mountComponent(DocumentsPage)

    // Assert
    expect(wrapper.find('h3').text()).toBe('文档管理')
  })

  it('渲染开发中提示文案', () => {
    // Arrange & Act
    const wrapper = mountComponent(DocumentsPage)

    // Assert
    expect(wrapper.find('p').text()).toBe('该功能正在开发中，敬请期待')
  })

  it('渲染 Document 图标及图标容器', () => {
    // Arrange & Act
    const wrapper = mountComponent(DocumentsPage)

    // Assert
    expect(wrapper.find('.placeholder-icon').exists()).toBe(true)
    expect(wrapper.findComponent(Document).exists()).toBe(true)
  })

  it('根节点包含 placeholder-page 样式类', () => {
    // Arrange & Act
    const wrapper = mountComponent(DocumentsPage)

    // Assert
    expect(wrapper.classes()).toContain('placeholder-page')
  })
})

describe('KnowledgePage 知识库管理占位页', () => {
  it('渲染页面标题"知识库管理"', () => {
    // Arrange & Act
    const wrapper = mountComponent(KnowledgePage)

    // Assert
    expect(wrapper.find('h3').text()).toBe('知识库管理')
  })

  it('渲染开发中提示文案', () => {
    // Arrange & Act
    const wrapper = mountComponent(KnowledgePage)

    // Assert
    expect(wrapper.find('p').text()).toBe('该功能正在开发中，敬请期待')
  })

  it('渲染 Collection 图标及图标容器', () => {
    // Arrange & Act
    const wrapper = mountComponent(KnowledgePage)

    // Assert
    expect(wrapper.find('.placeholder-icon').exists()).toBe(true)
    expect(wrapper.findComponent(Collection).exists()).toBe(true)
  })

  it('根节点包含 placeholder-page 样式类', () => {
    // Arrange & Act
    const wrapper = mountComponent(KnowledgePage)

    // Assert
    expect(wrapper.classes()).toContain('placeholder-page')
  })
})

describe('NotFoundPage 404 错误页', () => {
  it('渲染错误码 404', () => {
    // Arrange & Act
    const wrapper = mountComponent(NotFoundPage)

    // Assert
    expect(wrapper.find('.error-code').text()).toBe('404')
  })

  it('渲染错误提示文案', () => {
    // Arrange & Act
    const wrapper = mountComponent(NotFoundPage)

    // Assert
    expect(wrapper.find('p').text()).toBe('抱歉，您访问的页面不存在')
  })

  it('渲染"返回首页"按钮', () => {
    // Arrange & Act
    const wrapper = mountComponent(NotFoundPage)

    // Assert
    const btn = wrapper.find('.back-btn')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toBe('返回首页')
  })

  it('点击"返回首页"按钮调用 router.push("/")', async () => {
    // Arrange
    const wrapper = mountComponent(NotFoundPage)

    // Act
    await wrapper.find('.back-btn').trigger('click')

    // Assert
    expect(mockRouterPush).toHaveBeenCalledTimes(1)
    expect(mockRouterPush).toHaveBeenCalledWith('/')
  })

  it('根节点包含 error-page 样式类', () => {
    // Arrange & Act
    const wrapper = mountComponent(NotFoundPage)

    // Assert
    expect(wrapper.classes()).toContain('error-page')
  })
})
