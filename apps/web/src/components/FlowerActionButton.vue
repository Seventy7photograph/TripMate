<!-- 文件说明：Vue 组件：FlowerActionButton。 -->
<script setup lang="ts">
// 首次规划和会话发送共用同一套花瓣交互动效。
defineProps<{
  label: string;
  busy?: boolean;
  disabled?: boolean;
}>();
</script>

<template>
  <button
    class="btn flower-action"
    :class="{ 'is-busy': busy }"
    type="submit"
    :disabled="disabled"
    :aria-label="label"
  >
    <span class="wrapper">
      <span class="text">{{ label }}</span>
      <span
        v-for="index in 6"
        :key="index"
        class="flower"
        :class="`flower${index}`"
        aria-hidden="true"
      >
        <span class="petal one" />
        <span class="petal two" />
        <span class="petal three" />
        <span class="petal four" />
      </span>
    </span>
  </button>
</template>

<style scoped>
.btn {
  display: grid;
  width: 12em;
  height: 4em;
  place-items: center;
  padding: 0;
  border: 0;
  background: transparent;
  color: #121719;
  cursor: pointer;
}

.wrapper {
  position: relative;
  display: grid;
  width: 8em;
  height: 2em;
  place-items: center;
  background: transparent;
}

.text {
  z-index: 2;
  margin: 0;
  padding: 4px 12px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.7);
  color: #000;
  font-size: 17px;
  font-weight: 650;
  line-height: 1.2;
  transition:
    background-color 0.5s ease,
    transform 0.5s ease;
}

.flower {
  position: absolute;
  display: grid;
  grid-template-columns: 1em 1em;
  transition: grid-template-columns 0.8s ease;
}

.flower1 {
  top: -12px;
  left: -13px;
  transform: rotate(5deg);
}

.flower2 {
  bottom: -5px;
  left: 8px;
  transform: rotate(35deg);
}

.flower3 {
  bottom: -15px;
  transform: rotate(0deg);
}

.flower4 {
  top: -14px;
  transform: rotate(15deg);
}

.flower5 {
  top: -3px;
  right: 11px;
  transform: rotate(25deg);
}

.flower6 {
  right: -15px;
  bottom: -15px;
  transform: rotate(30deg);
}

.petal {
  z-index: 0;
  width: 1em;
  height: 1em;
  border: 0.5px solid #96d1ec;
  border-radius: 40% 70% / 7% 90%;
  background: linear-gradient(#07a6d7, #93e0ee);
  transition:
    width 0.8s ease,
    height 0.8s ease,
    background 0.35s ease,
    border-color 0.35s ease;
}

.two {
  transform: rotate(90deg);
}

.three {
  transform: rotate(270deg);
}

.four {
  transform: rotate(180deg);
}

.btn:hover:not(:disabled) .petal {
  border-color: #96b4ec;
  background: linear-gradient(#0761d7, #93bdee);
}

.btn:hover:not(:disabled) .flower {
  grid-template-columns: 1.5em 1.5em;
}

.btn:hover:not(:disabled) .flower .petal {
  width: 1.5em;
  height: 1.5em;
}

.btn:hover:not(:disabled) .text {
  background: rgba(255, 255, 255, 0.4);
  transform: scale(1.02);
}

.btn:hover:not(:disabled) .flower1 {
  animation: flower1 15s linear infinite;
}

.btn:hover:not(:disabled) .flower2 {
  animation: flower2 13s linear 1s infinite;
}

.btn:hover:not(:disabled) .flower3 {
  animation: flower3 16s linear 1s infinite;
}

.btn:hover:not(:disabled) .flower4 {
  animation: flower4 17s linear 1s infinite;
}

.btn:hover:not(:disabled) .flower5 {
  animation: flower5 20s linear 1s infinite;
}

.btn:hover:not(:disabled) .flower6 {
  animation: flower6 15s linear 1s infinite;
}

.btn:focus-visible {
  outline: 2px solid #116a86;
  outline-offset: 4px;
  border-radius: 8px;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.btn.is-busy .flower {
  animation-play-state: paused;
}

@keyframes flower1 {
  from { transform: rotate(5deg); }
  to { transform: rotate(365deg); }
}

@keyframes flower2 {
  from { transform: rotate(35deg); }
  to { transform: rotate(-325deg); }
}

@keyframes flower3 {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes flower4 {
  from { transform: rotate(15deg); }
  to { transform: rotate(375deg); }
}

@keyframes flower5 {
  from { transform: rotate(25deg); }
  to { transform: rotate(-335deg); }
}

@keyframes flower6 {
  from { transform: rotate(30deg); }
  to { transform: rotate(390deg); }
}

@media (prefers-reduced-motion: reduce) {
  .btn,
  .flower,
  .petal,
  .text {
    animation: none !important;
    transition: none;
  }
}
</style>
