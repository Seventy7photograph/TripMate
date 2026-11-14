<!-- 文件说明：管理后台页面：Providers。 -->
<script setup lang="ts">
import {
  CloudSun,
  Cpu,
  Map as MapIcon,
  MapPinned,
  Power,
  RefreshCw,
  Server,
  ShieldAlert,
  Wrench,
} from "lucide-vue-next";
import { computed, onMounted, ref, type Component } from "vue";

import { adminApi } from "../api";
import { formatDateTime } from "../format";
import type {
  FeatureFlag,
  FeatureFlagKey,
  McpConnectorStatus,
  ProviderStatus,
  ToolHealth,
} from "../types";

const props = defineProps<{ token: string }>();
const loading = ref(true);
const toggling = ref<string | null>(null);
const togglingFeature = ref<FeatureFlagKey | null>(null);
const togglingConnector = ref<string | null>(null);
const error = ref("");
const providers = ref<ProviderStatus[]>([]);
const features = ref<FeatureFlag[]>([]);
const mcpConnectors = ref<McpConnectorStatus[]>([]);
const toolHealth = ref<ToolHealth[]>([]);

const featureMap = computed(
  () => new globalThis.Map(features.value.map((feature) => [feature.key, feature])),
);

const providerIcons: Partial<Record<FeatureFlagKey, Component>> = {
  llm_provider: Cpu,
  map_provider: MapIcon,
  weather_provider: CloudSun,
};
const connectorLabels: Record<string, string> = {
  amap: "AMap",
  weather: "Weather",
};
const connectorIcons: Record<string, Component> = {
  amap: MapPinned,
  weather: CloudSun,
};

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [providerData, featureData, connectorData, toolData] = await Promise.all([
      adminApi.providers(props.token),
      adminApi.features(props.token),
      adminApi.mcpConnectors(props.token),
      adminApi.toolHealth(props.token),
    ]);
    providers.value = providerData;
    features.value = featureData;
    mcpConnectors.value = connectorData;
    toolHealth.value = toolData;
  } catch {
    error.value = "Provider 状态加载失败。";
  } finally {
    loading.value = false;
  }
}

async function toggleConnector(connector: McpConnectorStatus): Promise<void> {
  if (togglingConnector.value) return;
  togglingConnector.value = connector.connector_id;
  error.value = "";
  try {
    const updated = await adminApi.toggleMcpConnector(
      props.token,
      connector.connector_id,
      !connector.enabled,
      `mcp connector ${connector.enabled ? "disabled" : "enabled"} from admin`,
    );
    mcpConnectors.value = mcpConnectors.value.map((item) =>
      item.connector_id === updated.connector_id ? updated : item,
    );
  } catch {
    error.value = "MCP Connector 状态更新失败。";
  } finally {
    togglingConnector.value = null;
  }
}

async function toggle(provider: ProviderStatus): Promise<void> {
  if (toggling.value) return;
  toggling.value = provider.key;
  error.value = "";
  try {
    const updated = await adminApi.toggleFeature(
      props.token,
      provider.key,
      !provider.enabled,
      `${provider.provider_type} provider ${provider.enabled ? "disabled" : "enabled"} from admin`,
    );
    features.value = features.value.map((feature) =>
      feature.key === updated.key ? updated : feature,
    );
    await load();
  } catch {
    error.value = "Provider 开关更新失败。";
  } finally {
    toggling.value = null;
  }
}

