<!-- 文件说明：前端页面：BudgetView。 -->
<script setup lang="ts">
import {
  AlertTriangle,
  ArrowLeft,
  Plus,
  RefreshCw,
  Wallet,
} from "lucide-vue-next";
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { budgetApi } from "../../features/budget/api";
import {
  formatMoney,
  parseBudgetAmount,
} from "../../features/budget/form";
import type {
  BudgetSummary,
  ExpenseCategory,
} from "../../features/budget/types";
import { tripApi } from "../../features/trips/api";
import type { Trip } from "../../features/trips/types";
import { ApiError, isVersionConflict } from "../../lib/http";
import { useAuthStore } from "../../stores/auth";

const auth = useAuthStore();
const route = useRoute();
const trip = ref<Trip | null>(null);
const budget = ref<BudgetSummary | null>(null);
const loading = ref(true);
const submitting = ref(false);
const error = ref("");
const message = ref("");
const form = reactive({
  category: "food" as ExpenseCategory,
  amount: "",
  currency: "CNY",
  expenseDate: new Date().toISOString().slice(0, 10),
  note: "",
});

const tripId = computed(() =>
  typeof route.params.tripId === "string" ? route.params.tripId : "",
);

const categoryLabels: Record<ExpenseCategory, string> = {
  transport: "交通",
  lodging: "住宿",
  food: "餐饮",
  tickets: "门票",
  shopping: "购物",
  activities: "活动",
  other: "其他",
};

const spendingRatio = computed(() => {
  if (!budget.value?.budget_minor) return 0;
  return Math.min(100, (budget.value.total_minor / budget.value.budget_minor) * 100);
});

function money(value: number | null): string {
  if (value === null || !budget.value) return "未设置";
  return formatMoney(value, budget.value.currency);
}

async function loadBudget(): Promise<void> {
  if (!auth.token || !tripId.value) return;
  loading.value = true;
  error.value = "";
  try {
    const [loadedTrip, loadedBudget] = await Promise.all([
      tripApi.get(auth.token, tripId.value),
      budgetApi.get(auth.token, tripId.value),
    ]);
    trip.value = loadedTrip;
    budget.value = loadedBudget;
    form.currency = loadedBudget.currency;
  } catch (cause) {
    error.value =
      cause instanceof ApiError && cause.status === 404
        ? "这份旅行不存在，或你没有访问权限。"
        : "预算加载失败，请稍后重试。";
  } finally {
    loading.value = false;
  }
}

async function addExpense(): Promise<void> {
  if (!auth.token || !trip.value || !budget.value) return;
  const amountMinor = parseBudgetAmount(form.amount);
  if (amountMinor === undefined || amountMinor === null) {
    error.value = "金额需为有效的非负数字，最多两位小数。";
    return;
  }

  submitting.value = true;
  error.value = "";
  message.value = "";
  try {
    const result = await budgetApi.createExpense(auth.token, tripId.value, {
      expected_version: trip.value.version,
      category: form.category,
      amount_minor: amountMinor,
      currency: form.currency,
      expense_date: form.expenseDate,
      note: form.note.trim() || null,
    });
    trip.value.version = result.version;
    form.amount = "";
    form.note = "";
    await loadBudget();
    message.value = "支出已记录";
  } catch (cause) {
    error.value = isVersionConflict(cause)
      ? "旅行已在其他会话更新，请刷新后重新记录支出。"
      : cause instanceof ApiError && cause.status === 422
        ? "支出币种必须与旅行币种一致，金额不能为负。"
        : "支出记录失败，请稍后重试。";
  } finally {
    submitting.value = false;
  }
}

onMounted(loadBudget);
</script>

