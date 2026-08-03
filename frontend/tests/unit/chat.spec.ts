/**
 * 聊天页 单元测试
 *
 * 说明: 聊天组件依赖 @/api/chat（chatCompletion / submitFeedback），单元测试 Mock
 * 这两个 API；element-plus 的 ElMessage 与 navigator.clipboard 也 Mock。marked /
 * dompurify 保持真实运行，覆盖 Markdown 渲染与 XSS 清洗逻辑。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { nextTick } from 'vue'
import ElementPlus from 'element-plus'
import ChatPage from '@/views/chat/index.vue'

// ---- Mock @/api/chat ----
const { mockChatCompletion, mockSubmitFeedback } = vi.hoisted(() => ({
  mockChatCompletion: vi.fn(),
  mockSubmitFeedback: vi.fn(),
}))

vi.mock('@/api/chat', () => ({
  chatCompletion: (...args: unknown[]) => mockChatCompletion(...args),
  submitFeedback: (...args: unknown[]) => mockSubmitFeedback(...args),
}))

// ---- Mock 外部依赖: ElMessage（避免 jsdom 中注入消息 DOM） ----
const { mockElMessage } = vi.hoisted(() => ({
  mockElMessage: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  }),
}))

vi.mock('element-plus', async importOriginal => {
  const actual = (await importOriginal()) as typeof import('element-plus')
  return { ...actual, ElMessage: mockElMessage }
})

const QUICK_QUESTIONS = [
  '如何查询公司规章制度？',
  '请假流程是什么？',
  '报销流程是怎样的？',
  '入职手续如何办理？',
]

// 助手固定回复内容（mock chatCompletion 返回）
const ASSISTANT_ANSWER =
  '您好！我是企业知识库智能助手。\n\n关于您的问题，我可以为您提供以下信息：\n\n1. **制度规范**：包括考勤制度、报销制度、晋升制度等\n2. **业务流程**：请假流程、审批流程、入职离职流程等\n3. **产品文档**：产品手册、操作指南、常见问题等\n\n请问您具体想了解哪方面的业务？'
const ASSISTANT_REPLY = '您好！我是企业知识库智能助手。'
const ASSISTANT_SOURCES = [
  {
    document_id: 'doc-001',
    chunk_index: 0,
    score: 0.92,
    content_preview: '公司员工规章制度手册...',
  },
]
const ASSISTANT_DATA = {
  answer: ASSISTANT_ANSWER,
  sources: ASSISTANT_SOURCES,
  tokens_used: 42,
  latency_ms: 100,
  session_id: 'sess-1',
  message_id: 'msg-1',
}

const mountChat = (): VueWrapper =>
  mount(ChatPage, {
    global: {
      plugins: [createPinia(), ElementPlus],
    },
  })

const flush = async (): Promise<void> => {
  await nextTick()
  await nextTick()
  await nextTick()
}

const typeMessage = async (wrapper: VueWrapper, text: string): Promise<void> => {
  await wrapper.find('.el-textarea__inner').setValue(text)
  await nextTick()
}

// 受控 chatCompletion：beforeEach 里设为 pending，本函数触发发送后手动 resolve
let resolveChat!: (v: unknown) => void

const sendAndReceiveReply = async (wrapper: VueWrapper, text: string): Promise<void> => {
  await typeMessage(wrapper, text)
  await wrapper.find('.send-btn').trigger('click')
  await flush() // 运行到 await chatCompletion
  resolveChat({ code: 'SUCCESS', message: '操作成功', data: ASSISTANT_DATA })
  await flush() // 解析 promise + 渲染助手回复
}

const setClipboard = (writeText: ReturnType<typeof vi.fn>): void => {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText },
    configurable: true,
    writable: true,
  })
}

const findActionButton = (wrapper: VueWrapper, text: string): VueWrapper => {
  const btn = wrapper.findAll('.message-actions button').find(b => b.text().includes(text))
  if (!btn) {
    throw new Error(`操作按钮 "${text}" 未找到`)
  }
  return btn
}

describe('ChatPage', () => {
  let wrapper: VueWrapper

  beforeEach(() => {
    mockElMessage.mockClear()
    mockElMessage.success.mockClear()
    mockElMessage.error.mockClear()
    mockChatCompletion.mockClear()
    mockSubmitFeedback.mockClear()
    // chatCompletion 默认 pending（用于测加载态）；sendAndReceiveReply 里手动 resolve
    mockChatCompletion.mockImplementation(
      () =>
        new Promise(r => {
          resolveChat = r
        }),
    )
    mockSubmitFeedback.mockResolvedValue({ code: 'SUCCESS', message: '操作成功', data: null })
    setClipboard(vi.fn().mockResolvedValue(undefined))
    wrapper = mountChat()
  })

  // ==================== 渲染 ====================
  it('无消息时渲染欢迎区，包含标题、描述与快捷问题', () => {
    expect(wrapper.find('.welcome-area h2').text()).toBe('企业知识库智能助手')
    expect(wrapper.find('.welcome-desc').text()).toContain('企业知识库助手')

    const tags = wrapper.findAll('.question-tag')
    expect(tags).toHaveLength(4)
    tags.forEach((tag, i) => {
      expect(tag.text()).toBe(QUICK_QUESTIONS[i])
    })
  })

  it('渲染知识库选择器与 Ctrl+Enter 输入提示', () => {
    expect(wrapper.find('.el-select').exists()).toBe(true)
    expect(wrapper.find('.input-hint').text()).toBe('Ctrl + Enter 发送')
  })

  it('输入为空时发送按钮禁用，输入内容后启用', async () => {
    const sendBtn = () => wrapper.find('.send-btn').element as HTMLButtonElement
    expect(sendBtn().disabled).toBe(true)

    await typeMessage(wrapper, '你好')

    expect(sendBtn().disabled).toBe(false)
  })

  // ==================== 发送流程 ====================
  it('发送消息后展示用户气泡与“正在思考中”加载态，并隐藏欢迎区', async () => {
    await typeMessage(wrapper, '你好')
    await wrapper.find('.send-btn').trigger('click')
    await flush()

    const userItem = wrapper.find('.message-item.user')
    expect(userItem.exists()).toBe(true)
    expect(userItem.text()).toContain('你好')
    expect(wrapper.find('.message-bubble.loading').text()).toContain('正在思考中...')
    expect(wrapper.find('.welcome-area').exists()).toBe(false)
  })

  it('收到回复后渲染助手回复与参考来源，并移除加载态', async () => {
    await sendAndReceiveReply(wrapper, '你好')

    expect(wrapper.find('.message-item.assistant').exists()).toBe(true)
    expect(wrapper.find('.message-bubble.loading').exists()).toBe(false)
    expect(wrapper.find('.message-sources').exists()).toBe(true)
    expect(wrapper.find('.source-title').text()).toContain('来源 1')
    expect(wrapper.find('.source-preview').text()).toContain('公司员工规章制度手册')
  })

  it('Ctrl+Enter 触发发送', async () => {
    await wrapper.find('.el-textarea__inner').setValue('快捷发送')
    await wrapper.find('.el-textarea__inner').trigger('keyup', {
      key: 'Enter',
      ctrlKey: true,
    })
    await flush()

    expect(wrapper.find('.message-item.user').text()).toContain('快捷发送')
  })

  it('点击快捷问题标签发送对应问题', async () => {
    const tag = wrapper.findAll('.question-tag')[0]

    await tag.find('.el-tag').trigger('click')
    await flush()

    expect(wrapper.find('.message-item.user').text()).toContain(QUICK_QUESTIONS[0])
  })

  it('发送后清空输入框', async () => {
    await typeMessage(wrapper, '清空测试')
    await wrapper.find('.send-btn').trigger('click')
    await flush()

    const textarea = wrapper.find('.el-textarea__inner').element as HTMLTextAreaElement
    expect(textarea.value).toBe('')
  })

  it('回复加载中时不重复发送消息', async () => {
    await typeMessage(wrapper, '第一条')
    await wrapper.find('.send-btn').trigger('click')
    await flush()

    // loading 期间再次输入并尝试 Ctrl+Enter
    await wrapper.find('.el-textarea__inner').setValue('第二条')
    await wrapper.find('.el-textarea__inner').trigger('keyup', {
      key: 'Enter',
      ctrlKey: true,
    })
    await flush()

    const userItems = wrapper.findAll('.message-item.user')
    expect(userItems).toHaveLength(1)
    expect(userItems[0].text()).toContain('第一条')
  })

  // ==================== Markdown / XSS ====================
  it('将助手回复中的 Markdown 加粗渲染为 <strong>', async () => {
    await sendAndReceiveReply(wrapper, '你好')

    expect(wrapper.find('.message-item.assistant .message-text').html()).toContain(
      '<strong>制度规范</strong>',
    )
  })

  it('清洗用户消息中的恶意 HTML（移除 <script> 与 onerror）', async () => {
    const malicious = "<script>alert('xss')</script><img src=x onerror=alert(1)>"

    await sendAndReceiveReply(wrapper, malicious)

    const html = wrapper.find('.message-item.user .message-text').html()
    expect(html).not.toContain('<script')
    expect(html).not.toContain('onerror')
    expect(html).not.toContain('alert')
  })

  // ==================== 消息操作 ====================
  it('点击“有用”将助手消息标记为已点赞并显示反馈', async () => {
    await sendAndReceiveReply(wrapper, '你好')
    const likeBtn = findActionButton(wrapper, '有用')
    expect(likeBtn.classes()).not.toContain('el-button--primary')

    await likeBtn.trigger('click')
    await flush() // 等 submitFeedback 解析

    expect(likeBtn.classes()).toContain('el-button--primary')
    expect(mockSubmitFeedback).toHaveBeenCalledWith(
      expect.objectContaining({ message_id: 'msg-1', is_liked: true }),
    )
    expect(mockElMessage.success).toHaveBeenCalledWith('感谢您的反馈')
  })

  it('点击“无用”将助手消息标记为已踩并显示反馈', async () => {
    await sendAndReceiveReply(wrapper, '你好')
    const dislikeBtn = findActionButton(wrapper, '无用')
    expect(dislikeBtn.classes()).not.toContain('el-button--danger')

    await dislikeBtn.trigger('click')
    await flush()

    expect(dislikeBtn.classes()).toContain('el-button--danger')
    expect(mockSubmitFeedback).toHaveBeenCalledWith(
      expect.objectContaining({ message_id: 'msg-1', is_liked: false }),
    )
    expect(mockElMessage.success).toHaveBeenCalledWith('我们会继续改进')
  })

  it('点击“复制”将助手内容写入剪贴板并显示成功反馈', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    setClipboard(writeText)
    await sendAndReceiveReply(wrapper, '你好')

    await findActionButton(wrapper, '复制').trigger('click')
    await flush()

    expect(writeText).toHaveBeenCalledTimes(1)
    expect(String(writeText.mock.calls[0][0])).toContain(ASSISTANT_REPLY)
    expect(mockElMessage.success).toHaveBeenCalledWith('已复制到剪贴板')
  })

  it('剪贴板写入失败时显示错误反馈', async () => {
    setClipboard(vi.fn().mockRejectedValue(new Error('denied')))
    await sendAndReceiveReply(wrapper, '你好')

    await findActionButton(wrapper, '复制').trigger('click')
    await flush()

    expect(mockElMessage.error).toHaveBeenCalledWith('复制失败')
  })

  // ==================== 滚动 ====================
  it('发送消息后将消息列表滚动到底部', async () => {
    const listEl = wrapper.find('.message-list').element as HTMLElement
    Object.defineProperty(listEl, 'scrollHeight', { configurable: true, value: 500 })

    await typeMessage(wrapper, '滚动')
    await wrapper.find('.send-btn').trigger('click')
    await flush()

    expect(listEl.scrollTop).toBe(500)
  })
})
