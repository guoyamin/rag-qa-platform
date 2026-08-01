/**
 * 模型管理页 (src/views/admin/models/index.vue) 补充单元测试
 *
 * 覆盖：渲染、onMounted 数据拉取、刷新交互、
 *       新建/编辑/切换/删除流程及其错误边界。
 *
 * 说明：jsdom 无法测量元素尺寸，真实 el-table 不会渲染 fixed 列
 * （操作列按钮缺失），故对 el-table / el-table-column 这两个第三方
 * UI 组件做轻量桩件——按行渲染列插槽；被测组件自身的逻辑
 * （handler / 表单 / API 调用）全部真实运行，未做任何 mock。
 *
 * 生成信息:
 * - AI辅助生成: 是
 * - 生成日期: 2026-08-01
 * 版本: V1.0
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { defineComponent, provide, inject, ref, h, type VNode } from 'vue'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import type { ModelInstance } from '@/api/model'

// 仅 Mock 外部依赖：模型管理 API（组件唯一外部数据源）
vi.mock('@/api/model', () => ({
  listModels: vi.fn(),
  createModel: vi.fn(),
  updateModel: vi.fn(),
  toggleModel: vi.fn(),
  deleteModel: vi.fn(),
  listApiKeys: vi.fn(),
  getHealthSummary: vi.fn(),
}))

import ModelsPage from '@/views/admin/models/index.vue'
import {
  listModels,
  createModel,
  updateModel,
  toggleModel,
  deleteModel,
  listApiKeys,
  getHealthSummary,
} from '@/api/model'

// ---------- el-table / el-table-column 桩件 ----------
// 真实 el-table 在 jsdom 中因无法计算布局而不渲染 fixed 列，
// 这里用最小桩件按行渲染各列的默认插槽，使操作列按钮可交互。
const COLUMNS_KEY = Symbol('el-table-columns')

// eslint-disable-next-line vue/one-component-per-file -- 测试桩件需与列桩件共存于同一测试文件
const ElTableStub = defineComponent({
  name: 'ElTable',
  props: { data: { type: Array, default: () => [] } },
  setup(props, { slots }) {
    const columns = ref<Array<(scope: { row: any; $index: number }) => VNode[] | string>>([])
    provide(COLUMNS_KEY, {
      add: (render: (scope: any) => VNode[] | string) => {
        columns.value = [...columns.value, render]
      },
    })
    return () =>
      h('div', { class: 'el-table', 'data-testid': 'el-table' }, [
        h('table', [
          h('tbody', [
            ...(props.data || []).map((row, idx) =>
              h(
                'tr',
                { key: idx, 'data-testid': 'table-row' },
                columns.value.map((render, ci) =>
                  h('td', { key: ci }, [render({ row, $index: idx })]),
                ),
              ),
            ),
          ]),
        ]),
        // 渲染默认插槽以挂载 el-table-column 子组件（触发列注册）
        h('div', { style: 'display:none' }, slots.default ? slots.default() : []),
      ])
  },
})

// eslint-disable-next-line vue/one-component-per-file -- 列桩件与表桩件配对使用
const ElTableColumnStub = defineComponent({
  name: 'ElTableColumn',
  props: {
    prop: { type: String, default: '' },
    label: { type: String, default: '' },
  },
  setup(props, { slots }) {
    const ctx = inject(COLUMNS_KEY) as
      { add: (r: (s: any) => VNode[] | string) => void } | undefined
    if (ctx) {
      ctx.add((scope: { row: any }) => {
        if (slots.default) return slots.default(scope)
        const val = props.prop ? scope.row[props.prop] : ''
        return val != null ? String(val) : ''
      })
    }
    return () => null
  },
})

// ---------- 测试数据 ----------
const makeModel = (over: Partial<ModelInstance> = {}): ModelInstance => ({
  id: 'm1',
  name: 'GPT-4o',
  provider: 'openai',
  api_key_id: 'k1',
  model_type: 'chat',
  config: {
    model: 'gpt-4o',
    api_base: 'https://api.openai.com/v1',
    temperature: 0.7,
    max_tokens: 2048,
    timeout: 60,
  },
  status: 'active',
  description: 'OpenAI flagship',
  created_by: 'admin',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  ...over,
})

const models: ModelInstance[] = [
  makeModel({ id: 'm1', name: 'GPT-4o', provider: 'openai', status: 'active' }),
  makeModel({
    id: 'm2',
    name: 'Claude 3.5',
    provider: 'anthropic',
    status: 'inactive',
    description: null,
    config: {
      model: 'claude-3-5-sonnet',
      api_base: '',
      temperature: 0.7,
      max_tokens: 4096,
      timeout: 60,
    },
  }),
]

const apiKeys = [
  {
    id: 'k1',
    name: 'OpenAI Key',
    provider: 'openai',
    usage: 'llm' as const,
    status: 'active' as const,
    key_preview: 'sk**ab',
    expires_at: null,
    description: null,
    created_by: 'admin',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
]

const health = {
  total_models: 2,
  healthy_count: 1,
  degraded_count: 1,
  unhealthy_count: 0,
  unknown_count: 0,
}

const listResp = { items: models, total: models.length, page: 1, page_size: 20 }
const keysResp = { items: apiKeys, total: apiKeys.length }

// ---------- 消息提示 Spy（避免真实 DOM 渲染副作用） ----------
const errorSpy = vi.spyOn(ElMessage, 'error')
const successSpy = vi.spyOn(ElMessage, 'success')
const confirmSpy = vi.spyOn(ElMessageBox, 'confirm')

// ---------- 工具方法 ----------
let wrapper: ReturnType<typeof mount> | null = null

const mountComponent = () => {
  wrapper = mount(ModelsPage, {
    global: {
      plugins: [createPinia(), ElementPlus],
      stubs: {
        ElTable: ElTableStub,
        ElTableColumn: ElTableColumnStub,
      },
    },
    attachTo: document.body,
  })
  return wrapper
}

// 多次 flush 以覆盖嵌套异步链（validate -> createModel -> fetchModels）
const flushAll = async () => {
  for (let i = 0; i < 4; i++) {
    await flushPromises()
  }
}

/** 在 document 中查找第 nth 个包含指定文本的 button 并点击 */
const clickButton = async (text: string, nth = 0) => {
  const buttons = Array.from(document.querySelectorAll('button')).filter(b =>
    (b.textContent || '').replace(/\s+/g, '').includes(text.replace(/\s+/g, '')),
  )
  expect(buttons[nth], `未找到包含 "${text}" 的按钮`).toBeTruthy()
  buttons[nth].click()
  await flushAll()
}

