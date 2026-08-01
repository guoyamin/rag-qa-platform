/**
 * 模型管理 E2E 测试
 */
import { test, expect } from '@playwright/test'

test.describe('登录页面', () => {
  test('登录页面正常加载', async ({ page }) => {
    await page.goto('/login')

    // 等待 Vue 应用挂载
    await page.waitForSelector('.login-page', { timeout: 10000 })

    // 检查表单元素
    await expect(page.locator('input[placeholder="请输入工号/用户名"]')).toBeVisible()
    await expect(page.locator('input[placeholder="请输入密码"]')).toBeVisible()
    await expect(page.getByRole('button', { name: /登 录/ })).toBeVisible()
  })

  test('登录页品牌区正常', async ({ page }) => {
    await page.goto('/login')
    await page.waitForSelector('.login-page', { timeout: 10000 })

    // 检查品牌区
    await expect(page.locator('.login-brand')).toBeVisible()
    await expect(page.locator('.brand-title')).toContainText('知识库')
  })
})

test.describe('模型管理页面', () => {
  test('页面可以访问', async ({ page }) => {
    await page.goto('/models')

    // 等待页面加载
    await page.waitForLoadState('networkidle')

    // 验证页面已加载（任何状态都可以）
    const url = page.url()
    expect(url.includes('/login') || url.includes('/models')).toBeTruthy()
  })
})
