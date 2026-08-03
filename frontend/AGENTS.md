# Frontend AGENTS — Vue 3 前端工作指令

> 本文件是 AI 在 `frontend/` 下工作的**模块级指令**，叠加在根 `AGENTS.md` 之上。

## 技术栈

Vue 3（`<script setup>` + Composition API）· TypeScript（vue-tsc 强制）· Vite · Pinia（含 persistedstate）· Vue Router · Element Plus · axios · openapi-typescript

## 目录约定

```
src/
  views/        页面（路由级）
  components/   可复用组件（PascalCase 多词名）
  composables/  组合式函数（use* 前缀）
  api/          axios 封装 + 按模块请求函数
  stores/       Pinia store
  router/       路由（懒加载 + 鉴权守卫）
  types/        TS 类型（含 OpenAPI 生成的 API 类型）
```

## 核心约定

- **类型不手抄**：后端 DTO 类型由 `openapi-typescript` 从 OpenAPI 生成（`types/` 下），改后端 schema 后跑 `make gen-client` 同步。禁止手写重复的接口类型。
- 组件用 `<script setup lang="ts">`；状态用 Pinia（`defineStore`），需要持久化加 `persist` 选项
- API 调用走 `src/api/` 封装（统一 axios 实例 + 拦截器：token 注入、错误处理），不在组件里直接 `axios`
- 路由懒加载（`() => import(...)`），鉴权守卫在 `router/`

## 门禁（提交前）

`pnpm build` = `vue-tsc --noEmit` + `vite build`（类型检查强制）；`pnpm lint`（eslint）；`pnpm test:unit`（vitest）。CI 前端门禁 = type-check + lint + vitest。

## 约定

- 响应解包：后端统一 `{code, message, data}`，axios 拦截器通常解 `data`；错误按 `code` 处理（见 `docs/standards/api-contract.md`）
- 样式用 scoped 或 CSS Modules，避免全局污染
- 改 API 调用 → 确认类型来自生成；改路由 → 同步 `router/` 和权限
