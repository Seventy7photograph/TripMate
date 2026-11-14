<!-- 文件说明：前端页面：FavoritesView。 -->
<script setup lang="ts">
import {
  Download,
  ExternalLink,
  FolderHeart,
  MapPin,
  Pencil,
  RefreshCw,
  Route,
  Search,
  Trash2,
  X,
} from "lucide-vue-next";
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";

import { favoriteApi } from "../../features/share/api";
import type { Favorite } from "../../features/share/types";
import { useAuthStore } from "../../stores/auth";

const auth = useAuthStore();
const favorites = ref<Favorite[]>([]);
const loading = ref(true);
const error = ref("");
const message = ref("");
const kind = ref<"all" | "place" | "trip">("all");
const folder = ref("all");
const query = ref("");
const editing = ref<Favorite | null>(null);
const saving = ref(false);
const editForm = reactive({
  folder: "",
  note: "",
});
const kindOptions = [
  { value: "all", label: "全部收藏" },
  { value: "place", label: "地点收藏" },
  { value: "trip", label: "行程收藏" },
] as const;

const folders = computed(() =>
  [...new Set(favorites.value.map((item) => item.folder))].sort((a, b) =>
    a.localeCompare(b, "zh-CN"),
  ),
);

const filtered = computed(() => {
  const keyword = query.value.trim().toLowerCase();
  return favorites.value.filter((item) => {
    if (kind.value !== "all" && item.kind !== kind.value) return false;
    if (folder.value !== "all" && item.folder !== folder.value) return false;
    if (
      keyword &&
      !item.label.toLowerCase().includes(keyword) &&
      !(item.note ?? "").toLowerCase().includes(keyword)
    ) {
      return false;
    }
    return true;
  });
});

function kindCount(value: "all" | "place" | "trip"): number {
  return value === "all"
    ? favorites.value.length
    : favorites.value.filter((item) => item.kind === value).length;
}

function favoriteKindLabel(item: Favorite): string {
  return item.kind === "place" ? "地点收藏" : "行程收藏";
}

function favoriteMeta(item: Favorite): string {
  const kindLabel = favoriteKindLabel(item);
  const folder = item.folder.trim();
  const folderLabel =
    !folder || folder === "默认收藏" || folder === kindLabel
      ? kindLabel
      : `${kindLabel} · ${folder}`;
  return `${folderLabel} · ${formatDate(item.created_at)}`;
}

const emptyTitle = computed(() => {
  if (kind.value === "place") return "还没有地点收藏";
  if (kind.value === "trip") return "还没有行程收藏";
  return "还没有收藏";
});

async function load(): Promise<void> {
  if (!auth.token) return;
  loading.value = true;
  error.value = "";
  try {
    favorites.value = await favoriteApi.list(auth.token);
  } catch {
    error.value = "收藏列表加载失败。";
  } finally {
    loading.value = false;
  }
}

function startEdit(item: Favorite): void {
  editing.value = item;
  editForm.folder = item.folder;
  editForm.note = item.note ?? "";
}

async function saveEdit(): Promise<void> {
  if (!auth.token || !editing.value || saving.value) return;
  saving.value = true;
  error.value = "";
  message.value = "";
  try {
    const updated = await favoriteApi.update(auth.token, editing.value.id, {
      folder: editForm.folder.trim() || favoriteKindLabel(editing.value),
      note: editForm.note.trim() || null,
    });
    favorites.value = favorites.value.map((item) =>
      item.id === updated.id ? updated : item,
    );
    editing.value = null;
    message.value = "收藏已更新";
  } catch {
    error.value = "收藏更新失败。";
  } finally {
    saving.value = false;
  }
}

async function remove(item: Favorite): Promise<void> {
  if (!auth.token) return;
  if (!window.confirm(`删除收藏“${item.label}”？`)) return;
  error.value = "";
  try {
    await favoriteApi.remove(auth.token, item.id);
    favorites.value = favorites.value.filter((favorite) => favorite.id !== item.id);
    if (editing.value?.id === item.id) editing.value = null;
    message.value = "收藏已删除";
  } catch {
    error.value = "收藏删除失败。";
  }
}