async function toggleFeature(feature: FeatureFlag): Promise<void> {
  if (togglingFeature.value) return;
  togglingFeature.value = feature.key;
  error.value = "";
  try {
    const updated = await adminApi.toggleFeature(
      props.token,
      feature.key,
      !feature.enabled,
      "provider feature toggle",
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

onMounted(load);
</script>

<template>
  <section class="admin-page">
    <header class="admin-page__heading">
      <div>
        <p>Provider controls</p>
        <h1>Provider</h1>
      </div>
      <button class="admin-button" type="button" :disabled="loading" @click="load">
        <RefreshCw :size="15" :class="{ 'is-spinning': loading }" />
        刷新
      </button>
    </header>

    <p v-if="error" class="admin-error" role="alert">{{ error }}</p>

    <div v-if="loading" class="admin-state">正在加载</div>
    <div v-else class="provider-grid">
      <article
        v-for="provider in providers"
        :key="provider.key"
        class="provider-card"
        :class="{ 'is-disabled': !provider.enabled }"
      >
        <header>
          <span class="provider-card__icon">
            <component :is="providerIcons[provider.key] ?? Server" :size="20" />
          </span>
          <span class="provider-card__status" :class="`is-${provider.status}`">
            {{ provider.status }}
          </span>
        </header>
        <div class="provider-card__title">
          <h2>{{ featureMap.get(provider.key)?.label ?? provider.key }}</h2>
          <small>{{ provider.provider_name }} · {{ provider.profile }}</small>
        </div>
        <dl>
          <div>
            <dt>配置</dt>
            <dd>{{ provider.configured ? "已配置" : "未配置" }}</dd>
          </div>
          <div>
            <dt>24h 调用</dt>
            <dd>{{ provider.invocations }}</dd>
          </div>
          <div>
            <dt>失败</dt>
            <dd>{{ provider.failed_invocations }}</dd>
          </div>
          <div>
            <dt>平均延迟</dt>
            <dd>{{ provider.average_latency_ms }} ms</dd>
          </div>
        </dl>
        <p class="provider-card__checked">
          最近检查 {{ formatDateTime(provider.last_checked_at) }}
        </p>
        <p
          v-if="provider.last_error_code"
          class="provider-card__error"
        >
          <ShieldAlert :size="14" />
          {{ provider.last_error_code }}
        </p>
        <button
          class="admin-button"
          :class="{ 'admin-button--danger': provider.enabled }"
          type="button"
          :disabled="toggling === provider.key"
          @click="toggle(provider)"
        >
          <Power :size="15" />
          {{
            toggling === provider.key
              ? "更新中"
              : provider.enabled
                ? "停用 Provider"
                : "启用 Provider"
          }}
        </button>
      </article>
    </div>

    <section class="admin-panel admin-panel--wide">
      <header>
        <strong>MCP Connectors</strong>
        <span>固定 endpoint、只读 Tool 与服务端配额</span>
      </header>
      <div v-if="loading" class="admin-state">正在加载</div>
      <div v-else class="mcp-connector-list">
        <article
          v-for="connector in mcpConnectors"
          :key="connector.connector_id"
          :class="{ 'is-disabled': !connector.enabled }"
        >
          <span class="provider-card__icon">
            <component
              :is="connectorIcons[connector.connector_id] ?? Server"
              :size="18"
            />
          </span>
          <span class="mcp-connector__identity">
            <strong>
              {{ connectorLabels[connector.connector_id] ?? connector.connector_id }}
            </strong>
            <small>{{ connector.connector_id }} · read-only</small>
          </span>
          <span
            class="provider-card__status"
            :class="`is-${connector.status}`"
          >
            {{ connector.status }}
          </span>
          <span class="mcp-connector__metrics">
            <span class="mcp-connector__metric">
              <small>延迟</small>
              <strong>{{ connector.latency_ms }} ms</strong>
            </span>
            <span class="mcp-connector__metric">
              <small>今日配额</small>
              <strong>{{ connector.requests_today }} / {{ connector.daily_quota }}</strong>
            </span>
            <span class="mcp-connector__metric">
              <small>分钟限流</small>
              <strong>{{ connector.window_calls }} / {{ connector.rate_limit_per_minute }}</strong>
            </span>
          </span>
          <span class="mcp-connector__health">
            <small>
              {{
                connector.last_error_code
                  ? connector.last_error_code
                  : `最近检查 ${formatDateTime(connector.checked_at)}`
              }}
            </small>
          </span>
          <button
            class="admin-button"
            :class="{ 'admin-button--danger': connector.enabled }"
            type="button"
            :disabled="togglingConnector === connector.connector_id"
            @click="toggleConnector(connector)"
          >
            <Power :size="15" />
            {{
              togglingConnector === connector.connector_id
                ? "更新中"
                : connector.enabled
                  ? "停用 Connector"
                  : "启用 Connector"
            }}
          </button>
        </article>
      </div>
    </section>

    <section class="admin-panel admin-panel--wide">
      <header>
        <strong>Local Tool Health</strong>
        <span>近 24 小时调用、失败与延迟</span>
      </header>
      <div v-if="loading" class="admin-state">正在加载</div>
      <div v-else-if="!toolHealth.length" class="admin-state">暂无 Tool 调用记录</div>
      <div v-else class="tool-health-list">
        <article v-for="tool in toolHealth" :key="`${tool.tool_name}-${tool.provider}`">
          <span class="provider-card__icon"><Wrench :size="17" /></span>
          <span class="mcp-connector__identity">
            <strong>{{ tool.tool_name }}</strong>
            <small>{{ tool.provider }}</small>
          </span>
          <span class="provider-card__status" :class="`is-${tool.status}`">
            {{ tool.status }}
          </span>
          <span class="mcp-connector__metric">
            <small>调用</small>
            <strong>{{ tool.invocations }}</strong>
          </span>
          <span class="mcp-connector__metric">
            <small>失败</small>
            <strong>{{ tool.failed_invocations }}</strong>
          </span>
          <span class="mcp-connector__metric">
            <small>平均延迟</small>
            <strong>{{ tool.average_latency_ms }} ms</strong>
          </span>
          <span class="mcp-connector__health">
            <small>
              {{
                tool.last_error_code
                  ? tool.last_error_code
                  : `最近调用 ${formatDateTime(tool.checked_at)}`
              }}
            </small>
          </span>
        </article>
      </div>
    </section>

    <section class="admin-panel admin-panel--wide">
      <header>
        <strong>功能开关</strong>
        <span>所有开关即时生效并写入审计</span>
      </header>
      <div class="feature-table">
        <article v-for="feature in features" :key="feature.key">
          <span>
            <strong>{{ feature.label }}</strong>
            <small>{{ feature.description }}</small>
          </span>
          <code>{{ feature.key }}</code>
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
  </section>
</template>
