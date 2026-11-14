<!-- 文件说明：前端功能模块：ChatAttachmentPicker。 -->
<script setup lang="ts">
import { FileText, Image, Paperclip, X } from "lucide-vue-next";
import { onBeforeUnmount, ref } from "vue";

import type { PendingAttachment } from "./types";

const props = defineProps<{
  attachments: PendingAttachment[];
  disabled?: boolean;
}>();

const emit = defineEmits<{
  "update:attachments": [attachments: PendingAttachment[]];
}>();

const input = ref<HTMLInputElement | null>(null);
const localError = ref("");
const maxFiles = 3;
const maxImageBytes = 5 * 1024 * 1024;
const maxDocumentBytes = 10 * 1024 * 1024;
const acceptedTypes = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
  "application/pdf",
  "text/plain",
  "text/markdown",
]);

function openPicker(): void {
  if (props.disabled) return;
  localError.value = "";
  input.value?.click();
}

function onFiles(event: Event): void {
  const target = event.target as HTMLInputElement;
  const incoming = Array.from(target.files ?? []);
  target.value = "";
  if (!incoming.length) return;
  if (props.attachments.length + incoming.length > maxFiles) {
    localError.value = "最多添加 3 个附件";
    return;
  }

  const next = [...props.attachments];
  for (const file of incoming) {
    const isImage = acceptedTypes.has(file.type) && file.type.startsWith("image/");
    const isDocument = acceptedTypes.has(file.type) && !isImage;
    if (!isImage && !isDocument) {
      localError.value = "仅支持图片、PDF、TXT 和 Markdown";
      return;
    }
    if (isImage && file.size > maxImageBytes) {
      localError.value = `${file.name} 超过 5 MB`;
      return;
    }
    if (isDocument && file.size > maxDocumentBytes) {
      localError.value = `${file.name} 超过 10 MB`;
      return;
    }
    next.push({
      key: crypto.randomUUID?.() ?? `${Date.now()}-${file.name}`,
      file,
      previewUrl: isImage ? URL.createObjectURL(file) : null,
    });
  }
  emit("update:attachments", next);
}

function removeAttachment(attachment: PendingAttachment): void {
  if (attachment.previewUrl) URL.revokeObjectURL(attachment.previewUrl);
  emit(
    "update:attachments",
    props.attachments.filter((item) => item.key !== attachment.key),
  );
}

function formatSize(size: number): string {
  return size >= 1024 * 1024
    ? `${(size / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(size / 1024))} KB`;
}

onBeforeUnmount(() => {
  props.attachments.forEach((attachment) => {
    if (attachment.previewUrl) URL.revokeObjectURL(attachment.previewUrl);
  });
});
</script>

<template>
  <div class="attachment-picker">
    <input
      ref="input"
      class="sr-only"
      type="file"
      multiple
      accept="image/png,image/jpeg,image/webp,application/pdf,text/plain,text/markdown"
      @change="onFiles"
    />
    <button
      class="attachment-picker__trigger"
      type="button"
      :disabled="disabled"
      aria-label="添加图片或文件"
      title="添加图片或文件"
      @click="openPicker"
    >
      <Paperclip :size="17" :stroke-width="1.8" />
    </button>

    <div v-if="attachments.length" class="attachment-picker__files">
      <span
        v-for="attachment in attachments"
        :key="attachment.key"
        class="attachment-chip"
      >
        <img
          v-if="attachment.previewUrl"
          :src="attachment.previewUrl"
          alt=""
        />
        <Image
          v-else-if="attachment.file.type.startsWith('image/')"
          :size="15"
        />
        <FileText v-else :size="15" />
        <span>
          <strong>{{ attachment.file.name }}</strong>
          <small>{{ formatSize(attachment.file.size) }}</small>
        </span>
        <button
          type="button"
          aria-label="移除附件"
          @click="removeAttachment(attachment)"
        >
          <X :size="13" />
        </button>
      </span>
    </div>
    <span v-if="localError" class="attachment-picker__error" role="alert">
      {{ localError }}
    </span>
  </div>
</template>