function exportFavorites(): void {
  const blob = new Blob([JSON.stringify(filtered.value, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "tripmate-favorites.json";
  link.click();
  URL.revokeObjectURL(url);
}

function targetLink(item: Favorite): string {
  return item.kind === "trip"
    ? `/trips/${item.target_id}`
    : `/places?q=${encodeURIComponent(item.label)}`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}

onMounted(load);
</script>

<template>
  <main class="favorites-page">
    <header class="favorites-heading">
      <div>
        <p>Saved places & trips</p>
        <h1>收藏</h1>
      </div>
      <div class="favorites-heading__actions">
        <button
          class="quiet-action"
          type="button"
          :disabled="!filtered.length"
          @click="exportFavorites"
        >
          <Download :size="16" :stroke-width="1.8" />
          导出
        </button>
        <button class="quiet-action" type="button" :disabled="loading" @click="load">
          <RefreshCw :size="16" :stroke-width="1.8" :class="{ 'is-spinning': loading }" />
          刷新
        </button>
      </div>
    </header>

    <nav class="favorites-type-tabs" role="tablist" aria-label="收藏类型">
      <button
        v-for="item in kindOptions"
        :key="item.value"
        type="button"
        role="tab"
        :aria-selected="kind === item.value"
        :class="{ 'is-active': kind === item.value }"
        @click="kind = item.value"
      >
        {{ item.label }}
        <span>{{ kindCount(item.value) }}</span>
      </button>
    </nav>

    <div class="favorites-controls">
      <label class="field favorites-search">
        <span>搜索收藏</span>
        <span class="field__control">
          <Search :size="16" :stroke-width="1.7" />
          <input v-model.trim="query" placeholder="地点、旅行或备注" />
        </span>
      </label>
      <label class="field">
        <span>收藏夹</span>
        <span class="field__control">
          <select v-model="folder">
            <option value="all">全部收藏夹</option>
            <option v-for="name in folders" :key="name" :value="name">
              {{ name }}
            </option>
          </select>
        </span>
      </label>
    </div>

    <p v-if="message" class="form-success" role="status">{{ message }}</p>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>

    <section class="favorites-list" aria-live="polite">
      <div v-if="loading" class="favorites-state">正在加载</div>
      <div v-else-if="!filtered.length" class="favorites-state">
        <FolderHeart :size="23" :stroke-width="1.6" />
        <strong>{{ emptyTitle }}</strong>
        <RouterLink class="quiet-action" to="/places">去探索地点</RouterLink>
      </div>
      <template v-else>
        <article v-for="item in filtered" :key="item.id" class="favorite-row">
          <span class="favorite-row__icon">
            <MapPin v-if="item.kind === 'place'" :size="18" />
            <Route v-else :size="18" />
          </span>
          <span class="favorite-row__copy">
            <span>
              <strong>{{ item.label }}</strong>
              <small>{{ favoriteMeta(item) }}</small>
            </span>
            <p v-if="item.note">{{ item.note }}</p>
          </span>
          <RouterLink
            class="icon-action"
            :to="targetLink(item)"
            :aria-label="`打开收藏 ${item.label}`"
          >
            <ExternalLink :size="15" :stroke-width="1.8" />
          </RouterLink>
          <button
            class="icon-action"
            type="button"
            :aria-label="`编辑收藏 ${item.label}`"
            @click="startEdit(item)"
          >
            <Pencil :size="15" :stroke-width="1.8" />
          </button>
          <button
            class="icon-action icon-action--danger"
            type="button"
            :aria-label="`删除收藏 ${item.label}`"
            @click="remove(item)"
          >
            <Trash2 :size="15" :stroke-width="1.8" />
          </button>
        </article>
      </template>
    </section>

    <Transition name="dialog-fade">
      <div
        v-if="editing"
        class="dialog-backdrop"
        role="presentation"
        @click.self="editing = null"
      >
        <section
          class="favorite-edit-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="favorite-edit-title"
        >
          <header>
            <div>
              <p>收藏整理</p>
              <h2 id="favorite-edit-title">{{ editing.label }}</h2>
            </div>
            <button
              class="icon-action"
              type="button"
              aria-label="关闭收藏编辑"
              @click="editing = null"
            >
              <X :size="18" :stroke-width="1.8" />
            </button>
          </header>
          <div class="favorite-edit-dialog__body">
            <label class="field">
              <span>收藏夹</span>
              <span class="field__control">
                <input v-model.trim="editForm.folder" maxlength="80" list="favorite-folders" />
              </span>
            </label>
            <datalist id="favorite-folders">
              <option v-for="name in folders" :key="name" :value="name" />
            </datalist>
            <label class="field">
              <span>备注</span>
              <span class="field__control field__control--textarea">
                <textarea v-model.trim="editForm.note" maxlength="2000" rows="4" />
              </span>
            </label>
          </div>
          <footer>
            <button class="quiet-action" type="button" @click="editing = null">
              取消
            </button>
            <button class="primary-button" type="button" :disabled="saving" @click="saveEdit">
              {{ saving ? "保存中" : "保存" }}
            </button>
          </footer>
        </section>
      </div>
    </Transition>
  </main>
</template>
