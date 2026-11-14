<!-- 文件说明：管理后台页面：AgentRuns。 -->
<script setup lang="ts">
import { Filter, RefreshCw } from "lucide-vue-next";
import { onMounted, reactive, ref } from "vue";

import { adminApi } from "../api";
import { formatCurrency, formatDateTime, formatNumber } from "../format";
import type { AgentRun } from "../types";

const props = defineProps<{ token: string }>();
const loading = ref(true);
const error = ref("");
const runs = ref<AgentRun[]>([]);
const total = ref(0);
const filters = reactive({
  status: "",
  purpose: "",
  provider: "",
});

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const response = await adminApi.agentRuns(props.token, {
      ...filters,
      limit: 100,
    });
    runs.value = response.items;
    total.value = response.total;
  } catch {
    error.value = "Agent Runs 加载失败。";
  } finally {
    loading.value = false;
  }
}

function routeConfidence(run: AgentRun): number | null {
  const confidence = run.skill_route?.confidence;
  return typeof confidence === "number" ? confidence : null;
}

function fallbackReason(run: AgentRun): string | null {
  const reason = run.skill_route?.fallback_reason;
  return typeof reason === "string" ? reason : null;
}

onMounted(load);
</script>

<template>
  <section class="admin-page">
    <header class="admin-page__heading">
      <div>
        <p>Execution audit</p>
        <h1>Agent Runs</h1>
      </div>
      <span class="admin-count">{{ total }} 条记录</span>
    </header>

    <form class="filter-bar" @submit.prevent="load">
      <Filter :size="15" />
      <select v-model="filters.status">
        <option value="">全部状态</option>
        <option value="queued">queued</option>
        <option value="running">running</option>
        <option value="completed">completed</option>
        <option value="partial">partial</option>
        <option value="failed">failed</option>
      </select>
      <select v-model="filters.purpose">
        <option value="">全部用途</option>
        <option value="planning">planning</option>
        <option value="brief_parse">brief_parse</option>
        <option value="travel_chat">travel_chat</option>
      </select>
      <input v-model.trim="filters.provider" placeholder="Provider" />
      <button class="admin-button" type="submit" :disabled="loading">
        <RefreshCw :size="15" :class="{ 'is-spinning': loading }" />
        筛选
      </button>
    </form>

    <p v-if="error" class="admin-error" role="alert">{{ error }}</p>

    <div class="table-shell">
      <table class="admin-table">
        <thead>
          <tr>
            <th>状态</th>
            <th>用途 / 模型</th>
            <th>Provider</th>
            <th>Skill / Router</th>
            <th>Prompt</th>
            <th>Tokens</th>
            <th>成本</th>
            <th>工具 / 循环</th>
            <th>延迟</th>
            <th>时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="10" class="admin-state">正在加载</td>
          </tr>
          <tr v-else-if="!runs.length">
            <td colspan="10" class="admin-state">暂无运行记录</td>
          </tr>
          <template v-else>
            <tr v-for="run in runs" :key="run.id">
              <td>
                <span class="run-status" :class="`run-status--${run.status}`">
                  {{ run.status }}
                </span>
              </td>
              <td>
                <strong>{{ run.purpose }}</strong>
                <small>{{ run.model_name }}</small>
              </td>
              <td>{{ run.provider }}</td>
              <td>
                <div class="run-skills">
                  <code
                    v-for="skill in run.skills_used"
                    :key="`${skill.name}-${skill.version}`"
                  >
                    {{ skill.name }}@{{ skill.version }}
                  </code>
                  <em v-if="!run.skills_used.length">no skill</em>
                  <small v-if="routeConfidence(run) !== null">
                    router {{ (routeConfidence(run)! * 100).toFixed(1) }}%
                  </small>
                  <small v-if="fallbackReason(run)" class="run-skills__fallback">
                    {{ fallbackReason(run) }}
                  </small>
                </div>
              </td>
              <td>
                <small v-if="!run.prompt_versions.length">-</small>
                <small
                  v-for="prompt in run.prompt_versions"
                  v-else
                  :key="`${prompt.agent}-${prompt.prompt_id}-${prompt.version}`"
                >
                  {{ prompt.prompt_id }}@{{ prompt.version }}
                </small>
              </td>
              <td>{{ formatNumber(run.input_tokens + run.output_tokens) }}</td>
              <td>{{ formatCurrency(run.estimated_cost_minor) }}</td>
              <td>{{ run.tool_call_count }} / {{ run.loop_count }}</td>
              <td>{{ run.latency_ms }} ms</td>
              <td>{{ formatDateTime(run.created_at) }}</td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </section>
</template>