<template>
  <main class="budget-page">
    <RouterLink class="back-link" :to="`/trips/${tripId}/itinerary`">
      <ArrowLeft :size="16" :stroke-width="1.8" />
      返回逐日行程
    </RouterLink>

    <div v-if="loading" class="itinerary-loading" aria-label="正在加载预算">
      <span />
      <span />
    </div>

    <div v-else-if="!trip || !budget" class="trip-state-panel trip-state-panel--error">
      <strong>无法打开预算</strong>
      <span>{{ error }}</span>
      <button class="quiet-action" type="button" @click="loadBudget">
        <RefreshCw :size="16" :stroke-width="1.8" />
        重新加载
      </button>
    </div>

    <template v-else>
      <header class="budget-heading">
        <div>
          <p>Trip budget</p>
          <h1>预算与支出</h1>
          <span>{{ trip.brief.destination }} · {{ trip.brief.party_size }} 人</span>
        </div>
        <span class="version-chip">版本 {{ trip.version }}</span>
      </header>

      <p v-if="message" class="form-success" role="status">{{ message }}</p>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>

      <section class="budget-overview" aria-label="预算总览">
        <div class="budget-overview__primary">
          <span>旅行预算</span>
          <strong>{{ money(budget.budget_minor) }}</strong>
          <small data-testid="budget-remaining">剩余 {{ money(budget.remaining_minor) }}</small>
        </div>
        <div>
          <span>预计</span>
          <strong data-testid="budget-estimated">{{ money(budget.estimated_minor) }}</strong>
          <small>来自逐日行程</small>
        </div>
        <div>
          <span>实际</span>
          <strong data-testid="budget-actual">{{ money(budget.total_minor) }}</strong>
          <small>人均 {{ money(budget.per_person_minor) }}</small>
        </div>
        <div class="budget-overview__bar">
          <span :style="{ transform: `scaleX(${spendingRatio / 100})` }" />
        </div>
      </section>

      <article
        v-for="issue in budget.issues"
        :key="issue.code + issue.message"
        class="budget-alert"
      >
        <AlertTriangle :size="18" :stroke-width="1.8" />
        <span>
          <strong>{{ issue.message }}</strong>
          <small>超出 {{ money(issue.overage_minor) }}</small>
        </span>
      </article>

      <div class="budget-layout">
        <section class="budget-categories" aria-labelledby="budget-category-title">
          <header>
            <h2 id="budget-category-title">分类明细</h2>
            <span>预计 / 实际</span>
          </header>
          <div
            v-for="category in budget.categories"
            :key="category.category"
            class="budget-category-row"
          >
            <strong>{{ categoryLabels[category.category] }}</strong>
            <span>{{ money(category.estimated_minor) }}</span>
            <span>{{ money(category.actual_minor) }}</span>
          </div>
        </section>

        <section class="expense-panel" aria-labelledby="expense-form-title">
          <header>
            <Wallet :size="17" :stroke-width="1.7" />
            <div>
              <h2 id="expense-form-title">记录支出</h2>
              <span>金额按整数分保存</span>
            </div>
          </header>

          <form @submit.prevent="addExpense">
            <div class="expense-form-grid">
              <label class="field">
                <span>支出类别</span>
                <span class="field__control">
                  <select v-model="form.category">
                    <option
                      v-for="(label, category) in categoryLabels"
                      :key="category"
                      :value="category"
                    >
                      {{ label }}
                    </option>
                  </select>
                </span>
              </label>

              <label class="field">
                <span>金额 ({{ form.currency }})</span>
                <span class="field__control">
                  <input v-model="form.amount" inputmode="decimal" required placeholder="0.00" />
                </span>
              </label>

              <label class="field">
                <span>币种</span>
                <span class="field__control">
                  <input v-model.trim="form.currency" maxlength="3" required />
                </span>
              </label>

              <label class="field">
                <span>支出日期</span>
                <span class="field__control">
                  <input v-model="form.expenseDate" type="date" required />
                </span>
              </label>

              <label class="field field--wide">
                <span>备注</span>
                <span class="field__control">
                  <input v-model="form.note" maxlength="500" placeholder="可选" />
                </span>
              </label>
            </div>

            <button class="primary-button" type="submit" :disabled="submitting">
              <Plus :size="16" :stroke-width="1.8" />
              {{ submitting ? "记录中" : "记录支出" }}
            </button>
          </form>
        </section>
      </div>

      <section class="expense-list" aria-labelledby="expense-list-title">
        <header>
          <h2 id="expense-list-title">支出记录</h2>
          <span>{{ budget.expenses.length }} 条</span>
        </header>
        <div v-if="budget.expenses.length" class="expense-list__rows">
          <article v-for="expense in budget.expenses" :key="expense.id">
            <span>
              <strong>{{ categoryLabels[expense.category] }}</strong>
              <small>{{ expense.expense_date }} · {{ expense.note || "无备注" }}</small>
            </span>
            <strong>{{ formatMoney(expense.amount_minor, expense.currency) }}</strong>
          </article>
        </div>
        <p v-else class="expense-list__empty">还没有实际支出。</p>
      </section>
    </template>
  </main>
</template>
