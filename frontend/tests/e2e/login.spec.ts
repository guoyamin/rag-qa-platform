import { test, expect } from '@playwright/test'

test('login page loads', async ({ page }) => {
  await page.goto('/login')

  // 检查页面标题
  await expect(page.locator('h2')).toContainText('欢迎登录')

  // 检查表单元素
  await expect(page.locator('input[placeholder="请输入工号/用户名"]')).toBeVisible()
  await expect(page.locator('input[placeholder="请输入密码"]')).toBeVisible()
  await expect(page.locator('button:has-text("登 录")')).toBeVisible()
})

test('login with empty fields shows validation', async ({ page }) => {
  await page.goto('/login')

  // 表单默认预填了 admin / Admin@123，先清空以模拟空字段提交
  await page.locator('input[placeholder="请输入工号/用户名"]').clear()
  await page.locator('input[placeholder="请输入密码"]').clear()

  // 点击登录按钮触发整表校验（formRef.validate 校验所有字段）
  await page.click('button:has-text("登 录")')

  // 等待验证消息（用户名和密码两项均会触发，取第一个）
  await expect(page.locator('.el-form-item__error').first()).toBeVisible()
})
