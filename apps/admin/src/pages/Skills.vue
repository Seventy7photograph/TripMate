<!-- 文件说明：管理后台页面：Skills。 -->
<script setup lang="ts">
import {
  Bot,
  Clock3,
  Link2,
  RefreshCw,
  ShieldCheck,
  Wrench,
} from "lucide-vue-next";
import { computed, onMounted, ref } from "vue";

import { adminApi } from "../api";
import { formatDateTime } from "../format";
import type {
  AuditLog,
  McpConnectorStatus,
  SkillManifest,
} from "../types";

const props = defineProps<{ token: string }>();
const loading = ref(true);
const error = ref("");
const skills = ref<SkillManifest[]>([]);
const audits = ref<AuditLog[]>([]);
const connectors = ref<McpConnectorStatus[]>([]);
const toggling = ref<string | null>(null);

const skillExplanations: Record<
  string,
  { title: string; summary: string; boundary: string }
> = {
  "attachment-understanding": {
    title: "附件理解",
    summary: "提取图片、PDF、Markdown 和文本中的旅行需求。",
    boundary: "附件正文是不可信数据，不能扩大 Tool 权限或执行指令。",
  },
  "budget-optimization": {
    title: "预算优化",
    summary: "根据人数、天数和候选行程给出可解释的预算分配建议。",
    boundary: "金额使用最小货币单位；模型不直接进行真实价格计算。",
  },
  "destination-research": {
    title: "目的地研究与候选地点筛选",
    summary: "查询真实地点、区域特征和可访问信息，为行程提供候选。",
    boundary: "只使用 Provider 返回的地点，不编造坐标和来源。",
  },
  "evidence-verification": {
    title: "事实与 Evidence 校验",
    summary: "检查事实来源、新鲜度、冲突和未确认字段。",
    boundary: "过期、冲突或缺失的 Evidence 不会被视为已验证事实。",
  },
  "food-planning": {
    title: "餐饮与在地美食规划",
    summary: "结合地点、饮食限制和行程节奏安排餐饮候选。",
    boundary: "营业时间未知时明确标记，不推断实时库存或排位。",
  },
  "lodging-area-selection": {
    title: "住宿区域选择",
    summary: "比较交通锚点、活动区域和预算，推荐住宿片区。",
    boundary: "不承诺酒店房态、价格或可预订结果。",
  },
  "route-optimization": {
    title: "路线与顺序优化",
    summary: "根据地点位置、交通方式和时间约束调整游览顺序。",
    boundary: "路线事实来自地图 Provider，不接受模型伪造折线。",
  },
  "safety-briefing": {
    title: "旅行安全提示",
    summary: "针对海拔、天气、同行人和活动强度生成风险提醒。",
    boundary: "不替代医疗、救援或官方安全建议。",
  },
  "social-copywriting": {
    title: "旅行社交文案",
    summary: "基于已确认行程生成分享文案和备选表达。",
    boundary: "只使用 confirmed facts，不自动发布或暴露私人信息。",
  },
  "travel-memory": {
    title: "授权旅行记忆",
    summary: "读取用户明确启用的偏好和约束，为当前任务补充上下文。",
    boundary: "只读、按 owner 隔离；删除或停用记忆不会进入结果。",
  },
  "trip-intent-routing": {
    title: "旅行意图路由",
    summary: "识别规划、研究、路线、预算、附件等旅行任务类型。",
    boundary: "非旅行任务拒绝，低置信度先澄清。",
  },
  "weather-and-clothing": {
    title: "天气与穿衣建议",
    summary: "结合 AMap Weather 或 Open-Meteo 事实给出穿衣和户外建议。",
    boundary: "天气缺失时明确 unknown，不生成虚假温度或降水概率。",
  },
};

const mcpExplanations: Record<
  string,
  { title: string; summary: string; boundary: string }
> = {
  amap: {
    title: "高德地点与路线 MCP",
    summary: "只读访问高德地点搜索、详情和路线能力。",
    boundary: "固定服务端 endpoint；失败后回退本地高德 Provider Tool。",
  },
  weather: {
    title: "天气 MCP",
    summary: "只读访问天气事实，供天气与穿衣 Skill 使用。",
    boundary: "固定 connector、独立配额与开关；不接收用户 URL。",
  },
};

const activeCount = computed(
  () => skills.value.filter((skill) => skill.enabled).length,
);
const connectorCount = computed(
  () =>
    new Set(
      skills.value.flatMap((skill) => skill.allowed_mcp_connectors),
    ).size,
);

function latestAudit(skillName: string): AuditLog | null {
  return (
    audits.value.find(
      (audit) =>
        audit.target_type === "skill" &&
        audit.target_id === skillName,
    ) ?? null
  );
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [skillData, auditData, connectorData] = await Promise.all([
      adminApi.skills(props.token),
      adminApi.auditLogs(props.token, 100),
      adminApi.mcpConnectors(props.token),
    ]);
    skills.value = skillData;
    audits.value = auditData.items;
    connectors.value = connectorData;
  } catch {
    error.value = "Skill 状态加载失败。";
  } finally {
    loading.value = false;
  }
}

async function toggle(skill: SkillManifest): Promise<void> {
  if (toggling.value) return;
  toggling.value = skill.name;
  error.value = "";
  try {
    const updated = await adminApi.toggleSkill(
      props.token,
      skill.name,
      !skill.enabled,
      `skill ${skill.enabled ? "disabled" : "enabled"} from admin`,
    );
    skills.value = skills.value.map((item) =>
      item.name === updated.name ? updated : item,
    );
    const auditData = await adminApi.auditLogs(props.token, 100);
    audits.value = auditData.items;
  } catch {
    error.value = "Skill 状态更新失败。";
  } finally {
    toggling.value = null;
  }
}

