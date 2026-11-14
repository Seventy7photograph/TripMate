---
name: social-copywriting
version: 1.0.0
status: active
owner: tripmate
---

# 社交文案生成

## 用途

将已经确认的 TripMate 行程或已授权旅行记忆转换为可用的社交平台文案。不得编造旅行事实，不得自动发布，也不得把建议文案写成用户实际经历。

本 Skill 已提供受控 handler，不会自动发布，也不会调用社交平台写接口。

## 输入

```text
SocialCopyInput
- platform: xiaohongshu | wechat_moments | weibo | generic
- goal: share | inspire | diary | recommendation
- source_itinerary
- verified_facts[]
- tone: quiet | practical | vivid
- language
- length_limit
```

## 输出

```text
SocialCopyOutput
- title
- body
- hashtags[]
- image_suggestions[]
- evidence_links[]
- warnings[]
- facts_used[]
- auto_published: false
```

## 规则

- 只能使用已确认行程和 Evidence 中的事实。
- 不得编造价格、营业时间、预约状态、评分或个人体验。
- 第一人称建议文案与事实描述必须区分。
- 用户没有提供时，不得声称已经到访、用餐、预订或付款。
- 平台风格不明确时，提供有标签的中文备选。
- 使用精确酒店、住址、儿童、健康状况等敏感信息前必须先询问。
- 没有明确确认和单独审核过的写 Tool 时，不得发布、发消息或调用社交平台。
- `facts_used` 必须来自 confirmed_facts；不得用模型生成内容替代事实引用。

## 成本控制

- 默认生成 1 份文案，最多提供 2 个风格备选。
- 复用父 AgentRun 已加载的行程和 Evidence。
- 按平台和输出语言限制 Token。
- 用户没有要求视觉素材时，不调用图片生成或搜索 Tool。

## 验收

- 每个事实性表述都能映射到行程或 Evidence。
- 受众、平台或语气不明确时返回简短澄清或有标签候选。
- 个人隐私信息最小化。
- 平台凭据不得出现在 Prompt、输出、日志或文案中。
