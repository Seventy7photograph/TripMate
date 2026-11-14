# evidence-verification

## 目标

只检查已经存在的 EvidenceRecord，识别缺失、过期、冲突和来源不完整。该 Skill 不访问外部网络，也不补造事实。

## 允许的 Tools

无外部 Tool。

## 输入

- `records`：现有 Evidence 列表，包含事实类型、Provider、查询时间、有效期、freshness、置信度和值。

## 输出

- `issues`：`missing`、`stale`、`conflict` 或 `unsupported_claim` 问题。
- `verified_count`：通过验证的记录数量。

## 使用条件

- 行程或回答需要验证事实可追溯性。
- 需要区分已确认、过期、冲突和未知数据。
- 需要为引用来源提供最终质量检查。

## 禁止项

- 不得调用 Web、Tool、MCP、数据库或文件系统。
- 不得把过期数据当作实时数据。
- 不得修改原始 Evidence 或伪造缺失字段。

## 失败回退

记录不完整或 schema 无效时返回明确问题并回退 `existing_itinerary_graph`，不输出“已验证”。

## 验收样例

1. 天气记录有效期已过，返回 `stale`。
2. 同一地点两个 Provider 的营业时间冲突，返回 `conflict`。
3. 价格字段没有 Evidence ID，返回 `missing` 或 `unsupported_claim`。