/** 设置 el-input 内部原生 input 的值并触发 v-model 更新 */
const setInputValue = (placeholder: string, value: string) => {
  const input = document.querySelector(`input[placeholder="${placeholder}"]`) as HTMLInputElement
  expect(input, `未找到 placeholder 为 "${placeholder}" 的输入框`).toBeTruthy()
  input.value = value
  input.dispatchEvent(new Event('input', { bubbles: true }))
}

afterEach(() => {
  if (wrapper) {
    wrapper.unmount()
    wrapper = null
  }
  document.body.innerHTML = ''
})

beforeEach(() => {
  // 重置所有 mock 并重新设置默认实现，避免用例间状态泄漏
  vi.mocked(listModels).mockReset()
  vi.mocked(listModels).mockResolvedValue(listResp)
  vi.mocked(listApiKeys).mockReset()
  vi.mocked(listApiKeys).mockResolvedValue(keysResp)
  vi.mocked(getHealthSummary).mockReset()
  vi.mocked(getHealthSummary).mockResolvedValue(health)
  vi.mocked(createModel).mockReset()
  vi.mocked(createModel).mockResolvedValue(makeModel())
  vi.mocked(updateModel).mockReset()
  vi.mocked(updateModel).mockResolvedValue(makeModel())
  vi.mocked(toggleModel).mockReset()
  vi.mocked(toggleModel).mockResolvedValue(makeModel())
  vi.mocked(deleteModel).mockReset()
  vi.mocked(deleteModel).mockResolvedValue(undefined as any)

  errorSpy.mockReset()
  errorSpy.mockImplementation(() => ({ close: vi.fn() }) as any)
  successSpy.mockReset()
  successSpy.mockImplementation(() => ({ close: vi.fn() }) as any)
  confirmSpy.mockReset()
  confirmSpy.mockResolvedValue('confirm')
})

