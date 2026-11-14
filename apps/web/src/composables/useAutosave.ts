// 文件说明：Vue 组合式逻辑：useAutosave。
import { getCurrentScope, onScopeDispose, ref } from "vue";

export type AutosaveStatus = "idle" | "pending" | "saving" | "saved" | "error";

export interface UseAutosaveOptions<T> {
  key: () => string;
  save: (value: T) => Promise<void>;
  delay?: number;
  storage?: Pick<Storage, "getItem" | "setItem" | "removeItem">;
}

export function useAutosave<T>({
  key,
  save,
  delay = 800,
  storage = typeof window === "undefined" ? undefined : window.localStorage,
}: UseAutosaveOptions<T>) {
  const status = ref<AutosaveStatus>("idle");
  const error = ref<unknown>(null);
  const hasDraft = ref(false);

  let timer: ReturnType<typeof setTimeout> | undefined;
  let pendingValue: T | undefined;
  let pendingSerialized: string | null = null;

  function readStored(): string | null {
    if (!storage) return null;
    try {
      return storage.getItem(key());
    } catch {
      return null;
    }
  }

  function writeStored(serialized: string): void {
    if (!storage) return;
    try {
      storage.setItem(key(), serialized);
      hasDraft.value = true;
    } catch {
      hasDraft.value = false;
    }
  }

  function removeStored(): void {
    if (!storage) return;
    try {
      storage.removeItem(key());
    } catch {
      // Storage availability must not break editing.
    }
    hasDraft.value = false;
  }

  async function flush(): Promise<boolean> {
    if (timer) {
      clearTimeout(timer);
      timer = undefined;
    }
    if (pendingSerialized === null || pendingValue === undefined) {
      return true;
    }

    // 固定本次待保存版本，保存期间的新编辑继续保留为 pending。
    const valueToSave = pendingValue;
    const serializedToSave = pendingSerialized;
    status.value = "saving";
    error.value = null;
    try {
      await save(valueToSave);
      if (pendingSerialized === serializedToSave) {
        pendingValue = undefined;
        pendingSerialized = null;
        removeStored();
        status.value = "saved";
      }
      return true;
    } catch (cause) {
      error.value = cause;
      if (pendingSerialized === serializedToSave) {
        status.value = "error";
      }
      return false;
    }
  }

  function schedule(value: T): void {
    // 先写本地草稿，再防抖提交服务端。
    pendingValue = value;
    pendingSerialized = JSON.stringify(value);
    writeStored(pendingSerialized);
    error.value = null;
    status.value = "pending";

    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      void flush();
    }, delay);
  }

  function restoreDraft(): T | null {
    const serialized = readStored();
    if (!serialized) return null;
    try {
      const value = JSON.parse(serialized) as T;
      pendingValue = value;
      pendingSerialized = serialized;
      hasDraft.value = true;
      status.value = "pending";
      return value;
    } catch {
      removeStored();
      return null;
    }
  }

  function discardDraft(): void {
    if (timer) {
      clearTimeout(timer);
      timer = undefined;
    }
    pendingValue = undefined;
    pendingSerialized = null;
    error.value = null;
    removeStored();
    status.value = "idle";
  }

  if (getCurrentScope()) {
    onScopeDispose(() => {
      if (timer) clearTimeout(timer);
    });
  }

  return {
    status,
    error,
    hasDraft,
    schedule,
    flush,
    restoreDraft,
    discardDraft,
  };
}
