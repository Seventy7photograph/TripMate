# Changelog

TripMate 使用语义化版本。格式参考 Keep a Changelog。

## [1.1.0] - 2026-11-15

### Added

- 旅行对话能力矩阵、通用旅行信号分类、模型误判纠偏和固定 Prompt 评测。
- 服务端 `planning_draft`、跨轮字段合并、确定性中文日期解析和预算可选。
- 结构化交通策略，覆盖自驾、租车、公共交通、步行、高铁、航班和混合交通。
- `travel-memory` 在旅行问答中真实执行，记忆上下文进入回答 Prompt。
- 对话驱动的行程创建、已有行程更新和重新规划；显式应用时保留旧版本快照。
- 长对话独立滚动布局、稳定底部输入框和模型思考加载动画。
- 统一 Skill Runtime、真实 Skill 调用、AgentRun 失败审计和 12 个生产 Skills。
- 真实 AMap/Weather Streamable HTTP MCP Server、Gateway 配额、健康和 Provider 回退。
- Admin Skill 多版本、工具健康、Provider 实时状态和 5 秒刷新。

### Fixed

- 路线缓存键加入起终点坐标哈希与坐标系，地点移动后不再复用旧路线。
- 退出登录递增用户 `token_version`，使现有访问 Token 立即失效。
- 生产环境强制独立 `MODEL_CONFIG_ENCRYPTION_KEY`、ClamAV 和显式出站代理。
- 上传接入 ClamAV `INSTREAM`，恶意文件阻断，scanner 故障失败关闭。
- 备份恢复覆盖上传文件，并校验 SHA-256、文件计数与 Alembic revision。
- Skill Manifest 增加 SHA-256 lock、CI 校验和 `CODEOWNERS`。
- 修复长对话消息被输入框覆盖、页面滚动抖动和模型等待期间空白。
- 修复续聊不发送 `conversation_id`、规划草稿不持久化和重复创建 Trip。

### Security

- 生产 Provider 只允许显式出站代理和固定 allowed-host 策略。
- 上传、附件、Tool、Skill、MCP 和历史消息继续按不可信输入分层隔离。
- Skill 启停、版本、预算、Tool/MCP 白名单和输出 Schema 在运行时校验。
- JWT 撤销、资源归属、管理员权限、限流和数据库版本锁回归通过。

## [1.0.0] - 2026-11-15

### Added

- 自然语言旅行需求解析、LangGraph 单主 Agent 和有限重规划。
- EvidenceRecord、事实来源、freshness、置信度和冲突验证。
- 受控 Skill Registry、Skill Router、启停状态和 AgentRun 审计。
- 目的地研究、路线优化、预算、天气、餐饮、住宿、安全、附件、记忆和社媒文案 Skills。
- Typed Tool Registry、ToolContext、统一超时、调用预算和审计。
- AMap Places、Route、Weather、Nearby、Place Detail/Facts、Route Matrix。
- Open-Meteo Weather、Geocoding 和 Elevation 降级。
- 只读 MCP Gateway、固定 connector allowlist、健康状态、配额和 Provider fallback。
- 逐日行程编辑、版本冲突、地图路线、预算、收藏、分享与导出。
- 用户授权旅行记忆和删除权。
- Admin Agent Runs、成本、Provider、MCP、Skills、模型配置和功能开关。
- 按 Provider、模型和 Skill 的成本聚合。
- Docker Compose、备份恢复、Playwright E2E、性能测试和依赖审计。
- 30+ Skill 发布质量评测场景和回滚开关。

### Security

- JWT、Argon2、资源归属校验、管理员角色校验和 Redis 限流。
- 上传文件类型、大小、文件头和图片结构校验。
- Prompt Injection 隔离、URL SSRF 阻断和安全响应头。
- MCP 内容不可信包装、固定 endpoint、严格 Schema 和白名单。
- 功能开关支持 Agent Skills、Skill Router、MCP Gateway 和 Weather Provider 独立回滚。

### Known Boundaries

- 飞机路线是地图示意，不包含真实航线、航班号、机场或票价。
- 火车/高铁票务、航班库存、酒店房态和预订支付尚未接入。
- 实际 Live Provider 可用性和配额取决于部署者自己的账户。
- 仓库提供 Docker 部署配置，但 V1.1.0 不包含公共托管实例。
