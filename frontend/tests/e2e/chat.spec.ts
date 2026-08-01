/**
 * 智能问答 E2E 测试（纯聊天，不 RAG）
 *
 * 覆盖完整流程：
 *   登录 -> 进入聊天页 -> 输入问题 -> 点发送 -> 等待助手回复（真实 DeepSeek，30s 超时）-> 验证回复展示
 *
 * 说明：
 * - 助手回复来自真实 LLM（DeepSeek），存在网络延迟，等待超时统一设为 30s。
 * - 加载态气泡为 .message-bubble.loading（"正在思考中..."），真实回复气泡不带 .loading，
 *   以此区分加载态与最终回复，避免误把"正在思考中..."当作回复。
 */
import { test, expect } from '@playwright/test'

test.describe('智能问答', () => {
  test('登录后进入聊天页，页面正常加载', async ({ page }) => {
    // 1. 登录
    await page.goto('/login')
    await page.waitForSelector('.login-page', { timeout: 10000 })

    await page.locator('input[placeholder="请输入工号/用户名"]').fill('admin')
    await page.locator('input[placeholder="请输入密码"]').fill('Admin@123')
    await page.getByRole('button', { name: /登 录/ }).click()

    // 等待跳转到聊天页（登录成功 router.push('/')，'/' 重定向到 '/chat'）
    await page.waitForURL(/\/chat$/, { timeout: 20000 })
    await page.waitForSelector('.chat-page', { timeout: 10000 })

    // 2. 验证聊天页加载：欢迎区展示（无消息时）
    await expect(page.locator('.welcome-area')).toBeVisible()
    await expect(page.locator('.welcome-area h2')).toContainText('企业知识库智能助手')

    // 输入框与发送按钮可见
    await expect(page.locator('textarea[placeholder="请输入您的问题..."]')).toBeVisible()
    await expect(page.locator('.send-btn')).toBeVisible()
  })

  test('发送问题后收到助手回复', async ({ page }) => {
    // 真实 LLM 有延迟，整体放宽到 90s（含登录 + 30s 回复等待）
    test.setTimeout(90000)

    // 1. 登录
    await page.goto('/login')
    await page.waitForSelector('.login-page', { timeout: 10000 })

    await page.locator('input[placeholder="请输入工号/用户名"]').fill('admin')
    await page.locator('input[placeholder="请输入密码"]').fill('Admin@123')
    await page.getByRole('button', { name: /登 录/ }).click()

    await page.waitForURL(/\/chat$/, { timeout: 20000 })
    await page.waitForSelector('.chat-page', { timeout: 10000 })

    // 2. 输入问题
    const inputBox = page.locator('textarea[placeholder="请输入您的问题..."]')
    await inputBox.fill('你好')

    // 3. 点发送
    await page.locator('.send-btn').click()

    // 验证用户消息已展示
    await expect(page.locator('.message-item.user .message-bubble').first()).toContainText('你好', {
      timeout: 10000,
    })

    // 4. 等待助手回复（真实 DeepSeek，有延迟，超时 30s）
    //    "正在思考中..." 为 .message-bubble.loading；真实回复气泡不带 .loading
    const assistantBubble = page
      .locator('.message-item.assistant .message-bubble:not(.loading)')
      .first()
    await assistantBubble.waitFor({ state: 'visible', timeout: 30000 })

    // 5. 验证回复展示（非空文本）
    const replyText = ((await assistantBubble.textContent()) ?? '').trim()
    expect(replyText.length).toBeGreaterThan(0)
  })
})
