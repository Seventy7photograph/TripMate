# 文件说明：Skill 与 MCP 的服务端展示元数据和真实使用边界。
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    display_name: str
    purpose: str
    boundary: str
    surfaces: tuple[str, ...]


SKILL_METADATA: dict[str, SkillMetadata] = {
    "attachment-understanding": SkillMetadata(
        display_name="附件理解",
        purpose="从用户上传的图片、PDF、Markdown 和文本中提取旅行需求。",
        boundary="附件正文始终是不可信数据，不允许改变 Tool 或 MCP 权限。",
        surfaces=("travel_chat",),
    ),
    "budget-optimization": SkillMetadata(
        display_name="预算优化",
        purpose="使用整数最小货币单位计算已知费用、剩余预算和超支状态。",
        boundary="缺少费用事实时不得推断实时价格，只计算已确认金额。",
        surfaces=("travel_chat", "planning"),
    ),
    "destination-research": SkillMetadata(
        display_name="目的地研究与候选地点",
        purpose="通过 AMap 或 MCP 查询真实地点，为问答和规划提供候选。",
        boundary="只使用 Provider 返回的坐标和来源，不生成虚构地点。",
        surfaces=("travel_chat", "planning"),
    ),
    "evidence-verification": SkillMetadata(
        display_name="事实与 Evidence 校验",
        purpose="检查事实来源、有效期和冲突，阻止过期事实被当作实时数据。",
        boundary="缺失或过期 Evidence 不得进入已验证事实集合。",
        surfaces=("planning",),
    ),
    "food-planning": SkillMetadata(
        display_name="餐饮与在地美食规划",
        purpose="结合真实 POI、营业事实和忌口生成餐饮候选。",
        boundary="营业时间未知时明确标记，不承诺实时排队或库存。",
        surfaces=("travel_chat", "planning"),
    ),
    "lodging-area-selection": SkillMetadata(
        display_name="住宿区域选择",
        purpose="比较真实交通锚点、活动区域和预算，推荐住宿片区。",
        boundary="只推荐区域，不承诺酒店房态、价格或可预订结果。",
        surfaces=("travel_chat", "planning"),
    ),
    "route-optimization": SkillMetadata(
        display_name="路线与顺序优化",
        purpose="使用地图 Provider 的真实坐标和道路能力计算点到点路线。",
        boundary="没有坐标或 Provider 结果时不得绘制假路线。",
        surfaces=("travel_chat", "planning"),
    ),
    "safety-briefing": SkillMetadata(
        display_name="旅行安全提示",
        purpose="结合天气、海拔、同行人和活动强度生成风险提醒。",
        boundary="不替代医疗、救援或官方安全建议。",
        surfaces=("travel_chat", "planning"),
    ),
    "social-copywriting": SkillMetadata(
        display_name="旅行社交文案",
        purpose="仅基于已确认事实生成小红书、朋友圈或微博文案。",
        boundary="不自动发布，不编造体验、价格或隐私信息。",
        surfaces=("travel_chat",),
    ),
    "travel-memory": SkillMetadata(
        display_name="授权旅行记忆",
        purpose="只读当前用户明确启用的旅行偏好和约束。",
        boundary="按 owner 隔离，停用或删除的记忆不得进入新任务。",
        surfaces=("travel_chat", "planning"),
    ),
    "trip-intent-routing": SkillMetadata(
        display_name="旅行意图路由",
        purpose="识别旅行任务类型并限制可用 Skill、Tool 和 MCP 白名单。",
        boundary="非旅行任务拒绝，低置信度先澄清。",
        surfaces=("travel_chat", "planning"),
    ),
    "weather-and-clothing": SkillMetadata(
        display_name="天气与穿衣建议",
        purpose="通过 AMap Weather、Open-Meteo 或 Weather MCP 获取真实预报。",
        boundary="预报缺失时标记未知，不生成虚假温度或降水概率。",
        surfaces=("travel_chat", "planning"),
    ),
}


@dataclass(frozen=True, slots=True)
class McpMetadata:
    display_name: str
    purpose: str
    boundary: str
    tools: tuple[str, ...]


MCP_METADATA: dict[str, McpMetadata] = {
    "amap": McpMetadata(
        display_name="高德地点 MCP",
        purpose="通过官方 Streamable HTTP MCP 协议调用真实高德地点搜索。",
        boundary="固定服务端 endpoint；失败时回退本地 AMap Provider Tool。",
        tools=("search_places",),
    ),
    "weather": McpMetadata(
        display_name="天气 MCP",
        purpose="通过官方 Streamable HTTP MCP 协议调用真实天气 Provider。",
        boundary="固定服务端 endpoint；返回事实继续经过 Evidence 和 Schema 校验。",
        tools=("get_weather",),
    ),
}
