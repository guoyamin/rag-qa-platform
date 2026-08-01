/**
 * 管理后台占位页面单元测试
 *
 * 覆盖组件:
 * - src/views/admin/settings.vue (系统设置占位页)
 * - src/views/admin/users.vue (用户管理占位页)
 *
 * 说明: 两个组件均为纯展示型占位页,无 API / Store / Router 依赖,
 *      仅需提供 ElementPlus 插件以支持 el-icon 渲染,并提供 Pinia
 *      与现有测试 (login.spec.ts) 保持一致的挂载环境。
 *
 * 生成信息:
 * - AI辅助生成: 是
 * - 生成日期: 2026-08-01
 * 版本: V1.0
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import SettingsPage from '@/views/admin/settings.vue'
import UsersPage from '@/views/admin/users.vue'

/**
 * 创建公共挂载选项
 * 每次调用生成新的 Pinia 实例,保证各测试用例状态隔离
 */
function getMountOptions() {
  return {
    global: {
      plugins: [createPinia(), ElementPlus],
    },
  }
}

describe('SettingsPage - 系统设置占位页', () => {
  it('渲染根占位容器 placeholder-page', () => {
    // Arrange & Act
    const wrapper = mount(SettingsPage, getMountOptions())

    // Assert
    expect(wrapper.find('.placeholder-page').exists()).toBe(true)
  })

  it('渲染占位卡片容器 placeholder-card', () => {
    // Arrange & Act
    const wrapper = mount(SettingsPage, getMountOptions())

    // Assert
    expect(wrapper.find('.placeholder-card').exists()).toBe(true)
  })

  it('渲染图标容器 placeholder-icon', () => {
    // Arrange & Act
    const wrapper = mount(SettingsPage, getMountOptions())

    // Assert
    expect(wrapper.find('.placeholder-icon').exists()).toBe(true)
  })

  it('渲染 Setting 图标 (el-icon 内包含 svg)', () => {
    // Arrange & Act
    const wrapper = mount(SettingsPage, getMountOptions())

    // Assert: el-icon 组件存在且其内渲染了 svg 图标
    expect(wrapper.find('.el-icon').exists()).toBe(true)
    expect(wrapper.find('.placeholder-icon svg').exists()).toBe(true)
  })

  it('标题文案为"系统设置"', () => {
    // Arrange & Act
    const wrapper = mount(SettingsPage, getMountOptions())

    // Assert
    expect(wrapper.find('h3').text()).toBe('系统设置')
  })

  it('提示文案为"该功能正在开发中，敬请期待"', () => {
    // Arrange & Act
    const wrapper = mount(SettingsPage, getMountOptions())

    // Assert
    expect(wrapper.find('p').text()).toBe('该功能正在开发中，敬请期待')
  })

  it('占位卡片结构完整: 图标容器、标题、提示同时存在', () => {
    // Arrange & Act
    const wrapper = mount(SettingsPage, getMountOptions())
    const card = wrapper.find('.placeholder-card')

    // Assert: 卡片内同时包含图标容器、标题与提示文案
    expect(card.find('.placeholder-icon').exists()).toBe(true)
    expect(card.find('h3').exists()).toBe(true)
    expect(card.find('p').exists()).toBe(true)
  })
})

describe('UsersPage - 用户管理占位页', () => {
  it('渲染根占位容器 placeholder-page', () => {
    // Arrange & Act
    const wrapper = mount(UsersPage, getMountOptions())

    // Assert
    expect(wrapper.find('.placeholder-page').exists()).toBe(true)
  })

  it('渲染占位卡片容器 placeholder-card', () => {
    // Arrange & Act
    const wrapper = mount(UsersPage, getMountOptions())

    // Assert
    expect(wrapper.find('.placeholder-card').exists()).toBe(true)
  })

  it('渲染图标容器 placeholder-icon', () => {
    // Arrange & Act
    const wrapper = mount(UsersPage, getMountOptions())

    // Assert
    expect(wrapper.find('.placeholder-icon').exists()).toBe(true)
  })

  it('渲染 User 图标 (el-icon 内包含 svg)', () => {
    // Arrange & Act
    const wrapper = mount(UsersPage, getMountOptions())

    // Assert: el-icon 组件存在且其内渲染了 svg 图标
    expect(wrapper.find('.el-icon').exists()).toBe(true)
    expect(wrapper.find('.placeholder-icon svg').exists()).toBe(true)
  })

  it('标题文案为"用户管理"', () => {
    // Arrange & Act
    const wrapper = mount(UsersPage, getMountOptions())

    // Assert
    expect(wrapper.find('h3').text()).toBe('用户管理')
  })

  it('提示文案为"该功能正在开发中，敬请期待"', () => {
    // Arrange & Act
    const wrapper = mount(UsersPage, getMountOptions())

    // Assert
    expect(wrapper.find('p').text()).toBe('该功能正在开发中，敬请期待')
  })

  it('占位卡片结构完整: 图标容器、标题、提示同时存在', () => {
    // Arrange & Act
    const wrapper = mount(UsersPage, getMountOptions())
    const card = wrapper.find('.placeholder-card')

    // Assert: 卡片内同时包含图标容器、标题与提示文案
    expect(card.find('.placeholder-icon').exists()).toBe(true)
    expect(card.find('h3').exists()).toBe(true)
    expect(card.find('p').exists()).toBe(true)
  })
})
