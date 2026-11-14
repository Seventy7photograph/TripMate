<!-- 文件说明：Vue 组件：带叶片风动效果的通用操作按钮。 -->
<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";

const props = withDefaults(
  defineProps<{
    label: string;
    to?: string;
    type?: "button" | "submit" | "reset";
    disabled?: boolean;
    width?: string;
  }>(),
  {
    to: undefined,
    type: "button",
    disabled: false,
    width: undefined,
  },
);

const component = computed(() => (props.to ? RouterLink : "button"));
const componentProps = computed(() =>
  props.to
    ? { to: props.to, "aria-label": props.label }
    : {
        type: props.type,
        disabled: props.disabled,
        "aria-label": props.label,
      },
);
const style = computed(() =>
  props.width ? { width: props.width } : undefined,
);
</script>

<template>
  <component
    :is="component"
    class="leaf-action"
    :style="style"
    v-bind="componentProps"
  >
    <span class="leaf-action__content">
      <slot name="icon" />
      <span><slot>{{ label }}</slot></span>
    </span>
    <span class="leaf-action__icon leaf-action__icon--1" aria-hidden="true">
      <svg viewBox="0 0 48 84">
        <path class="stem" d="M28 2C24 24 21 51 14 82" />
        <path d="M27 13C18 10 11 14 7 21C16 24 24 21 27 13Z" />
        <path d="M27 13C32 7 39 7 44 13C38 19 31 20 27 13Z" />
        <path d="M25 25C15 22 9 26 5 33C15 36 22 33 25 25Z" />
        <path d="M25 25C31 19 38 19 43 25C37 31 30 32 25 25Z" />
        <path d="M23 37C14 34 8 38 4 45C14 48 21 45 23 37Z" />
        <path d="M23 37C28 31 35 31 40 37C34 43 28 44 23 37Z" />
        <path d="M21 49C13 46 7 50 3 57C12 60 19 57 21 49Z" />
        <path d="M21 49C26 43 33 43 38 49C32 55 26 56 21 49Z" />
        <path d="M19 61C11 58 6 62 3 68C12 71 18 68 19 61Z" />
        <path d="M19 61C24 55 30 55 35 61C29 67 24 68 19 61Z" />
      </svg>
    </span>
    <span class="leaf-action__icon leaf-action__icon--2" aria-hidden="true">
      <svg viewBox="0 0 48 84">
        <path class="stem" d="M29 2C25 25 21 54 15 82" />
        <path d="M28 14C19 11 12 15 8 22C17 25 25 22 28 14Z" />
        <path d="M28 14C33 8 40 8 45 14C39 20 32 21 28 14Z" />
        <path d="M26 27C17 24 10 28 6 35C16 38 23 35 26 27Z" />
        <path d="M26 27C32 21 39 21 44 27C38 33 31 34 26 27Z" />
        <path d="M23 41C15 38 9 42 5 49C14 52 21 49 23 41Z" />
        <path d="M23 41C28 35 35 35 40 41C34 47 28 48 23 41Z" />
        <path d="M20 56C12 53 7 57 4 64C13 67 19 64 20 56Z" />
        <path d="M20 56C25 50 31 50 36 56C30 62 24 63 20 56Z" />
      </svg>
    </span>
    <span class="leaf-action__icon leaf-action__icon--3" aria-hidden="true">
      <svg viewBox="0 0 48 84">
        <path class="stem" d="M26 2C24 27 23 55 25 82" />
        <path d="M25 12C16 9 9 13 5 20C14 23 22 20 25 12Z" />
        <path d="M25 12C30 6 37 6 42 12C36 18 29 19 25 12Z" />
        <path d="M25 24C15 21 9 25 5 32C15 35 22 32 25 24Z" />
        <path d="M25 24C31 18 38 18 43 24C37 30 30 31 25 24Z" />
        <path d="M24 36C15 33 9 37 5 44C15 47 22 44 24 36Z" />
        <path d="M24 36C29 30 36 30 41 36C35 42 29 43 24 36Z" />
        <path d="M24 48C15 45 9 49 5 56C15 59 22 56 24 48Z" />
        <path d="M24 48C29 42 36 42 41 48C35 54 29 55 24 48Z" />
        <path d="M25 60C16 57 10 61 6 68C16 71 23 68 25 60Z" />
        <path d="M25 60C30 54 37 54 42 60C36 66 30 68 25 60Z" />
        <path d="M25 72C18 69 13 73 10 78C18 81 24 78 25 72Z" />
        <path d="M25 72C30 66 36 66 40 72C35 78 30 80 25 72Z" />
      </svg>
    </span>
  </component>
