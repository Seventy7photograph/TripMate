# Contributing to TripMate

感谢你愿意改进 TripMate。提交代码前，请先创建 Issue 描述问题、动机和预期行为。
安全问题不要公开提交 Issue，请遵循 [SECURITY.md](SECURITY.md)。

## 开发流程

1. Fork 仓库并从 `main` 创建分支。
2. 保持修改范围聚焦，避免无关重构。
3. 新功能或缺陷修复必须包含测试。
4. 更新面向用户的文档或示例。
5. 提交 PR 前运行完整检查。

分支命名建议：

```text
feat/short-description
fix/short-description
docs/short-description
```

## 本地开发

```bash
corepack pnpm install
uv sync --project apps/api
cp .env.example .env
corepack pnpm dev
```

Windows PowerShell 使用 `Copy-Item .env.example .env`。

## 质量门禁

```bash
corepack pnpm verify
corepack pnpm e2e
corepack pnpm audit --audit-level high
python -m uv tool run pip-audit --path apps/api/.venv
```

如果某项检查因环境原因无法执行，请在 PR 中说明具体命令、错误和替代验证。

## 代码约定

- Python 使用 Ruff、Mypy 和类型化 Pydantic 契约。
- TypeScript 使用严格类型检查、ESLint 和 Vue 组合式 API。
- 金额使用整数最小货币单位或 `Decimal`。
- 外部 URL、上传文件、Agent Tool 结果和 MCP 内容均视为不可信输入。
- Provider 访问必须经过 Adapter，业务层不得硬编码供应商 URL。
- 数据库结构变更必须附带 Alembic 迁移。

## 测试要求

- 缺陷修复：先提交能复现问题的失败测试。
- API 变更：覆盖输入校验、权限隔离、异常和成功路径。
- UI 变更：补组件测试，关键流程补 Playwright。
- Agent/Tool 变更：覆盖白名单、超时、预算和 Prompt Injection 边界。

## 提交信息

推荐使用 Conventional Commits：

```text
feat(agent): add weather evidence fallback
fix(itinerary): prevent stale version writes
docs(readme): clarify provider setup
```

## PR 内容

PR 描述应包含：

- 问题与目标
- 主要实现方案
- 用户可见变化
- 测试命令与结果
- 数据库或配置变更
- 已知限制和回滚方式

提交 PR 即表示你同意以项目的 MIT License 授权该贡献。
