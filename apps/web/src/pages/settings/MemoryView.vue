<!-- 文件说明：前端页面：MemoryView。 -->
<script setup lang="ts">
import {
  Download,
  Pencil,
  Plus,
  Power,
  Save,
  Trash2,
  X,
} from "lucide-vue-next";
import { onMounted, reactive, ref } from "vue";

import { memoryApi } from "../../features/memory/api";
import type {
  MemoryCategory,
  TravelMemory,
} from "../../features/memory/types";
import { useAuthStore } from "../../stores/auth";

const auth = useAuthStore();
const memories = ref<TravelMemory[]>([]);
const loading = ref(true);
const submitting = ref(false);
const error = ref("");
const message = ref("");
const editingId = ref<string | null>(null);
const editingContent = ref("");
const editingCategory = ref<MemoryCategory>("preference");
const pendingDelete = ref<TravelMemory | null>(null);
const clearConfirmOpen = ref(false);
let loadGeneration = 0;

const form = reactive<{
  category: MemoryCategory;
  content: string;
  consent: boolean;
}>({
  category: "preference",
  content: "",
  consent: false,
});

const categoryLabels: Record<MemoryCategory, string> = {
  preference: "偏好",
  food: "饮食",
  mobility: "行动",
  lodging: "住宿",
  budget: "预算",
  avoid: "避开",
  other: "其他",
};

async function loadMemories(): Promise<void> {
  if (!auth.token) return;
  const generation = ++loadGeneration;
  loading.value = true;
  error.value = "";
  try {
    const items = await memoryApi.list(auth.token);
    if (generation === loadGeneration) memories.value = items;
  } catch {
    if (generation === loadGeneration) {
      error.value = "旅行记忆加载失败。";
    }
  } finally {
    if (generation === loadGeneration) loading.value = false;
  }
}

async function createMemory(): Promise<void> {
  if (!auth.token || submitting.value) return;
  error.value = "";
  message.value = "";
  if (!form.consent) {
    error.value = "请先允许保存这条记忆。";
    return;
  }
  submitting.value = true;
  try {
    const created = await memoryApi.create(auth.token, {
      category: form.category,
      content: form.content,
      consent: true,
    });
    loadGeneration += 1;
    loading.value = false;
    memories.value = [created, ...memories.value];
    form.content = "";
    form.consent = false;
    message.value = "已保存";
  } catch {
    error.value = "保存失败，请稍后重试。";
  } finally {
    submitting.value = false;
  }
}

function startEdit(memory: TravelMemory): void {
  editingId.value = memory.id;
  editingContent.value = memory.content;
  editingCategory.value = memory.category;
}

async function saveEdit(memory: TravelMemory): Promise<void> {
  if (!auth.token || submitting.value) return;
  submitting.value = true;
  error.value = "";
  message.value = "";
  try {
    const updated = await memoryApi.update(auth.token, memory.id, {
      category: editingCategory.value,
      content: editingContent.value,
    });
    memories.value = memories.value.map((item) =>
      item.id === updated.id ? updated : item,
    );
    editingId.value = null;
    message.value = "已更新";
  } catch {
    error.value = "更新失败，请稍后重试。";
  } finally {
    submitting.value = false;
  }
}

async function toggleMemory(memory: TravelMemory): Promise<void> {
  if (!auth.token) return;
  error.value = "";
  try {
    const updated = await memoryApi.update(auth.token, memory.id, {
      enabled: !memory.enabled,
    });
    memories.value = memories.value.map((item) =>
      item.id === updated.id ? updated : item,
    );
  } catch {
    error.value = "状态更新失败。";
  }
}

async function deleteMemory(): Promise<void> {
  if (!auth.token || !pendingDelete.value) return;
  const target = pendingDelete.value;
  submitting.value = true;
  error.value = "";
  try {
    await memoryApi.remove(auth.token, target.id);
    memories.value = memories.value.filter((item) => item.id !== target.id);
    pendingDelete.value = null;
    message.value = "已删除";
  } catch {
    error.value = "删除失败，请稍后重试。";
  } finally {
    submitting.value = false;
  }
}

async function clearMemories(): Promise<void> {
  if (!auth.token) return;
  submitting.value = true;
  error.value = "";
  try {
    await memoryApi.clear(auth.token);
    memories.value = [];
    clearConfirmOpen.value = false;
    message.value = "已全部清除";
  } catch {
    error.value = "清除失败，请稍后重试。";
  } finally {
    submitting.value = false;
  }
}