describe('ModelsPage - 渲染', () => {
  it('渲染页面标题与新增按钮', async () => {
    // Arrange / Act
    const wrapper = mountComponent()
    await flushAll()

    // Assert
    expect(wrapper.find('h2').text()).toBe('模型管理')
    expect(wrapper.text()).toContain('新增模型')
  })

  it('onMounted 拉取模型列表、API Key、健康汇总', async () => {
    // Arrange / Act
    mountComponent()
    await flushAll()

    // Assert
    expect(listModels).toHaveBeenCalledTimes(1)
    expect(listModels).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
      provider: undefined,
      status: undefined,
    })
    expect(listApiKeys).toHaveBeenCalledWith({ page_size: 100 })
    expect(getHealthSummary).toHaveBeenCalledTimes(1)
  })

  it('渲染健康状态卡片数量', async () => {
    // Arrange / Act
    const wrapper = mountComponent()
    await flushAll()

    // Assert
    expect(wrapper.find('.status-card.healthy .status-count').text()).toBe('1')
    expect(wrapper.find('.status-card.degraded .status-count').text()).toBe('1')
    expect(wrapper.find('.status-card.unhealthy .status-count').text()).toBe('0')
    expect(wrapper.find('.status-card.total .status-count').text()).toBe('2')
  })

  it('健康汇总失败时状态卡片显示 0 且不弹错误', async () => {
    // Arrange
    vi.mocked(getHealthSummary).mockRejectedValue(new Error('boom'))

    // Act
    const wrapper = mountComponent()
    await flushAll()

    // Assert
    expect(wrapper.find('.status-card.total .status-count').text()).toBe('0')
    expect(errorSpy).not.toHaveBeenCalled()
  })

  it('空模型列表正常渲染', async () => {
    // Arrange
    vi.mocked(listModels).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    })
    vi.mocked(getHealthSummary).mockResolvedValue({
      total_models: 0,
      healthy_count: 0,
      degraded_count: 0,
      unhealthy_count: 0,
      unknown_count: 0,
    })

    // Act
    const wrapper = mountComponent()
    await flushAll()

    // Assert
    expect(wrapper.find('h2').text()).toBe('模型管理')
    expect(wrapper.find('.status-card.total .status-count').text()).toBe('0')
  })
})

describe('ModelsPage - 数据拉取错误处理', () => {
  it('获取模型列表失败时提示错误', async () => {
    // Arrange
    vi.mocked(listModels).mockRejectedValue(new Error('boom'))

    // Act
    mountComponent()
    await flushAll()

    // Assert
    expect(errorSpy).toHaveBeenCalledWith('获取模型列表失败')
  })

  it('获取 API Key 失败时静默忽略', async () => {
    // Arrange
    vi.mocked(listApiKeys).mockRejectedValue(new Error('boom'))

    // Act
    mountComponent()
    await flushAll()

    // Assert
    expect(errorSpy).not.toHaveBeenCalled()
  })
})

describe('ModelsPage - 列表与交互渲染', () => {
  it('渲染模型列表表格行', async () => {
    // Arrange / Act
    const wrapper = mountComponent()
    await flushAll()

    // Assert
    expect(wrapper.text()).toContain('GPT-4o')
    expect(wrapper.text()).toContain('Claude 3.5')
  })

  it('根据状态显示启用/禁用标签', async () => {
    // Arrange / Act
    const wrapper = mountComponent()
    await flushAll()

    // Assert
    const tags = wrapper.findAll('.el-tag').map(t => t.text())
    expect(tags).toContain('启用')
    expect(tags).toContain('禁用')
  })

  it('操作列切换按钮文案随状态变化', async () => {
    // Arrange / Act
    const wrapper = mountComponent()
    await flushAll()

    // Assert：active 行切换按钮为"禁用"，inactive 行为"启用"
    const buttonTexts = wrapper.findAll('button').map(b => b.text().replace(/\s+/g, ''))
    expect(buttonTexts).toContain('禁用')
    expect(buttonTexts).toContain('启用')
  })

  it('点击刷新按钮重新拉取模型列表', async () => {
    // Arrange
    mountComponent()
    await flushAll()

    // Act
    await clickButton('刷新')

    // Assert：onMounted 1 次 + 刷新 1 次
    expect(listModels).toHaveBeenCalledTimes(2)
  })
})

describe('ModelsPage - 新建模型', () => {
  it('点击新增打开对话框并显示新增标题', async () => {
    // Arrange
    mountComponent()
    await flushAll()

    // Act
    await clickButton('新增模型')

    // Assert
    expect(document.querySelector('.el-dialog__title')?.textContent).toContain('新增模型')
    expect(document.querySelector('input[placeholder="请输入模型名称"]')).not.toBeNull()
  })

  it('提交新建模型成功后调用 createModel 并刷新列表与健康汇总', async () => {
    // Arrange
    mountComponent()
    await flushAll()
    await clickButton('新增模型')

    // Act：填写必填字段后提交
    setInputValue('请输入模型名称', 'New Model')
    setInputValue('如: gpt-4o', 'gpt-4o-mini')
    await flushAll()
    await clickButton('确定')

    // Assert
    expect(createModel).toHaveBeenCalledWith(expect.objectContaining({ name: 'New Model' }))
    expect(successSpy).toHaveBeenCalledWith('创建成功')
    expect(listModels).toHaveBeenCalledTimes(2)
    expect(getHealthSummary).toHaveBeenCalledTimes(2)
  })

  it('新建模型失败时提示创建失败', async () => {
    // Arrange
    vi.mocked(createModel).mockRejectedValue(new Error('boom'))
    mountComponent()
    await flushAll()
    await clickButton('新增模型')
    setInputValue('请输入模型名称', 'New Model')
    setInputValue('如: gpt-4o', 'gpt-4o-mini')
    await flushAll()

    // Act
    await clickButton('确定')

    // Assert
    expect(createModel).toHaveBeenCalledTimes(1)
    expect(errorSpy).toHaveBeenCalledWith('创建失败')
  })
})

