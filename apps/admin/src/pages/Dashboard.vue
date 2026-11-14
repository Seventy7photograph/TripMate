<!-- 文件说明：管理后台页面：Dashboard。 -->
<script setup lang="ts">
import { Activity, Coins, RefreshCw, Server, TriangleAlert } from "lucide-vue-next";
import { computed, onMounted, ref } from "vue";

import { adminApi } from "../api";
import { formatCurrency, formatDateTime, formatNumber } from "../format";
import type {
  AgentRun,
  AuditLog,
  CostSummary,
  FeatureFlag,
  FeatureFlagKey,
  ProviderStatus,
} from "../types";

const props = defineProps<{ token: string }>();
const loading = ref(true);
const error = ref("");
const costs = ref<CostSummary | null>(null);
const providers = ref<ProviderStatus[]>([]);
const features = ref<FeatureFlag[]>([]);
const runs = ref<AgentRun[]>([]);
const audits = ref<AuditLog[]>([]);
const togglingFeature = ref<FeatureFlagKey | null>(null);

const healthyProviders = computed(
  () =>
    providers.value.filter((item) =>
      ["healthy", "configured"].includes(item.status)
    ).length,
);
const activeFeatures = computed(
  () => features.value.filter((item) => item.enabled).length,
);

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [costData, providerData, featureData, runData, auditData] =
      await Promise.all([
        adminApi.costs(props.token, 7),
        adminApi.providers(props.token),
        adminApi.features(props.token),
        adminApi.agentRuns(props.token, { limit: 8 }),
        adminApi.auditLogs(props.token, 8),
      ]);
    costs.value = costData;
    providers.value = providerData;
    features.value = featureData;
    runs.value = runData.items;
    audits.value = auditData.items;
  } catch {
    error.value = "运营数据加载失败。";
  } finally {
    loading.value = false;
  }
}

onMounted(load);

async function toggleFeature(feature: FeatureFlag): Promise<void> {
  if (togglingFeature.value) return;
  togglingFeature.value = feature.key;
  error.value = "";
  try {
    const updated = await adminApi.toggleFeature(
      props.token,
      feature.key,
      !feature.enabled,
      "dashboard feature toggle",
    );
    features.value = features.value.map((item) =>
      item.key === updated.key ? updated : item,
    );
  } catch {
    error.value = "功能状态更新失败。";
  } finally {
    togglingFeature.value = null;
  }
}
</script>

<template>
  <section class="admin-page">
    <header class="admin-page__heading">
      <div>
        <p>Operations overview</p>
        <h1>运行概览</h1>
      </div>
      <button class="admin-button" type="button" :disabled="loading" @click="load">
        <RefreshCw :size="15" :class="{ 'is-spinning': loading }" />
        刷新
      </button>
    </header>

    <p v-if="error" class="admin-error" role="alert">{{ error }}</p>

    <div class="metric-grid">
      <article class="metric">
        <Activity :size="18" />
        <span>近 7 天 Agent Runs</span>
        <strong>{{ formatNumber(costs?.total_runs ?? 0) }}</strong>
        <small>{{ costs?.failed_runs ?? 0 }} 次失败</small>
      </article>
      <article class="metric">
        <Coins :size="18" />
        <span>近 7 天已记录模型成本</span>
        <strong>{{ formatCurrency(costs?.total_cost_minor ?? 0) }}</strong>
        <small>P50 延迟 {{ costs?.average_latency_ms ?? 0 }} ms</small>
      </article>
      <article class="metric">
        <Server :size="18" />
        <span>可用 Provider</span>
        <strong>{{ healthyProviders }} / {{ providers.length }}</strong>
        <small>配置与最近健康状态</small>
      </article>
      <article class="metric">
        <TriangleAlert :size="18" />
        <span>启用功能开关</span>
        <strong>{{ activeFeatures }} / {{ features.length }}</strong>
        <small>关闭后立即阻断新请求</small>
      </article>
    </div>

    <div class="admin-split">
      <section class="admin-panel">
        <header>
          <strong>最近 Agent Runs</strong>
          <span>按创建时间倒序</span>
        </header>
        <div v-if="loading" class="admin-state">正在加载</div>
        <div v-else-if="!runs.length" class="admin-state">暂无运行记录</div>
        <div v-else class="run-list">
          <article v-for="run in runs" :key="run.id">
            <span class="run-status" :class="`run-status--${run.status}`">
              {{ run.status }}
            </span>
            <span>
              <strong>{{ run.purpose }}</strong>
              <small>{{ run.provider }} · {{ run.model_name }}</small>
            </span>
            <span class="run-list__metric">
              {{ formatNumber(run.input_tokens + run.output_tokens) }} tokens
            </span>
            <time :datetime="run.created_at">{{ formatDateTime(run.created_at) }}</time>
          </article>
        </div>
      </section>

      <section class="admin-panel">
        <header>
          <strong>功能状态</strong>
          <span>服务端实时开关</span>
        </header>
        <div v-if="loading" class="admin-state">正在加载</div>
        <div v-else class="feature-list">
          <article v-for="feature in features" :key="feature.key">
            <span>
              <strong>{{ feature.label }}</strong>
              <small>{{ feature.key }}</small>
            </span>
            <button
              class="feature-toggle"
              :class="{ 'is-enabled': feature.enabled }"
              type="button"
              role="switch"
              :aria-checked="feature.enabled"
              :aria-label="`${feature.enabled ? '停用' : '启用'}${feature.label}`"
              :disabled="togglingFeature === feature.key"
              @click="toggleFeature(feature)"
            >
              <span />
              {{ togglingFeature === feature.key ? "更新中" : feature.enabled ? "启用" : "停用" }}
            </button>
          </article>
        </div>
      </section>
    </div>

    <section class="admin-panel admin-panel--wide">
      <header>
        <strong>最近管理操作</strong>
        <span>功能开关与审计记录</span>
      </header>
      <div v-if="loading" class="admin-state">正在加载</div>
      <div v-else-if="!audits.length" class="admin-state">暂无审计记录</div>
      <div v-else class="audit-list">
        <article v-for="audit in audits" :key="audit.id">
          <span>{{ audit.action }}</span>
          <strong>{{ audit.target_id }}</strong>
          <small>{{ audit.actor_id.slice(0, 8) }}</small>
          <time :datetime="audit.created_at">{{ formatDateTime(audit.created_at) }}</time>
        </article>
      </div>
    </section>
  </section>
</template>
