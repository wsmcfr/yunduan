# Component Guidelines

> How frontend components should be built in this project.

---

## Overview

The frontend now has a real component structure built around:

- `AppShell`, `AppHeader`, and `AppSidebar` for the shell
- `PageHeader` and `StatusTag` for shared presentation
- feature components such as `RecordCreateDialog` and `ManualReviewFormCard`
- route pages such as `RecordsPage`, `RecordDetailPage`, `PartsPage`, and `DevicesPage`

The core lesson still holds:

> a page should orchestrate data and workflow, while child components render one focused concern

---

## Component Structure

Preferred Vue SFC structure:

```vue
<script setup lang="ts">
// imports
// props and emits
// composables and local state
// derived state
// handlers
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

Current examples:

| Page concern | Current component |
|---|---|
| App shell | `AppShell.vue` |
| Top bar with route title, time, and user menu | `AppHeader.vue` |
| Left navigation | `AppSidebar.vue` |
| Shared page intro | `PageHeader.vue` |
| Manual review form | `ManualReviewFormCard.vue` |
| Result badges | `StatusTag.vue` |

---

## Props Conventions

| Rule | Reason |
|---|---|
| Define props explicitly with TypeScript types | Prevents hidden contracts |
| Pass data down, emit events up | Keeps ownership clear |
| Keep props focused on one concern | Avoids giant option bags |
| Use domain names, not vague names like `value1` or `data` | Improves readability across layers |

### Review Workspace Rule

Review actions belong to the record detail workspace, not to master-data pages.

Current contract:

- `RecordsPage` screens records and routes to detail
- `RecordDetailPage` owns evidence display, manual review, and AI review entry points
- `PartsPage` and `DevicesPage` manage master data only

---

## Styling Patterns

Production UI should follow these rules:

| Rule | Notes |
|---|---|
| Shared design tokens live in `src/styles/theme.css` | Avoid copying colors and radii into many files |
| Shared Element Plus dark-theme overrides live in `src/styles/base.css` | Keep the industrial dark look consistent |
| Page shell layout stays separate from feature-specific styling | Prevents layout duplication |
| Component-local styles are for one-off presentation only | Shared styling belongs in theme or base layers |

Current style coverage in `base.css` already includes:

- table
- pagination
- input and textarea
- select and date picker
- dialog and dropdown
- message and loading mask
- descriptions
- radio button group

### Convention: Live Shell Signals

The shell header clock must update automatically.

Why:

- users should see current local time without clicking refresh
- the refresh button is for page data, not for the clock itself

Implementation contract:

- call `setInterval(..., 1000)` on mount
- update the visible string every second
- clear the timer on unmount

### Convention: Element Plus On-Demand Import

Element Plus is auto-imported on demand through Vite plugins.

Build rule:

- do not force the whole `element-plus` library into one manual chunk
- keep manual chunk splitting limited to core vendor groups unless measurement proves otherwise

Why:

- a full `element-plus` chunk cancels the main benefit of on-demand component loading

### Convention: Radio Button Values

When using `ElRadioButton`, bind the selected value through `value`, not through `label`.

Why:

- recent Element Plus versions warn when `label` is used as the selection value
- `label` should be treated as display content, while `value` is the stable form contract

---

## Accessibility

| Requirement | Expected behavior |
|---|---|
| Interactive elements | Use real buttons, links, inputs, and labels |
| Status displays | Do not rely on color alone; include text labels |
| Tables and lists | Keep keyboard access and readable empty states |
| Images | Provide meaningful alt text when used in the web app |

The current app already pairs colors with text in `StatusTag` and alert content. Keep that pattern.

---

## Examples

| Repository evidence | What it shows |
|---|---|
| `AppHeader.vue` | The shell owns live clock and user actions, not feature pages |
| `RecordDetailPage.vue` + `ManualReviewFormCard.vue` | Detail page orchestrates workflow and child component emits a focused submit event |
| `theme.css` + `base.css` | Tokens and component-library overrides are centralized instead of repeated in feature files |

---

## Common Mistakes

| Mistake | Why it is a problem |
|---|---|
| Building one huge page component with all panels inline | Hard to test and reuse |
| Fetching backend data inside tiny presentational components | Couples rendering to transport logic |
| Hard-coding repeated colors and labels in many files | Drifts quickly |
| Making the header clock depend on a manual refresh click | Produces stale shell state |
| Using `label` as the selected radio value | Produces deprecation warnings and weak form contracts |
