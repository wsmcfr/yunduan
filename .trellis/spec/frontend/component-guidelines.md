# Component Guidelines

> How frontend components should be built in this project.

---

## Overview

There are no Vue components yet, so current component guidance is inferred from:

- `MainPagePrototype.qml`, which already separates layout regions and groups related state
- the planned cloud pages in `工业缺陷检测系统完整方案.md`

The main lesson from the existing prototype is:

> a page should compose smaller purpose-specific sections instead of becoming one giant screen component

---

## Component Structure

Preferred Vue SFC structure:

```vue
<script setup lang="ts">
// imports
// props and emits
// composables
// derived state
</script>

<template>
  <div />
</template>

<style scoped>
/* local styles only */
</style>
```

### Composition Rule

Use page-level components to orchestrate data and child components to render focused sections.

Examples inspired by `MainPagePrototype.qml`:

| Page concern | Suggested web component |
|---|---|
| Top status bar | `TopStatusBar.vue` |
| Left navigation | `AppSidebar.vue` |
| Main result panel | `DetectionResultPanel.vue` |
| Bottom stats block | `DashboardStatsBar.vue` |

---

## Props Conventions

| Rule | Reason |
|---|---|
| Define props explicitly with TypeScript types | Prevents hidden contracts |
| Pass data down, emit events up | Keeps ownership clear |
| Keep props focused on one concern | Avoids giant option bags |
| Use domain names, not UI-only placeholders | Improves readability across layers |

### Good examples to follow conceptually

The QML prototype groups state by intent:

- `currentStateText`
- `dxPixels`
- `surfaceResultText`
- `backlightResultText`
- `finalResultText`

This is a good signal that props should be named by domain meaning, not by vague labels such as `value1`, `info`, or `data`.

---

## Styling Patterns

Current prototype evidence uses inline colors and layout sizing because it is a standalone mock.

Production web UI should follow these rules:

| Rule | Notes |
|---|---|
| Shared tokens go in a central theme or style layer | Avoid copying hex colors everywhere |
| Keep page shell layout separate from feature-specific styling | Prevents layout duplication |
| Use component-local styles for one-off presentation only | Shared styles belong in tokens or common classes |

Prototype-only patterns that should not survive into production:

- repeated raw hex colors across many files
- mixed layout and domain logic in the same long component file

---

## Accessibility

| Requirement | Expected behavior |
|---|---|
| Interactive elements | Use real buttons, links, inputs, and labels |
| Status displays | Do not rely on color alone; include text labels |
| Tables and lists | Keep keyboard access and readable empty states |
| Images | Provide meaningful alt text when used in the web app |

The QML prototype already pairs status colors with text labels such as `在线`, `离线`, and `常亮`. Keep that idea in the web UI.

---

## Examples

| Repository evidence | What it shows |
|---|---|
| `MainPagePrototype.qml` | One root page with clearly named state groups and sectioned layout |
| `MainPagePrototype.qml` | Helper functions (`statusColor`, `beatText`) stay small and UI-focused |
| `工业缺陷检测系统完整方案.md` | The web app is page-driven, so components should support route-level composition |

---

## Common Mistakes

| Mistake | Why it is a problem |
|---|---|
| Building one huge page component with all panels inline | Hard to test and reuse |
| Fetching backend data inside tiny presentational components | Couples rendering to transport logic |
| Hard-coding repeated colors and labels in many files | Drifts quickly |
| Reusing embedded-device UI assumptions directly in the web dashboard | The web app has different interaction needs |
