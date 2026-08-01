<template>
  <div class="chat-page">
    <!-- 聊天区域 -->
    <div class="chat-container">
      <!-- 消息列表 -->
      <div ref="messageListRef" class="message-list">
        <!-- 欢迎消息 -->
        <div v-if="messages.length === 0" class="welcome-area">
          <div class="welcome-content">
            <div class="welcome-icon">
              <el-icon :size="44" color="#fff">
                <ChatDotRound />
              </el-icon>
            </div>
            <h2>企业知识库智能助手</h2>
            <p class="welcome-desc">
              我是您的企业知识库助手，可以帮您解答关于企业制度、业务流程、产品文档等方面的问题
            </p>
            <div class="quick-questions">
              <p>您可以试试以下问题：</p>
              <div class="question-tags">
                <el-tag
                  v-for="q in quickQuestions"
                  :key="q"
                  class="question-tag"
                  effect="plain"
                  @click="sendQuickQuestion(q)"
                >
                  {{ q }}
                </el-tag>
              </div>
            </div>
          </div>
        </div>

        <!-- 消息气泡 -->
        <div v-else class="messages">
          <div v-for="msg in messages" :key="msg.id" class="message-item" :class="msg.role">
            <div class="message-avatar">
              <el-avatar
                :size="36"
                :icon="msg.role === 'user' ? UserFilled : ChatDotRound"
                :style="{
                  background:
                    msg.role === 'user'
                      ? 'linear-gradient(135deg, #2d6cdf, #5b6ef5)'
                      : 'linear-gradient(135deg, #1a2342, #2d3561)',
                  color: '#fff',
                }"
              />
            </div>
            <div class="message-content">
              <div class="message-bubble">
                <div
                  v-if="msg.role === 'assistant' && msg.isStreaming"
                  class="streaming-text"
                  v-html="renderMarkdown(msg.content)"
                />
                <div v-else class="message-text" v-html="renderMarkdown(msg.content)" />
              </div>

              <!-- 来源引用 -->
              <div v-if="msg.sources && msg.sources.length > 0" class="message-sources">
                <el-collapse>
                  <el-collapse-item title="参考来源">
                    <div v-for="(source, idx) in msg.sources" :key="idx" class="source-item">
                      <div class="source-header">
                        <span class="source-title">来源 {{ idx + 1 }}</span>
                        <el-tag size="small" type="info"> 相似度: {{ source.score }} </el-tag>
                      </div>
                      <p class="source-preview">
                        {{ source.content_preview }}
                      </p>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>

              <!-- 消息操作 -->
              <div v-if="msg.role === 'assistant' && !msg.isStreaming" class="message-actions">
                <el-button
                  link
                  size="small"
                  :type="msg.is_liked === true ? 'primary' : ''"
                  @click="likeMessage(msg, true)"
                >
                  <el-icon><ArrowUp /></el-icon>有用
                </el-button>
                <el-button
                  link
                  size="small"
                  :type="msg.is_liked === false ? 'danger' : ''"
                  @click="likeMessage(msg, false)"
                >
                  <el-icon><ArrowDown /></el-icon>无用
                </el-button>
                <el-button link size="small" @click="copyMessage(msg)">
                  <el-icon><CopyDocument /></el-icon>复制
                </el-button>
              </div>
            </div>
          </div>

          <!-- 加载中 -->
          <div v-if="isLoading" class="message-item assistant">
            <div class="message-avatar">
              <el-avatar
                :size="36"
                :icon="ChatDotRound"
                style="background: linear-gradient(135deg, #1a2342, #2d3561); color: #fff"
              />
            </div>
            <div class="message-content">
              <div class="message-bubble loading">
                <el-icon class="is-loading">
                  <Loading />
                </el-icon>
                <span>正在思考中...</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-area">
        <div class="input-toolbar">
          <el-select
            v-model="selectedKBs"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择知识库（默认全部）"
            size="small"
            style="width: 240px"
          >
            <el-option v-for="kb in knowledgeBases" :key="kb.id" :label="kb.name" :value="kb.id" />
          </el-select>
        </div>

        <div class="input-box">
          <el-input
            v-model="inputMessage"
            type="textarea"
            :rows="2"
            placeholder="请输入您的问题..."
            resize="none"
            @keyup.enter.ctrl="sendMessage"
          />
          <el-button
            type="primary"
            class="send-btn"
            :loading="isLoading"
            :disabled="!inputMessage.trim()"
            @click="sendMessage"
          >
            <el-icon><Promotion /></el-icon>
          </el-button>
        </div>

        <div class="input-hint">
          <span>Ctrl + Enter 发送</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import {
  ChatDotRound,
  UserFilled,
  Promotion,
  Loading,
  ArrowUp,
  ArrowDown,
  CopyDocument,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { ChatMessage, KnowledgeBase } from '@/types'

const messageListRef = ref<HTMLDivElement>()
const inputMessage = ref('')
const isLoading = ref(false)
const selectedKBs = ref<string[]>([])

const quickQuestions = [
  '如何查询公司规章制度？',
  '请假流程是什么？',
  '报销流程是怎样的？',
  '入职手续如何办理？',
]

const knowledgeBases = ref<KnowledgeBase[]>([])

const messages = ref<(ChatMessage & { isStreaming?: boolean })[]>([])

const sendQuickQuestion = (question: string) => {
  inputMessage.value = question
  sendMessage()
}

const sendMessage = async () => {
  const content = inputMessage.value.trim()
  if (!content || isLoading.value) return

  // 添加用户消息
  const userMsg: ChatMessage & { isStreaming?: boolean } = {
    id: Date.now().toString(),
    role: 'user',
    content,
    created_at: new Date().toISOString(),
  }
  messages.value.push(userMsg)
  inputMessage.value = ''
  isLoading.value = true

  await scrollToBottom()

  // TODO: 调用后端API进行流式对话
  // 模拟AI回复
  setTimeout(() => {
    const assistantMsg: ChatMessage & { isStreaming?: boolean } = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content:
        '您好！我是企业知识库智能助手。\n\n关于您的问题，我可以为您提供以下信息：\n\n1. **制度规范**：包括考勤制度、报销制度、晋升制度等\n2. **业务流程**：请假流程、审批流程、入职离职流程等\n3. **产品文档**：产品手册、操作指南、常见问题等\n\n请问您具体想了解哪方面的业务？',
      sources: [
        {
          document_id: 'doc-001',
          chunk_index: 0,
          score: 0.92,
          content_preview: '公司员工规章制度手册...',
        },
      ],
      created_at: new Date().toISOString(),
      isStreaming: false,
    }
    messages.value.push(assistantMsg)
    isLoading.value = false
    nextTick(scrollToBottom)
  }, 1500)
}

