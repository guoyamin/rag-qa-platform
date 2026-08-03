# 错题集（Lessons Learned）

本项目开发过程中遇到的问题与教训，按类别整理，供团队和 AI 协作参考，避免重复踩坑。

## 目录

| 文件 | 内容 |
|------|------|
| [Harness Engineering 搭建复盘](./harness-engineering.md) | 门禁体系搭建踩坑：方案级错误（分支保护死局/release-please/门禁纯度等）+ 实施坑（detect-secrets 基线/PAT/prettier 对齐等） |
| [AI 编码陷阱](./ai-coding-pitfalls.md) | AI 辅助编码引入的 bug 与规避（Edit/类型声明/再导出/认证循环/未自检） |
| [开发环境问题](./dev-environment.md) | Docker / vite / worktree 等环境陷阱 |
| [安全与规范](./security-compliance.md) | 安全漏洞与编码规范违反 |

## 如何使用

- **新功能开发前**：浏览相关类别，避免重复踩坑
- **AI 协作时**：把相关条目作为上下文提供给 AI，减少同类错误
- **遇到新问题**：追加到对应文件，遵循「问题 → 后果 → 教训 → 避免」结构

## 文档结构约定

每条错题包含：
1. **问题**：发生了什么
2. **后果**：造成的影响
3. **教训**：根本原因
4. **如何避免**：具体规避方式（含代码示例）
