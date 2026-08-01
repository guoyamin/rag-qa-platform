import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import LoginPage from '@/views/login/index.vue'

describe('LoginPage', () => {
  it('renders login form', () => {
    const wrapper = mount(LoginPage, {
      global: {
        plugins: [createPinia(), ElementPlus],
      },
    })

    expect(wrapper.find('h2').text()).toBe('欢迎登录')
    expect(wrapper.find('input[placeholder="请输入工号/用户名"]').exists()).toBe(true)
    expect(wrapper.find('input[placeholder="请输入密码"]').exists()).toBe(true)
  })
})
