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
import { computed, onMounted, onUnmounted, ref } from "vue";

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
const checkingConnector = ref<string | null>(null);
const lastUpdated = ref<Date | null>(null);
const selectedVersions = ref<Record<string, string>>({});

const activeCount = computed(
  () => skills.value.filter((skill) => skill.enabled).length,
);
const connectorCount = computed(
  () => connectors.value.filter((connector) => connector.configured).length,
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

async function load(silent = false): Promise<void> {
  if (!silent) loading.value = true;
  error.value = "";
  try {
    const [skillData, auditData, connectorData] = await Promise.all([
      adminApi.skills(props.token),
      adminApi.auditLogs(props.token, 100),
      adminApi.mcpConnectors(props.token),
    ]);
    skills.value = skillData;
    for (const skill of skillData) {
      selectedVersions.value[skill.name] =
        selectedVersions.value[skill.name] || skill.version;
    }
    audits.value = auditData.items;
    connectors.value = connectorData;
    lastUpdated.value = new Date();
  } catch {
    error.value = "Skill 实时状态加载失败，当前展示最近一次成功数据。";
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
      selectedVersions.value[skill.name] ?? skill.version,
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

async function checkConnector(
  connector: McpConnectorStatus,
): Promise<void> {
  if (checkingConnector.value) return;
  checkingConnector.value = connector.connector_id;
  error.value = "";
  try {
    const updated = await adminApi.checkMcpConnector(
      props.token,
      connector.connector_id,
    );
    connectors.value = connectors.value.map((item) =>
      item.connector_id === updated.connector_id ? updated : item,
    );
    lastUpdated.value = new Date();
  } catch {
    error.value = "MCP Connector 检测失败。";
  } finally {
    checkingConnector.value = null;
  }
}

let refreshTimer: number | null = null;

function refreshWhenVisible(): void {
  if (document.visibilityState === "visible") void load(true);
}

onMounted(() => {
  void load();
  refreshTimer = window.setInterval(() => {
    if (document.visibilityState === "visible") void load(true);
  }, 5_000);
  document.addEventListener("visibilitychange", refreshWhenVisible);
});

onUnmounted(() => {
  if (refreshTimer !== null) window.clearInterval(refreshTimer);
  document.removeEventListener("visibilitychange", refreshWhenVisible);
});
</script>

<template>
  <section class="admin-page">
    <header class="admin-page__heading">
      <div>
        <p>Controlled capabilities</p>
        <h1>Agent Skills</h1>
        <small v-if="lastUpdated">
          最近同步 {{ lastUpdated.toLocaleTimeString("zh-CN") }}
        </small>
      </div>
      <button
        class="admin-button"
        type="button"
        :disabled="loading"
        @click="load()"
      >
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
            <strong>{{ skill.display_name }}</strong>
            <code>{{ skill.name }}</code>
            <small>{{ skill.description }}</small>
          </span>
          <span
            class="provider-card__status"
            :class="`is-${skill.runtime_status === 'ready' ? 'healthy' : skill.runtime_status}`"
          >
            {{ skill.runtime_status }}
          </span>
        </header>

        <div class="skill-card__explanation">
          <strong>{{ skill.purpose }}</strong>
          <span>{{ skill.boundary }}</span>
          <small>
            {{ skill.execution_mode }} · {{ skill.surfaces.join(" / ") }}
          </small>
        </div>

        <div class="skill-card__meta">
          <span>
            <small>当前版本</small>
            <select
              v-model="selectedVersions[skill.name]"
              :aria-label="`${skill.display_name} 版本`"
            >
              <option
                v-for="version in skill.available_versions"
                :key="version"
                :value="version"
              >
                {{ version }}
              </option>
            </select>
          </span>
          <span>
            <small>可选版本</small>
            <strong>{{ skill.available_versions.join(" / ") }}</strong>
          </span>
          <span><small>Tool 调用</small><strong>{{ skill.max_tool_calls }}</strong></span>
          <span><small>超时</small><strong>{{ skill.timeout_seconds }}s</strong></span>
          <span><small>Token</small><strong>{{ skill.max_tokens }}</strong></span>
          <span><small>24h 执行</small><strong>{{ skill.recent_runs }}</strong></span>
          <span>
            <small>成功率</small>
            <strong>
              {{
                skill.success_rate === null
                  ? "—"
                  : `${Math.round(skill.success_rate * 100)}%`
              }}
            </strong>
          </span>
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
            <strong>{{ connector.display_name }}</strong>
            <small>{{ connector.purpose }}</small>
          </span>
          <span class="provider-card__status" :class="`is-${connector.status}`">
            {{ connector.status }}
          </span>
          <span class="skill-mcp-grid__boundary">
            {{ connector.boundary }}
          </span>
          <span class="skill-mcp-grid__metrics">
            {{ connector.latency_ms }} ms · {{ connector.requests_today }} /
            {{ connector.daily_quota }} calls
          </span>
          <button
            class="admin-button"
            type="button"
            :disabled="checkingConnector === connector.connector_id"
            @click="checkConnector(connector)"
          >
            <RefreshCw
              :size="14"
              :class="{ 'is-spinning': checkingConnector === connector.connector_id }"
            />
            检测
          </button>
        </article>
      </div>
    </section>
  </section>
</template>
