<script setup lang="ts">
/**
 * 代码绘制的竞赛横向字标。
 * 这里使用单一 SVG 同时绘制芯片与双语口号，避免“图标和文字像后拼上去”的割裂感。
 */
</script>

<template>
  <svg
    class="contest-logo"
    viewBox="0 0 980 190"
    role="img"
    aria-label="AI赋能设计，设计点亮AI"
  >
    <g class="contest-logo__mark">
      <g class="contest-logo__pins">
        <path d="M34 42V26" />
        <path d="M48 42V26" />
        <path d="M62 42V26" />
        <path d="M76 42V26" />
        <path d="M90 42V26" />

        <path d="M34 140V124" />
        <path d="M48 140V124" />
        <path d="M62 140V124" />
        <path d="M76 140V124" />
        <path d="M90 140V124" />

        <path d="M26 50H10" />
        <path d="M26 64H10" />
        <path d="M26 78H10" />
        <path d="M26 92H10" />
        <path d="M26 106H10" />

        <path d="M114 50H130" />
        <path d="M114 64H130" />
        <path d="M114 78H130" />
        <path d="M114 92H130" />
        <path d="M114 106H130" />
      </g>

      <rect class="contest-logo__frame" x="26" y="42" width="88" height="88" rx="12" />
      <rect class="contest-logo__core" x="34" y="50" width="72" height="72" rx="8" />
      <text class="contest-logo__number" x="49" y="97">9</text>
      <text class="contest-logo__suffix" x="71" y="100">th</text>
    </g>

    <text class="contest-logo__title" x="152" y="92">AI赋能设计，设计点亮AI!</text>
    <text class="contest-logo__subtitle" x="152" y="142">AI for Design &amp; Design for AI!</text>
  </svg>
</template>

<style scoped>
.contest-logo {
  display: block;
  width: 100%;
  height: auto;
  overflow: visible;
}

.contest-logo__pins {
  fill: none;
  stroke: #2d5f90;
  stroke-width: 4;
  stroke-linecap: round;
}

.contest-logo__frame {
  fill: none;
  stroke: #2d5f90;
  stroke-width: 4.8;
}

.contest-logo__core {
  fill: rgba(249, 252, 255, 0.98);
  stroke: rgba(79, 115, 152, 0.24);
  stroke-width: 1.2;
}

.contest-logo__number,
.contest-logo__suffix,
.contest-logo__title,
.contest-logo__subtitle {
  fill: #2d5f90;
  font-family: "Bahnschrift", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.contest-logo__number {
  font-size: 46px;
  font-weight: 700;
  letter-spacing: -0.05em;
}

.contest-logo__suffix {
  font-size: 19px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.contest-logo__title {
  font-size: 64px;
  font-weight: 700;
  letter-spacing: -0.05em;
}

.contest-logo__subtitle {
  font-size: 37px;
  font-weight: 700;
  letter-spacing: -0.018em;
}
</style>