describe('ModelsPage - 编辑模型', () => {
  it('点击编辑打开对话框并预填表单', async () => {
    // Arrange
    mountComponent()
    await flushAll()

    // Act：点击第一行的编辑按钮（m1）
    await clickButton('编辑', 0)

    // Assert
    expect(document.querySelector('.el-dialog__title')?.textContent).toContain('编辑模型')
    const nameInput = document.querySelector(
      'input[placeholder="请输入模型名称"]',
    ) as HTMLInputElement
    expect(nameInput.value).toBe('GPT-4o')
    const modelInput = document.querySelector('input[placeholder="如: gpt-4o"]') as HTMLInputElement
    expect(modelInput.value).toBe('gpt-4o')
  })

  it('编辑 null 描述的模型时正常预填表单', async () => {
    // Arrange：m2 的 description 为 null，覆盖 `row.description || ''` 空值分支
    mountComponent()
    await flushAll()

    // Act：点击第二行的编辑按钮（m2）
    await clickButton('编辑', 1)

    // Assert
    expect(document.querySelector('.el-dialog__title')?.textContent).toContain('编辑模型')
    const nameInput = document.querySelector(
      'input[placeholder="请输入模型名称"]',
    ) as HTMLInputElement
    expect(nameInput.value).toBe('Claude 3.5')
  })

  it('提交编辑成功后调用 updateModel', async () => {
    // Arrange
    mountComponent()
    await flushAll()
    await clickButton('编辑', 0)

    // Act
    await clickButton('确定')

    // Assert
    expect(updateModel).toHaveBeenCalledWith('m1', expect.objectContaining({ name: 'GPT-4o' }))
    expect(successSpy).toHaveBeenCalledWith('更新成功')
  })

  it('更新失败时提示更新失败', async () => {
    // Arrange
    vi.mocked(updateModel).mockRejectedValue(new Error('boom'))
    mountComponent()
    await flushAll()
    await clickButton('编辑', 0)

    // Act
    await clickButton('确定')

    // Assert
    expect(updateModel).toHaveBeenCalledTimes(1)
    expect(errorSpy).toHaveBeenCalledWith('更新失败')
  })
})

describe('ModelsPage - 切换状态', () => {
  it('切换 active 模型提示已禁用', async () => {
    // Arrange
    mountComponent()
    await flushAll()

    // Act：m1(active) 的切换按钮文案为"禁用"
    await clickButton('禁用', 0)

    // Assert
    expect(toggleModel).toHaveBeenCalledWith('m1')
    expect(successSpy).toHaveBeenCalledWith('已禁用')
  })

  it('切换 inactive 模型提示已启用', async () => {
    // Arrange
    mountComponent()
    await flushAll()

    // Act：m2(inactive) 的切换按钮文案为"启用"
    await clickButton('启用', 0)

    // Assert
    expect(toggleModel).toHaveBeenCalledWith('m2')
    expect(successSpy).toHaveBeenCalledWith('已启用')
  })

  it('切换失败时提示操作失败', async () => {
    // Arrange
    vi.mocked(toggleModel).mockRejectedValue(new Error('boom'))
    mountComponent()
    await flushAll()

    // Act
    await clickButton('禁用', 0)

    // Assert
    expect(errorSpy).toHaveBeenCalledWith('操作失败')
  })
})

describe('ModelsPage - 删除模型', () => {
  it('删除模型弹确认框并调用 deleteModel', async () => {
    // Arrange
    mountComponent()
    await flushAll()

    // Act：点击第一行的删除按钮（m1）
    await clickButton('删除', 0)

    // Assert
    expect(confirmSpy).toHaveBeenCalledWith('确定删除模型 "GPT-4o" 吗？', '提示', {
      type: 'warning',
    })
    expect(deleteModel).toHaveBeenCalledWith('m1')
    expect(successSpy).toHaveBeenCalledWith('删除成功')
  })

  it('取消删除时不调用 deleteModel', async () => {
    // Arrange
    confirmSpy.mockRejectedValueOnce(new Error('cancel'))
    mountComponent()
    await flushAll()

    // Act
    await clickButton('删除', 0)

    // Assert
    expect(deleteModel).not.toHaveBeenCalled()
    expect(successSpy).not.toHaveBeenCalled()
  })
})
