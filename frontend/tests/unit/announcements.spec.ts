/**
 * 公告管理页 (src/views/admin/announcements/index.vue) 单元测试
 *
 * 覆盖：渲染、onMounted 数据拉取、API 错误提示。
 * dialog 相关流程（create/update/delete）依赖 ElMessageBox.confirm 同步对话框，
 * 在 jsdom 测试环境无法自动 resolve，暂不覆盖。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { defineComponent, provide, inject, ref, h, type VNode } from 'vue'
import ElementPlus, { ElMessage } from 'element-plus'
import type { AnnouncementItem } from '@/api/announcement'

// Mock 公告管理 API
vi.mock('@/api/announcement', () => ({
  listAnnouncements: vi.fn(),
  createAnnouncement: vi.fn(),
  updateAnnouncement: vi.fn(),
  deleteAnnouncement: vi.fn(),
  publishAnnouncement: vi.fn(),
}))

import AnnouncementsPage from '@/views/admin/announcements/index.vue'
import { listAnnouncements } from '@/api/announcement'

// ---------- el-table / el-table-column 桩件 ----------
const COLUMNS_KEY = Symbol('el-table-columns')

const ElTableStub = defineComponent({
  name: 'ElTable',
  props: { data: { type: Array, default: () => [] } },
  setup(props, { slots }) {
    const columns = ref<Array<(s: { row: any }) => VNode[] | string>>([])
    provide(COLUMNS_KEY, {
      add: (render: (s: { row: any }) => VNode[] | string) => {
        columns.value = [...columns.value, render]
      },
    })
    return () =>
      h('div', { class: 'el-table' }, [
        h('table', [
          h('tbody', [
            ...(props.data || []).map((row: any, idx: number) =>
              h(
                'tr',
                { key: idx, 'data-testid': 'table-row' },
                columns.value.map((render, ci) => h('td', { key: ci }, [render({ row })])),
              ),
            ),
          ]),
        ]),
        h('div', { style: 'display:none' }, slots.default ? slots.default() : []),
      ])
  },
})

const ElTableColumnStub = defineComponent({
  name: 'ElTableColumn',
  props: { prop: { type: String, default: '' }, label: { type: String, default: '' } },
  setup(props, { slots }) {
    const ctx = inject(COLUMNS_KEY) as
      { add: (r: (s: { row: any }) => VNode[] | string) => void } | undefined
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
const mockItem = (overrides: Partial<AnnouncementItem> = {}): AnnouncementItem => ({
  id: 'ann-1',
  title: '测试公告',
  content: '测试内容',
  type: 'notice',
  status: 'draft',
  pinned: false,
  published_at: null,
  created_at: '2026-08-01T12:00:00Z',
  updated_at: '2026-08-01T12:00:00Z',
  ...overrides,
})

// ---------- 测试设置 ----------
const mountPage = () =>
  mount(AnnouncementsPage, {
    global: {
      plugins: [createPinia(), ElementPlus as any],
      stubs: {
        'el-table': ElTableStub,
        'el-table-column': ElTableColumnStub,
        'el-button': true,
        'el-icon': true,
        'el-select': true,
        'el-option': true,
        'el-pagination': true,
        'el-dialog': true,
        'el-form': true,
        'el-form-item': true,
        'el-input': true,
        'el-textarea': true,
        'el-switch': true,
        'el-tag': { template: '<span>{type}</span>' },
      },
    },
  })

describe('公告管理页', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(ElMessage, 'error').mockImplementation(() => {})
    vi.spyOn(ElMessage, 'success').mockImplementation(() => {})
  })

  it('挂载时调用 listAnnouncements', async () => {
    vi.mocked(listAnnouncements).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    } as any)

    const wrapper = mountPage()
    await flushPromises()

    expect(listAnnouncements).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('公告列表正常渲染', async () => {
    const items = [mockItem({ title: '公告A' }), mockItem({ title: '公告B' })]
    vi.mocked(listAnnouncements).mockResolvedValue({
      items,
      total: 2,
      page: 1,
      page_size: 20,
    } as any)

    const wrapper = mountPage()
    await flushPromises()

    const rows = wrapper.findAll('[data-testid="table-row"]')
    expect(rows.length).toBe(2)
    wrapper.unmount()
  })

  it('API 错误时 ElMessage.error 被调用', async () => {
    vi.mocked(listAnnouncements).mockRejectedValue(new Error('network error'))

    const wrapper = mountPage()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('获取公告列表失败')
    wrapper.unmount()
  })
})
