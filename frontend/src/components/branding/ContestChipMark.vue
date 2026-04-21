<script setup lang="ts">
/**
 * 代码绘制的竞赛芯片标识。
 * 这里直接使用 SVG 复刻参考图中的“芯片 + 9th”结构，避免贴图方案带来的位图感和缩放失真。
 */
</script>

<template>
  <svg
    class="contest-chip"
    viewBox="0 0 92 92"
    role="img"
    aria-label="第九届嵌入式芯片与系统设计竞赛芯片标识"
  >
    <g class="contest-chip__pins">
      <path d="M28 18V8" />
      <path d="M37 18V8" />
      <path d="M46 18V8" />
      <path d="M55 18V8" />
      <path d="M64 18V8" />

      <path d="M28 84V74" />
      <path d="M37 84V74" />
      <path d="M46 84V74" />
      <path d="M55 84V74" />
      <path d="M64 84V74" />

      <path d="M18 28H8" />
      <path d="M18 37H8" />
      <path d="M18 46H8" />
      <path d="M18 55H8" />
      <path d="M18 64H8" />

      <path d="M84 28H74" />
      <path d="M84 37H74" />
      <path d="M84 46H74" />
      <path d="M84 55H74" />
      <path d="M84 64H74" />
    </g>

    <rect class="contest-chip__frame" x="18" y="18" width="56" height="56" rx="8" />
    <rect class="contest-chip__core" x="23" y="23" width="46" height="46" rx="5" />
    <text class="contest-chip__number" x="39" y="53">9</text>
    <text class="contest-chip__suffix" x="52" y="55">th</text>
  </svg>
</template>

<style scoped>
.contest-chip {
  display: block;
  width: 100%;
  height: auto;
  overflow: visible;
  color: var(--contest-brand-ink, #2d5f90);
}

.contest-chip__pins {
  fill: none;
  stroke: currentColor;
  stroke-width: 2.8;
  stroke-linecap: round;
  opacity: 0.94;
}

.contest-chip__frame {
  fill: none;
  stroke: currentColor;
  stroke-width: 3.2;
}

.contest-chip__core {
  fill: var(--contest-brand-core, rgba(248, 251, 255, 0.98));
  stroke: color-mix(in srgb, currentColor 26%, white);
  stroke-width: 0.8;
}

.contest-chip__number,
.contest-chip__suffix {
  fill: currentColor;
  font-family: "Bahnschrift", "Segoe UI", "Microsoft YaHei", sans-serif;
  font-style: normal;
}

.contest-chip__number {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.04em;
}

.contest-chip__suffix {
  font-size: 12px;
  font-weight: 800;
  letter-spacing: -0.02em;
}
</style>
