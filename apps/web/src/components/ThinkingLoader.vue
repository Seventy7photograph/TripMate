<!-- 文件说明：对话思考等待动画。 -->
<template>
  <span
    class="thinking-loader"
    data-testid="thinking-loader"
    aria-hidden="true"
  >
    <svg viewBox="0 0 240 240" focusable="false">
      <circle class="thinking-loader__ring thinking-loader__ring--a" cx="120" cy="120" r="105" />
      <circle class="thinking-loader__ring thinking-loader__ring--b" cx="120" cy="120" r="35" />
      <circle class="thinking-loader__ring thinking-loader__ring--c" cx="85" cy="120" r="70" />
      <circle class="thinking-loader__ring thinking-loader__ring--d" cx="155" cy="120" r="70" />
    </svg>
  </span>
</template>

<style scoped>
.thinking-loader {
  display: inline-grid;
  width: 54px;
  height: 54px;
  flex: 0 0 54px;
  place-items: center;
}

.thinking-loader svg {
  width: 100%;
  height: 100%;
  overflow: visible;
}

.thinking-loader__ring {
  fill: none;
  stroke-linecap: round;
  transform-origin: center;
}

.thinking-loader__ring--a {
  animation: ring-a 2s linear infinite;
  stroke: #9b5a38;
}

.thinking-loader__ring--b {
  animation: ring-b 2s linear infinite;
  stroke: #b59047;
}

.thinking-loader__ring--c {
  animation: ring-c 2s linear infinite;
  stroke: #406d69;
}

.thinking-loader__ring--d {
  animation: ring-d 2s linear infinite;
  stroke: #b25c72;
}

@keyframes ring-a {
  from,
  4% {
    stroke-dasharray: 0 660;
    stroke-dashoffset: -330;
    stroke-width: 20;
  }
  12%,
  32% {
    stroke-dasharray: 60 600;
    stroke-width: 30;
  }
  12% {
    stroke-dashoffset: -335;
  }
  32% {
    stroke-dashoffset: -595;
  }
  40%,
  54% {
    stroke-dasharray: 0 660;
    stroke-dashoffset: -660;
    stroke-width: 20;
  }
  62%,
  82% {
    stroke-dasharray: 60 600;
    stroke-width: 30;
  }
  62% {
    stroke-dashoffset: -665;
  }
  82% {
    stroke-dashoffset: -925;
  }
  90%,
  to {
    stroke-dasharray: 0 660;
    stroke-dashoffset: -990;
    stroke-width: 20;
  }
}

@keyframes ring-b {
  from,
  12% {
    stroke-dasharray: 0 220;
    stroke-dashoffset: -110;
    stroke-width: 20;
  }
  20%,
  40% {
    stroke-dasharray: 20 200;
    stroke-width: 30;
  }
  20% {
    stroke-dashoffset: -115;
  }
  40% {
    stroke-dashoffset: -195;
  }
  48%,
  62% {
    stroke-dasharray: 0 220;
    stroke-dashoffset: -220;
    stroke-width: 20;
  }
  70%,
  90% {
    stroke-dasharray: 20 200;
    stroke-width: 30;
  }
  70% {
    stroke-dashoffset: -225;
  }
  90% {
    stroke-dashoffset: -305;
  }
  98%,
  to {
    stroke-dasharray: 0 220;
    stroke-dashoffset: -330;
    stroke-width: 20;
  }
}

@keyframes ring-c {
  from {
    stroke-dasharray: 0 440;
    stroke-dashoffset: 0;
    stroke-width: 20;
  }
  8%,
  28% {
    stroke-dasharray: 40 400;
    stroke-width: 30;
  }
  8% {
    stroke-dashoffset: -5;
  }
  28% {
    stroke-dashoffset: -175;
  }
  36%,
  58% {
    stroke-dasharray: 0 440;
    stroke-dashoffset: -220;
    stroke-width: 20;
  }
  66%,
  86% {
    stroke-dasharray: 40 400;
    stroke-width: 30;
  }
  66% {
    stroke-dashoffset: -225;
  }
  86% {
    stroke-dashoffset: -395;
  }
  94%,
  to {
    stroke-dasharray: 0 440;
    stroke-dashoffset: -440;
    stroke-width: 20;
  }
}

@keyframes ring-d {
  from,
  8% {
    stroke-dasharray: 0 440;
    stroke-dashoffset: 0;
    stroke-width: 20;
  }
  16%,
  36% {
    stroke-dasharray: 40 400;
    stroke-width: 30;
  }
  16% {
    stroke-dashoffset: -5;
  }
  36% {
    stroke-dashoffset: -175;
  }
  44%,
  50% {
    stroke-dasharray: 0 440;
    stroke-dashoffset: -220;
    stroke-width: 20;
  }
  58%,
  78% {
    stroke-dasharray: 40 400;
    stroke-width: 30;
  }
  58% {
    stroke-dashoffset: -225;
  }
  78% {
    stroke-dashoffset: -395;
  }
  86%,
  to {
    stroke-dasharray: 0 440;
    stroke-dashoffset: -440;
    stroke-width: 20;
  }
}

@media (prefers-reduced-motion: reduce) {
  .thinking-loader__ring {
    animation: none;
    stroke-dasharray: 34 406;
    stroke-width: 22;
  }
}
</style>