function exportMemories(): void {
  const blob = new Blob([JSON.stringify(memories.value, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "tripmate-memories.json";
  link.click();
  URL.revokeObjectURL(url);
}

onMounted(loadMemories);
</script>

<template>
  <main class="memory-page">
    <header class="profile-heading memory-heading">
      <div>
        <p>Agent memory</p>
        <h1>旅行记忆</h1>
      </div>
      <div class="memory-heading__actions">
        <button
          class="quiet-action"
          type="button"
          :disabled="!memories.length"
          @click="exportMemories"
        >
          <Download :size="16" :stroke-width="1.8" />
          导出
        </button>
        <button
          class="quiet-action quiet-action--danger"
          type="button"
          :disabled="!memories.length"
          @click="clearConfirmOpen = true"
        >
          <Trash2 :size="16" :stroke-width="1.8" />
          全部清除
        </button>
      </div>
    </header>

    <p v-if="message" class="form-success" role="status">{{ message }}</p>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>

    <form class="memory-create" @submit.prevent="createMemory">
      <label class="field memory-create__category">
        <span>类型</span>
        <span class="field__control">
          <select v-model="form.category">
            <option
              v-for="(label, value) in categoryLabels"
              :key="value"
              :value="value"
            >
              {{ label }}
            </option>
          </select>
        </span>
      </label>
      <label class="field memory-create__content">
        <span>记忆内容</span>
        <span class="field__control">
          <input
            v-model.trim="form.content"
            maxlength="1000"
            required
            placeholder="例如：住宿优先靠近地铁站"
          />
        </span>
      </label>
      <label class="check-control memory-create__consent">
        <input v-model="form.consent" type="checkbox" />
        <span>允许用于后续规划</span>
      </label>
      <button class="primary-button" type="submit" :disabled="submitting || !form.consent">
        <Plus :size="16" :stroke-width="1.9" />
        保存记忆
      </button>
    </form>

    <section class="memory-list" aria-live="polite">
      <div v-if="loading" class="memory-state">
        正在加载
      </div>
      <div v-else-if="!memories.length" class="memory-state">
        还没有旅行记忆
      </div>
      <template v-else>
        <article
          v-for="memory in memories"
          :key="memory.id"
          class="memory-row"
          :class="{ 'is-disabled': !memory.enabled }"
        >
          <template v-if="editingId === memory.id">
            <select v-model="editingCategory">
              <option
                v-for="(label, value) in categoryLabels"
                :key="value"
                :value="value"
              >
                {{ label }}
              </option>
            </select>
            <input v-model.trim="editingContent" maxlength="1000" />
            <span class="memory-row__actions">
              <button
                class="icon-action"
                type="button"
                aria-label="保存记忆"
                :disabled="submitting || !editingContent"
                @click="saveEdit(memory)"
              >
                <Save :size="16" :stroke-width="1.8" />
              </button>
              <button
                class="icon-action"
                type="button"
                aria-label="取消编辑"
                @click="editingId = null"
              >
                <X :size="16" :stroke-width="1.8" />
              </button>
            </span>
          </template>
          <template v-else>
            <span class="memory-row__category">{{ categoryLabels[memory.category] }}</span>
            <span class="memory-row__content">{{ memory.content }}</span>
            <span class="memory-row__actions">
              <button
                class="icon-action"
                type="button"
                :aria-label="memory.enabled ? '停用记忆' : '启用记忆'"
                @click="toggleMemory(memory)"
              >
                <Power :size="16" :stroke-width="1.8" />
              </button>
              <button
                class="icon-action"
                type="button"
                aria-label="编辑记忆"
                @click="startEdit(memory)"
              >
                <Pencil :size="15" :stroke-width="1.8" />
              </button>
              <button
                class="icon-action icon-action--danger"
                type="button"
                aria-label="删除记忆"
                @click="pendingDelete = memory"
              >
                <Trash2 :size="15" :stroke-width="1.8" />
              </button>
            </span>
          </template>
        </article>
      </template>
    </section>

    <Transition name="dialog-fade">
      <div
        v-if="pendingDelete"
        class="dialog-backdrop"
        role="presentation"
        @click.self="pendingDelete = null"
      >
        <section
          class="confirm-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="memory-delete-title"
        >
          <header>
            <h2 id="memory-delete-title">删除这条记忆？</h2>
            <button
              class="icon-action"
              type="button"
              aria-label="关闭删除确认"
              @click="pendingDelete = null"
            >
              <X :size="18" :stroke-width="1.8" />
            </button>
          </header>
          <p>{{ pendingDelete.content }}</p>
          <footer>
            <button class="quiet-action" type="button" @click="pendingDelete = null">
              取消
            </button>
            <button
              class="quiet-action quiet-action--danger"
              type="button"
              :disabled="submitting"
              @click="deleteMemory"
            >
              确认删除
            </button>
          </footer>
        </section>
      </div>
    </Transition>

    <Transition name="dialog-fade">
      <div
        v-if="clearConfirmOpen"
        class="dialog-backdrop"
        role="presentation"
        @click.self="clearConfirmOpen = false"
      >
        <section
          class="confirm-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="memory-clear-title"
        >
          <header>
            <h2 id="memory-clear-title">清除全部旅行记忆？</h2>
            <button
              class="icon-action"
              type="button"
              aria-label="关闭清除确认"
              @click="clearConfirmOpen = false"
            >
              <X :size="18" :stroke-width="1.8" />
            </button>
          </header>
          <p>清除后，后续规划将不再读取这些记忆。</p>
          <footer>
            <button class="quiet-action" type="button" @click="clearConfirmOpen = false">
              取消
            </button>
            <button
              class="quiet-action quiet-action--danger"
              type="button"
              :disabled="submitting"
              @click="clearMemories"
            >
              确认清除
            </button>
          </footer>
        </section>
      </div>
    </Transition>
  </main>
</template>
