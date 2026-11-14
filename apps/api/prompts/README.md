# TripMate Prompt Catalog

静态系统 Prompt 按 Agent、职责和版本拆分为独立 Markdown 文件。动态用户文本、
Schema、历史对话、Tool 结果和重试错误仍由类型化 Python 代码构造。

## 目录约定

```text
prompts/agents/<agent>/<prompt-id>/<semver>.md
```

- `agent`、`prompt_id` 只允许小写字母、数字和连字符。
- 版本使用 `major.minor.patch`，代码必须固定引用精确版本。
- 每个文件只保存一个静态系统 Prompt，不建立聚合巨型文件。
- 生产代码不得接受用户输入作为目录片段。

## 文件 Schema

```markdown
---
schema_version: 1
agent: travel-chat
prompt_id: intent-router
version: 1.0.0
description: Travel intent routing policy
---
System prompt content.
```

加载器会验证 YAML、字段类型、路径与元数据一致性、UTF-8、重复版本和符号链接
逃逸。位置索引维护在 [`INVENTORY.md`](INVENTORY.md)。
