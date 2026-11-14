<!-- 文件说明：管理后台页面：Costs。 -->
<script setup lang="ts">
import { Coins, Gauge, RefreshCw, Timer, TriangleAlert } from "lucide-vue-next";
import { computed, onMounted, ref } from "vue";

import { adminApi } from "../api";
import { formatCurrency, formatNumber } from "../format";
import type { CostSummary } from "../types";

const props = defineProps<{ token: string }>();
const loading = ref(true);
const error = ref("");
const days = ref(30);
const summary = ref<CostSummary | null>(null);

const maxDailyCost = computed(
  () => Math.max(1, ...(summary.value?.daily.map((item) => item.cost_minor) ?? [0])),
);

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    summary.value = await adminApi.costs(props.token, days.value);
  } catch {
    error.value = "成本数据加载失败。";
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="admin-page">
    <header class="admin-page__heading">
      <div>
        <p>Cost governance</p>
        <h1>成本</h1>
      </div>
      <div class="cost-controls">
        <select v-model.number="days" @change="load">
          <option :value="7">近 7 天</option>
          <option :value="30">近 30 天</option>
          <option :value="90">近 90 天</option>
        </select>
        <button class="admin-button" type="button" :disabled="loading" @click="load">
          <RefreshCw :size="15" :class="{ 'is-spinning': loading }" />
          刷新
        </button>
      </div>
    </header>

    <p v-if="error" class="admin-error" role="alert">{{ error }}</p>
    <div v-if="loading" class="admin-state">正在加载</div>

    <template v-else-if="summary">
      <div class="metric-grid">
        <article class="metric">
          <Coins :size="18" />
          <span>已记录成本</span>
          <strong>{{ formatCurrency(summary.total_cost_minor) }}</strong>
          <small>{{ formatNumber(summary.total_runs) }} 次运行</small>
        </article>
        <article class="metric">
          <Gauge :size="18" />
          <span>Token 总量</span>
          <strong>
            {{ formatNumber(summary.total_input_tokens + summary.total_output_tokens) }}
          </strong>
          <small>
            输入 {{ formatNumber(summary.total_input_tokens) }} / 输出
            {{ formatNumber(summary.total_output_tokens) }}
          </small>
        </article>
        <article class="metric">
          <TriangleAlert :size="18" />
          <span>失败运行</span>
          <strong>{{ formatNumber(summary.failed_runs) }}</strong>
          <small>
            {{
              summary.total_runs
                ? ((summary.failed_runs / summary.total_runs) * 100).toFixed(1)
                : "0.0"
            }}% 失败率
          </small>
        </article>
        <article class="metric">
          <Timer :size="18" />
          <span>平均延迟</span>
          <strong>{{ formatNumber(summary.average_latency_ms) }} ms</strong>
          <small>全部 Agent Runs</small>
        </article>
      </div>

      <div class="admin-split">
        <section class="admin-panel">
          <header>
            <strong>按 Provider</strong>
            <span>成本与失败分布</span>
          </header>
          <div class="cost-breakdown">
            <article v-for="item in summary.by_provider" :key="item.key">
              <span>
                <strong>{{ item.key }}</strong>
                <small>{{ item.runs }} 次 · {{ item.failed_runs }} 次失败</small>
              </span>
              <strong>{{ formatCurrency(item.cost_minor) }}</strong>
            </article>
            <div v-if="!summary.by_provider.length" class="admin-state">
              暂无成本数据
            </div>
          </div>
        </section>

        <section class="admin-panel">
          <header>
            <strong>按模型</strong>
            <span>模型调用成本</span>
          </header>
          <div class="cost-breakdown">
            <article v-for="item in summary.by_model" :key="item.key">
              <span>
                <strong>{{ item.key }}</strong>
                <small>{{ item.runs }} 次运行</small>
              </span>
              <strong>{{ formatCurrency(item.cost_minor) }}</strong>
            </article>
            <div v-if="!summary.by_model.length" class="admin-state">
              暂无成本数据
            </div>
          </div>
        </section>
      </div>

      <section class="admin-panel admin-panel--wide">
        <header>
          <strong>按 Skill 均摊</strong>
          <span>同一运行内按 Skill 数均摊成本与 Token</span>
        </header>
        <div class="cost-breakdown skill-cost-breakdown">
          <article v-for="item in summary.by_skill" :key="item.key">
            <span>
              <strong>{{ item.key }}</strong>
              <small>
                {{ item.runs }} 次 · {{ item.failed_runs }} 次失败 ·
                {{ formatNumber(item.input_tokens + item.output_tokens) }} tokens
              </small>
            </span>
            <strong>{{ formatCurrency(item.cost_minor) }}</strong>
          </article>
          <div v-if="!summary.by_skill.length" class="admin-state">
            暂无 Skill 成本数据
          </div>
        </div>
      </section>

      <section class="admin-panel admin-panel--wide">
        <header>
          <strong>每日成本</strong>
          <span>UTC 日期</span>
        </header>
        <div v-if="summary.daily.length" class="daily-costs">
          <article v-for="item in summary.daily" :key="item.date">
            <time :datetime="item.date">{{ item.date }}</time>
            <span>
              <i :style="{ width: `${(item.cost_minor / maxDailyCost) * 100}%` }" />
            </span>
            <strong>{{ formatCurrency(item.cost_minor) }}</strong>
            <small>{{ item.runs }} runs</small>
          </article>
        </div>
        <div v-else class="admin-state">暂无每日成本记录</div>
      </section>

      <section class="limit-strip">
        <div>
          <span>单次运行</span>
          <strong>{{ formatCurrency(summary.limits.run_cost_minor) }}</strong>
        </div>
        <div>
          <span>单用户 / 日</span>
          <strong>{{ formatCurrency(summary.limits.user_daily_cost_minor) }}</strong>
        </div>
        <div>
          <span>单 IP / 日</span>
          <strong>{{ formatCurrency(summary.limits.ip_daily_cost_minor) }}</strong>
        </div>
        <div>
          <span>单 Provider / 日</span>
          <strong>{{ formatCurrency(summary.limits.provider_daily_cost_minor) }}</strong>
        </div>
        <div>
          <span>预警线</span>
          <strong>{{ Math.round(summary.limits.warning_ratio * 100) }}%</strong>
        </div>
      </section>
    </template>
  </section>
</template>