const renderMarkdown = (content: string) => {
  // 清洗 HTML 防止 XSS（RAG 上下文来自用户上传文档，可能含恶意脚本）
  return DOMPurify.sanitize(marked.parse(content, { breaks: true }) as string)
}

const likeMessage = (msg: ChatMessage, liked: boolean) => {
  msg.is_liked = liked
  ElMessage.success(liked ? '感谢您的反馈' : '我们会继续改进')
}

const copyMessage = async (msg: ChatMessage) => {
  try {
    await navigator.clipboard.writeText(msg.content)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}
</script>

<style scoped lang="scss">
.chat-page {
  display: flex;
  height: calc(100vh - 40px);
  gap: 16px;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-thumb {
    background: #e5e6eb;
    border-radius: 3px;
  }
}

.welcome-area {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;

  .welcome-content {
    text-align: center;
    max-width: 600px;
  }

  .welcome-icon {
    width: 88px;
    height: 88px;
    margin: 0 auto 20px;
    background: linear-gradient(135deg, #2d6cdf 0%, #5b6ef5 100%);
    border-radius: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 8px 24px rgba(45, 108, 223, 0.3);
  }

  h2 {
    font-size: 24px;
    color: #1d2129;
    margin-bottom: 8px;
  }

  .welcome-desc {
    color: #4e5969;
    margin-bottom: 32px;
    line-height: 1.6;
  }

  .quick-questions {
    p {
      color: var(--text-tertiary);
      margin-bottom: 12px;
      font-size: 14px;
    }

    .question-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      justify-content: center;

      .question-tag {
        cursor: pointer;
        transition: all 0.2s ease;
        border-radius: 8px;

        &:hover {
          color: #2d6cdf;
          border-color: #2d6cdf;
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(45, 108, 223, 0.15);
        }
      }
    }
  }
}

.messages {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.message-item {
  display: flex;
  gap: 12px;

  &.user {
    flex-direction: row-reverse;

    .message-content {
      align-items: flex-end;
    }

    .message-bubble {
      background: linear-gradient(135deg, #2d6cdf 0%, #5b6ef5 100%);
      color: #fff;
      border-radius: 14px 14px 2px 14px;
      box-shadow: 0 4px 12px rgba(45, 108, 223, 0.25);
    }
  }

  &.assistant {
    .message-bubble {
      background: var(--bg-card);
      color: var(--text-primary);
      border-radius: 14px 14px 14px 2px;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
      border: 1px solid var(--border-color);
    }
  }
}

.message-avatar {
  flex-shrink: 0;
}

.message-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 70%;
}

.message-bubble {
  padding: 12px 16px;
  line-height: 1.6;
  word-break: break-word;

  &.loading {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #86909c;
  }

  :deep(p) {
    margin: 0 0 8px;

    &:last-child {
      margin-bottom: 0;
    }
  }

  :deep(ul, ol) {
    margin: 8px 0;
    padding-left: 20px;
  }

  :deep(code) {
    background: rgba(45, 108, 223, 0.08);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.9em;
  }

  :deep(pre) {
    background: #1d1f27;
    color: #ccc;
    padding: 12px;
    border-radius: 8px;
    overflow-x: auto;

    code {
      background: none;
      padding: 0;
    }
  }
}

.message-sources {
  margin-top: 4px;

  .source-item {
    padding: 10px 12px;
    background: var(--bg-subtle);
    border-radius: 10px;
    margin-bottom: 8px;

    .source-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 4px;

      .source-title {
        font-size: 13px;
        font-weight: 500;
        color: var(--text-secondary);
      }
    }

    .source-preview {
      font-size: 12px;
      color: var(--text-tertiary);
      line-height: 1.5;
      margin: 0;
    }
  }
}

.message-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;

  .message-item.assistant:hover & {
    opacity: 1;
  }
}

.input-area {
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-card);
}

.input-toolbar {
  margin-bottom: 8px;
}

.input-box {
  display: flex;
  gap: 8px;
  align-items: flex-end;

  :deep(.el-textarea__inner) {
    border-radius: 12px;
    padding: 12px 16px;
    font-size: 14px;
    resize: none;

    &:focus {
      box-shadow: 0 0 0 2px rgba(45, 108, 223, 0.3) inset;
    }
  }

  .send-btn {
    width: 44px;
    height: 44px;
    padding: 0;
    border-radius: 12px;
    flex-shrink: 0;
    border: none;
    background: linear-gradient(135deg, #2d6cdf 0%, #5b6ef5 100%);
    box-shadow: 0 4px 12px rgba(45, 108, 223, 0.3);

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 16px rgba(45, 108, 223, 0.4);
    }

    &:disabled {
      background: #c9cdd4;
      box-shadow: none;
    }
  }
}

.input-hint {
  margin-top: 6px;
  text-align: right;
  font-size: 12px;
  color: #c9cdd4;
}
</style>
