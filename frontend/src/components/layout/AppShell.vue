<script setup lang="ts">
import AppHeader from "./AppHeader.vue";
import AppSidebar from "./AppSidebar.vue";
</script>

<template>
  <div class="shell">
    <div class="shell__grid">
      <AppSidebar />
      <main class="shell__content">
        <AppHeader />
        <section class="shell__page app-panel">
          <slot />
        </section>
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  padding: 20px;
  background:
    linear-gradient(transparent 23px, var(--app-grid-line) 24px),
    linear-gradient(90deg, transparent 23px, var(--app-grid-line) 24px);
  background-size: 24px 24px;
}

.shell__grid {
  display: flex;
  gap: 18px;
  min-height: calc(100vh - 40px);
}

.shell__content {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 18px;
}

.shell__page {
  flex: 1;
  padding: 26px;
}

@media (max-width: 1024px) {
  .shell {
    padding: 12px;
  }

  .shell__grid {
    flex-direction: column;
  }

  .shell__page {
    padding: 20px;
  }
}
</style>