</template>

<style scoped>
.leaf-action {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 15px 45px;
  overflow: visible;
  border: 1px solid #fec195;
  border-radius: 8px;
  background: #fec195;
  color: #181818;
  cursor: pointer;
  filter: drop-shadow(2px 2px 3px rgba(0, 0, 0, 0.2));
  font-size: 17px;
  font-weight: 500;
  line-height: 1;
  transition:
    background-color 180ms ease,
    border-color 180ms ease,
    filter 180ms ease;
}

.leaf-action:hover:not(:disabled),
.leaf-action:focus-visible {
  border-color: #f3b182;
  background: linear-gradient(
    85deg,
    #fec195,
    #fcc196,
    #fabd92,
    #fac097,
    #fac39c
  );
  background-size: 180% 180%;
  outline: none;
  animation: wind 2s ease-in-out infinite;
}

.leaf-action:focus-visible {
  box-shadow: 0 0 0 3px rgba(243, 177, 130, 0.32);
}

.leaf-action:disabled {
  cursor: wait;
  opacity: 0.62;
}

.leaf-action__content {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  white-space: nowrap;
}

.leaf-action__icon {
  position: absolute;
  top: 0;
  display: block;
  transform-origin: 50% 0;
  transition: transform 0.5s ease-in-out;
  filter: drop-shadow(2px 2px 3px rgba(0, 0, 0, 0.28));
  will-change: transform;
}

.leaf-action__icon svg {
  display: block;
  width: 100%;
  height: auto;
  fill: currentColor;
}

.leaf-action__icon .stem {
  fill: none;
  stroke: currentColor;
  stroke-width: 1.4;
  stroke-linecap: round;
}

.leaf-action__icon--1 {
  right: 0;
  width: 28px;
  transform: rotate(10deg);
}

.leaf-action__icon--2 {
  left: 25px;
  width: 14px;
  transform: rotate(10deg);
}

.leaf-action__icon--3 {
  left: 0;
  width: 20px;
  transform: rotate(-5deg);
}

.leaf-action:hover:not(:disabled) .leaf-action__icon--1 {
  animation: leaf-1 3s cubic-bezier(0.52, 0, 0.58, 1) infinite;
}

.leaf-action:hover:not(:disabled) .leaf-action__icon--2 {
  animation: leaf-2 3s cubic-bezier(0.52, 0, 0.58, 1) 0.08s infinite;
}

.leaf-action:hover:not(:disabled) .leaf-action__icon--3 {
  animation: leaf-3 2.4s cubic-bezier(0.52, 0, 0.58, 1) 0.16s infinite;
}

@keyframes wind {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

@keyframes leaf-1 {
  0%, 100% { transform: rotate(10deg); }
  50% { transform: rotate(-5deg); }
}

@keyframes leaf-2 {
  0%, 100% { transform: rotate(10deg); }
  50% { transform: rotate(18deg); }
}

@keyframes leaf-3 {
  0%, 100% { transform: rotate(-5deg); }
  50% { transform: rotate(-12deg); }
}

@media (prefers-reduced-motion: reduce) {
  .leaf-action,
  .leaf-action__icon {
    animation: none !important;
    transition: none;
  }
}
</style>
