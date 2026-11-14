# TripMate 提示词位置清单

静态系统 Prompt 使用 `apps/api/prompts/` 下的版本化 Markdown 统一管理。动态
用户文本、响应 Schema、历史对话、Tool 结果和校验错误继续由类型化 Python 代码
构造，不进入静态 Prompt 文件。

## Agent 系统提示词

| Agent | 能力 | Prompt ID | 版本 | 文件 |
| --- | --- | --- | --- | --- |
| `requirement-parser` | 旅行需求解析 | `system` | `1.0.0` | `apps/api/prompts/agents/requirement-parser/system/1.0.0.md` |
| `research-planner` | 地点研究 Tool 选择 | `tool-selection` | `1.0.0` | `apps/api/prompts/agents/research-planner/tool-selection/1.0.0.md` |
| `itinerary-composer` | 行程编排 | `system` | `1.0.0` | `apps/api/prompts/agents/itinerary-composer/system/1.0.0.md` |
| `travel-chat` | 旅行意图路由 | `intent-router` | `1.0.0` | `apps/api/prompts/agents/travel-chat/intent-router/1.0.0.md` |
| `travel-chat` | 旅行问答与 Web 来源 | `answer` | `1.0.0` | `apps/api/prompts/agents/travel-chat/answer/1.0.0.md` |

## 动态提示词构造位置

| 职责 | 文件 | 构造入口 |
| --- | --- | --- |
| 需求解析 Schema、附件、修复轮次 | `apps/api/app/agents/requirement_parser.py` | `RequirementParser._user_prompt()` |
| Tool 定义、TripBrief 与检索请求 | `apps/api/app/agents/research_planner.py` | `LlmResearchPlanner.plan()` |
| 候选地点、行李约束与 JSON Schema | `apps/api/app/agents/itinerary_composer.py` | `LlmItineraryComposer.compose()` |
| 历史、当前消息、Skill 元数据与 Tool 结果 | `apps/api/app/agents/travel_chat.py` | `_intent_prompt()`、`_answer_prompt()` |

## 安全与不可信输入

- `apps/api/app/services/prompt_safety.py`：Prompt Injection 模式识别。
- `apps/api/app/services/url_safety.py`：Provider URL 与私网地址限制。
- `apps/api/app/agents/*.py`：将用户文本、附件、历史和 Tool 结果包装为不可信数据。

## 产品 Skill 指令

- `skills/*/SKILL.md`：供人和 Agent 阅读的任务方法、禁止项、回退和验收样例。
- `skills/*/skill.yaml`：机器可读的 Schema、Tool 白名单、预算和状态。

## 修改约定

1. 静态系统提示词只能放在 `apps/api/prompts/agents/`，使用精确版本引用。
2. 不把密钥、用户隐私、完整网页正文或内部 Tool 实现写入 Prompt。
3. 实时事实优先使用受控 Tool/Web citations，并明确未知或未确认信息。
4. Prompt 版本变更必须更新本清单、运行审计和固定评测样例。
