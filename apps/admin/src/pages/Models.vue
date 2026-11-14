<!-- 文件说明：管理后台页面：Models。 -->
<script setup lang="ts">
import { Bot, KeyRound, RefreshCw, Save, ShieldCheck } from "lucide-vue-next";
import { onMounted, reactive, ref } from "vue";

import { adminApi } from "../api";
import { formatDateTime } from "../format";
import type { ModelConfig, ModelConfigUpdate, ModelStage } from "../types";

interface ModelDraft {
  base_url: string;
  model_name: string;
  api_key: string;
  clear_api_key: boolean;
  timeout_seconds: number;
  max_retries: number;
}

const props = defineProps<{ token: string }>();
const loading = ref(true);
const saving = ref<ModelStage | null>(null);
const error = ref("");
const message = ref("");
const configs = ref<ModelConfig[]>([]);
const drafts = reactive<Record<ModelStage, ModelDraft>>({
  brief_parse: emptyDraft(),
  research_planner: emptyDraft(),
  itinerary_composer: emptyDraft(),
  travel_chat: emptyDraft(),
});

function emptyDraft(): ModelDraft {
  return {
    base_url: "https://api.deepseek.com",
    model_name: "",
    api_key: "",
    clear_api_key: false,
    timeout_seconds: 30,
    max_retries: 2,
  };
}

function applyConfig(config: ModelConfig): void {
  const draft = drafts[config.stage];
  draft.base_url = config.base_url;
  draft.model_name = config.model_name;
  draft.api_key = "";
  draft.clear_api_key = false;
  draft.timeout_seconds = config.timeout_seconds;
  draft.max_retries = config.max_retries;
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    configs.value = await adminApi.modelConfigs(props.token);
    configs.value.forEach(applyConfig);
  } catch {
    error.value = "模型配置加载失败。";
  } finally {
    loading.value = false;
  }
}

async function save(stage: ModelStage): Promise<void> {
  const draft = drafts[stage];
  const config = configs.value.find((item) => item.stage === stage);
  error.value = "";
  message.value = "";
  if (!draft.api_key.trim() && !config?.api_key_configured) {
    error.value = "Live 模式需要填写 API Key，或保留已配置密钥。";
    return;
  }
  const payload: ModelConfigUpdate = {
    provider_profile: "live",
    base_url: draft.base_url,
    model_name: draft.model_name,
    clear_api_key: draft.clear_api_key,
    timeout_seconds: draft.timeout_seconds,
    max_retries: draft.max_retries,
  };
  if (draft.api_key.trim()) payload.api_key = draft.api_key.trim();

  saving.value = stage;
  try {
    const updated = await adminApi.updateModelConfig(
      props.token,
      stage,
      payload,
    );
    configs.value = configs.value.map((item) =>
      item.stage === updated.stage ? updated : item,
    );
    applyConfig(updated);
    message.value = `${updated.label}配置已保存`;
  } catch {
    error.value = "模型配置保存失败，请检查 URL、模型名和密钥。";
  } finally {
    saving.value = null;
  }
}

onMounted(load);
</script>

<template>
  <section class="admin-page">
    <header class="admin-page__heading">
      <div>
        <p>Model routing</p>
        <h1>模型配置</h1>
      </div>
      <button class="admin-button" type="button" :disabled="loading" @click="load">
        <RefreshCw :size="15" :class="{ 'is-spinning': loading }" />
        刷新
      </button>
    </header>

    <p v-if="message" class="admin-notice" role="status">{{ message }}</p>
    <p v-if="error" class="admin-error" role="alert">{{ error }}</p>
    <div v-if="loading" class="admin-state">正在加载</div>

    <div v-else class="model-grid">
      <article v-for="config in configs" :key="config.stage" class="model-card">
        <header>
          <span class="model-card__icon"><Bot :size="19" /></span>
          <span>
            <strong>{{ config.label }}</strong>
            <small>{{ config.stage }}</small>
          </span>
          <el-tag
            :type="config.source === 'database' ? 'success' : 'info'"
            effect="plain"
            disable-transitions
          >
            {{ config.source === "database" ? "在线配置" : "环境默认" }}
          </el-tag>
          <el-tag
            :type="config.provider_profile === 'live' ? 'success' : 'warning'"
            effect="dark"
            disable-transitions
          >
            {{ config.provider_profile === "live" ? "Live" : "需迁移 Live" }}
          </el-tag>
        </header>

        <label>
          <span>Base URL</span>
          <input
            v-model.trim="drafts[config.stage].base_url"
            type="url"
            placeholder="https://api.deepseek.com"
          />
        </label>
        <label>
          <span>模型名称</span>
          <input
            v-model.trim="drafts[config.stage].model_name"
            placeholder="deepseek-flash"
          />
        </label>
        <label>
          <span>
            API Key
            <small v-if="config.api_key_configured">
              <ShieldCheck :size="12" />
              已配置，留空不修改
            </small>
          </span>
          <span class="model-key-input">
            <KeyRound :size="15" />
            <input
              v-model="drafts[config.stage].api_key"
              type="password"
              autocomplete="new-password"
              :placeholder="
                config.api_key_configured ? '保持现有密钥' : 'write-only API key'
              "
            />
          </span>
        </label>

        <div class="model-row">
          <label>
            <span>超时秒数</span>
            <input
              v-model.number="drafts[config.stage].timeout_seconds"
              type="number"
              min="1"
              max="120"
            />
          </label>
          <label>
            <span>最大重试</span>
            <input
              v-model.number="drafts[config.stage].max_retries"
              type="number"
              min="0"
              max="5"
            />
          </label>
        </div>

        <label class="model-clear-key">
          <input
            v-model="drafts[config.stage].clear_api_key"
            type="checkbox"
          />
          <span>清除已保存密钥</span>
        </label>

        <footer>
          <span>更新 {{ formatDateTime(config.updated_at) }}</span>
          <button
            class="admin-button admin-button--primary"
            type="button"
            :disabled="saving === config.stage"
            @click="save(config.stage)"
          >
            <Save :size="15" />
            {{ saving === config.stage ? "保存中" : "保存配置" }}
          </button>
        </footer>
      </article>
    </div>
  </section>
</template>