onMounted(load);

function explanation(skillName: string) {
  return (
    skillExplanations[skillName] ?? {
      title: skillName,
      summary: "已审核的旅行 Agent Skill。",
      boundary: "仅使用 manifest 声明的 Tool 与 MCP 白名单。",
    }
  );
}

function connectorExplanation(connectorId: string) {
  return (
    mcpExplanations[connectorId] ?? {
      title: connectorId,
      summary: "只读 MCP connector。",
      boundary: "固定服务端 endpoint，不允许用户填写任意 URL。",
    }
  );
}
</script>

<template>
  <section class="admin-page">
    <header class="admin-page__heading">
      <div>
        <p>Controlled capabilities</p>
        <h1>Agent Skills</h1>
      </div>
      <button class="admin-button" type="button" :disabled="loading" @click="load">
        <RefreshCw :size="15" :class="{ 'is-spinning': loading }" />
        刷新
      </button>
    </header>

    <p v-if="error" class="admin-error" role="alert">{{ error }}</p>

    <div class="metric-grid skill-metrics">
      <article class="metric">
        <ShieldCheck :size="18" />
        <span>启用 Skill</span>
        <strong>{{ activeCount }} / {{ skills.length }}</strong>
        <small>服务端实时启停状态</small>
      </article>
      <article class="metric">
        <Bot :size="18" />
        <span>允许 MCP Connector</span>
        <strong>{{ connectorCount }}</strong>
        <small>manifest 白名单交集</small>
      </article>
      <article class="metric">
        <Wrench :size="18" />
        <span>受控 Tool 引用</span>
        <strong>
          {{
            new Set(skills.flatMap((skill) => skill.allowed_tools)).size
          }}
        </strong>
        <small>仅允许已注册 Tool</small>
      </article>
    </div>

    <div v-if="loading" class="admin-state">正在加载</div>
    <div v-else-if="!skills.length" class="admin-state">暂无 Skill</div>
    <div v-else class="skill-grid">
      <article
        v-for="skill in skills"
        :key="skill.name"
        class="skill-card"
        :class="{ 'is-disabled': !skill.enabled }"
      >
        <header>
          <span class="skill-card__icon"><Bot :size="18" /></span>
          <span>
            <strong>{{ skill.name }}</strong>
            <small>{{ skill.description }}</small>
          </span>
          <span class="provider-card__status" :class="`is-${skill.enabled ? 'healthy' : 'disabled'}`">
            {{ skill.enabled ? "enabled" : "disabled" }}
          </span>
        </header>

        <div class="skill-card__explanation">
          <strong>{{ explanation(skill.name).title }}</strong>
          <span>{{ explanation(skill.name).summary }}</span>
          <small>{{ explanation(skill.name).boundary }}</small>
        </div>

        <div class="skill-card__meta">
          <span><small>版本</small><strong>{{ skill.version }}</strong></span>
          <span><small>Tool 调用</small><strong>{{ skill.max_tool_calls }}</strong></span>
          <span><small>超时</small><strong>{{ skill.timeout_seconds }}s</strong></span>
          <span><small>Token</small><strong>{{ skill.max_tokens }}</strong></span>
        </div>

        <div class="skill-card__permissions">
          <span>
            <small>Tools</small>
            <code v-for="tool in skill.allowed_tools" :key="tool">{{ tool }}</code>
            <em v-if="!skill.allowed_tools.length">none</em>
          </span>
          <span>
            <small>MCP</small>
            <code v-for="connector in skill.allowed_mcp_connectors" :key="connector">
              {{ connector }}
            </code>
            <em v-if="!skill.allowed_mcp_connectors.length">none</em>
          </span>
        </div>

        <footer>
          <span>
            <Clock3 :size="13" />
            <small>
              {{
                latestAudit(skill.name)
                  ? `${latestAudit(skill.name)?.action} · ${formatDateTime(latestAudit(skill.name)?.created_at ?? null)}`
                  : `更新 ${formatDateTime(skill.updated_at)}`
              }}
            </small>
          </span>
          <button
            class="feature-toggle"
            :class="{ 'is-enabled': skill.enabled }"
            type="button"
            role="switch"
            :aria-checked="skill.enabled"
            :disabled="toggling === skill.name"
            @click="toggle(skill)"
          >
            <span />
            {{
              toggling === skill.name
                ? "更新中"
                : skill.enabled
                  ? "停用 Skill"
                  : "启用 Skill"
            }}
          </button>
        </footer>
      </article>
    </div>

    <section class="admin-panel admin-panel--wide">
      <header>
        <strong>MCP Connector 说明</strong>
        <span>固定 endpoint、只读能力与独立回滚</span>
      </header>
      <div v-if="loading" class="admin-state">正在加载</div>
      <div v-else class="skill-mcp-grid">
        <article v-for="connector in connectors" :key="connector.connector_id">
          <span class="skill-card__icon"><Link2 :size="17" /></span>
          <span>
            <strong>{{ connectorExplanation(connector.connector_id).title }}</strong>
            <small>{{ connectorExplanation(connector.connector_id).summary }}</small>
          </span>
          <span class="provider-card__status" :class="`is-${connector.status}`">
            {{ connector.status }}
          </span>
          <span class="skill-mcp-grid__boundary">
            {{ connectorExplanation(connector.connector_id).boundary }}
          </span>
          <span class="skill-mcp-grid__metrics">
            {{ connector.latency_ms }} ms · {{ connector.requests_today }} /
            {{ connector.daily_quota }} calls
          </span>
        </article>
      </div>
    </section>
  </section>
</template>
