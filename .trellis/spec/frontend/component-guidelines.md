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

### Convention: Element Plus Dark Pagination Readability

Element Plus pagination controls must stay readable in the authenticated dark console, including unselected page numbers and the page-size selector.

Implementation contract:

- keep shared Element Plus pagination theme overrides in `src/styles/base.css`, not inside one route page
- override the background pagination mode because Element Plus async chunk styles can arrive after page CSS
- cover normal, hover, active, and disabled states for `.el-pagination.is-background`
- use enough contrast for unselected page buttons; dark text on dark page-number backgrounds is forbidden
- include the page-size selector in records-style tables when users need to scan more or fewer rows per page
- if a page uses `layout="total, sizes, prev, pager, next, jumper"`, verify the `sizes` dropdown text and selected value remain readable in the dark theme
- when chunk CSS wins unexpectedly, use narrowly scoped `!important` rules in `base.css` for Element Plus library overrides instead of scattering higher-specificity selectors across route styles

Example:

```css
.el-pagination.is-background .el-pager li:not(.is-active) {
  color: var(--text-primary) !important;
  background-color: rgba(15, 23, 42, 0.92) !important;
  border: 1px solid var(--border-subtle) !important;
}

.el-pagination.is-background .el-pager li.is-active {
  color: #ffffff !important;
  background-color: var(--color-primary) !important;
}
```

Review points:

- open every page that uses Element Plus pagination, not just the page that triggered the complaint
- verify unselected page numbers, active page numbers, disabled arrows, page-size select text, and jumper input
- verify at least one authenticated table page with enough data to show multiple pages
- inspect the built Vite output or run a browser probe because Element Plus pagination CSS is emitted as an async chunk

Why:

- pagination often sits at the bottom of dense data pages, so low contrast is easy to miss in a quick top-of-page check
- route-local fixes can leave other paginated pages unreadable
- async component-library CSS can override ordinary page styles after navigation, so the shared base layer must own these dark-theme corrections

### Convention: Radio Button Values

When using `ElRadioButton`, bind the selected value through `value`, not through `label`.

Why:

- recent Element Plus versions warn when `label` is used as the selection value
- `label` should be treated as display content, while `value` is the stable form contract

### Convention: Evidence Preview Scaling

Sample-gallery cards and review workspaces must treat inspection images as evidence, not as decorative hero banners.

Implementation contract:

- on desktop, wide evidence cards should split into a constrained preview column plus a metadata/action column
- the preview stage may keep a stable ratio such as `4 / 3`, but it must also cap visible size with a `max-height` clamp
- evidence images should prefer `max-width: 100%`, `max-height: 100%`, and `object-fit: contain`
- do not use `object-fit: cover` for part-inspection previews when users need to see the full contour, edge, or hole position
- collapse back to a single-column layout on narrow screens so metadata is not squeezed

Example:

```vue
<style scoped>
.sample-card {
  display: grid;
  grid-template-columns: minmax(260px, clamp(280px, 32vw, 420px)) minmax(0, 1fr);
}

.sample-card__preview {
  display: flex;
  align-items: center;
  justify-content: center;
  aspect-ratio: 4 / 3;
  max-height: clamp(220px, 30vw, 340px);
}

.sample-card__preview img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

@media (max-width: 900px) {
  .sample-card {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
```

Why:

- full-width `cover` images make a single part photo dominate the whole card on large screens
- browser zoom changes expose the problem quickly: the page shrinks, but the evidence image still feels oversized
- `contain` preserves the whole part shape, which is more important than edge-to-edge filling for review and audit pages

### Convention: Visual Balance and Context-Specific Aesthetics

Production pages must optimize for human visual comfort, not only for data density.

Implementation contract:

- keep a clear visual axis in each section; cards in the same row should align by top edge and usually by bottom action area as well
- avoid accidental asymmetry caused by one card growing with text while neighboring cards keep short content; use equal-height cards, clamped text, or separated header/body/footer regions when the cards are meant to look like one set
- do not stretch a sparse summary column to the full height of a dense detail pane unless that extra height is intentionally filled with overview metrics, helper copy, or secondary navigation
- pick the aesthetic language by scenario instead of forcing one layout style everywhere:
  - dashboards may be more expressive and visual
  - settings and admin pages should prioritize order, symmetry, and scan efficiency
  - review workspaces should prioritize evidence visibility and action clarity
- reduce dead whitespace that looks like a layout bug; if one panel has much less content than its neighbor, prefer natural height plus a small overview block instead of a large empty slab
- check layout at common zoom and viewport states before shipping: `100%`, `125%`, `150%`, and a narrow breakpoint around `900px`

Example:

```vue
<style scoped>
.gateway-preset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  grid-auto-rows: 1fr;
}

.gateway-preset-card {
  display: flex;
  flex-direction: column;
}

.gateway-preset-card__body {
  flex: 1;
}

.gateway-preset-card__footer {
  margin-top: auto;
}

.gateway-workspace {
  display: grid;
  grid-template-columns: minmax(280px, 340px) minmax(0, 1fr);
  align-items: start;
}

.gateway-list {
  align-content: start;
}
</style>
```

Why:

- symmetry makes repeated management cards feel intentional rather than patched together
- context-specific density prevents admin screens from looking like dashboards and prevents dashboards from feeling lifeless
- natural-height side panels avoid the common “large empty column” defect that users read as broken design instead of deliberate whitespace

### Convention: Avoid Double-Shell Wrappers In Dense Workspaces

Dense workspaces such as the statistics AI stage must not stack a shared global shell on top of a page-specific root wrapper when the root already manages its own spacing and sub-block composition.

Why:

- `.app-panel` in `src/styles/base.css` injects a background, border, radius, shadow, and blur shell intended for standalone cards
- if a dense workspace root also wraps multiple inner blocks such as summary, analysis, and conversation, the extra shell makes the whole area look like one oversized frame
- users then perceive unrelated regions as being “boxed together”, especially when streaming text causes the inner blocks to grow

Implementation contract:

- use `.app-panel` for atomic cards such as filters, rankings, or standalone summary panels
- if the workspace root already has a dedicated class such as `stats-ai-panel`, let that root own `padding`, `gap`, and height behavior itself
- do not combine `.app-panel` with dense workspace roots that already contain multiple visually independent regions
- keep the visual grouping at the inner block level, not by adding one more global shell around everything
- when removing the shared shell, verify the root still keeps deliberate spacing through its own local layout rules

Wrong:

```vue
<section class="app-panel stats-ai-panel">
  <div class="stats-ai-panel__result">...</div>
  <div class="stats-ai-panel__analysis-block">...</div>
  <div class="stats-ai-panel__conversation">...</div>
</section>
```

Correct:

```vue
<section class="stats-ai-panel">
  <div class="stats-ai-panel__result">...</div>
  <div class="stats-ai-panel__analysis-block">...</div>
  <div class="stats-ai-panel__conversation">...</div>
</section>
```

Review points:

- at `100%`, `125%`, and `150%` zoom, confirm there is no extra border/shadow wrapping both the analysis area and the follow-up conversation area together
- confirm the workspace still has enough `padding` and `gap` after removing the shared shell
- confirm standalone sections that truly need a single card shell still keep `.app-panel`; this rule is for dense multi-region roots, not for every panel

### Convention: One-Screen Shell And Internal Page Scroll

The authenticated console must occupy one browser viewport. The outer browser page must not vertically scroll; long route content must scroll inside the right content panel.

Implementation contract:

- read [Layout Scroll Contract](./layout-scroll-contract.md) before touching shell, page root, workspace stage, table height, or any `height` / `overflow` CSS
- keep `body` and `.shell` locked to one viewport
- make `.shell__page > .page-grid` the default business-page scroll owner
- keep route roots such as `.records-page`, `.parts-page`, `.gallery-page`, and `.dashboard-page` naturally sized with `align-content: start`
- do not add `height: 100%` or `overflow: hidden` to route roots unless the `layout-scroll-contract.md` browser probe still proves the route scrolls internally
- do not use fixed stage-height tokens such as `--dashboard-workspace-stage-height` as the default way to prevent a long page
- keep workspace page switching as state and visibility only; the active workspace page should usually grow naturally inside `.page-grid`
- use nested `overflow-y: auto` only for smaller widgets such as chat histories, image lists, or intentionally bounded panes

Example:

```vue
<template>
  <div class="page-grid records-page">
    <PageHeader ... />
    <section class="app-panel records-toolbar">...</section>
    <section class="app-panel records-table">...</section>
  </div>
</template>

<style scoped>
.records-page {
  align-content: start;
}

.records-table {
  align-content: start;
}
</style>
```

Wrong:

```vue
<ElTable :data="items" height="100%" />
```

```css
.records-page {
  height: 100%;
  grid-template-rows: auto auto minmax(0, 1fr);
  overflow: hidden;
}

.dashboard-workspace-page {
  max-height: var(--dashboard-workspace-stage-height);
  overflow-y: auto;
}
```

Why wrong:

- the route root becomes another full-page scroll or clipping owner
- fixed stage height drifts when headers, filters, or pagers change
- screenshots may show overlapping blocks or unreachable bottom content
- switching to `body { overflow-y: auto; }` fixes clipping but violates the console product feel

Correct:

```css
body {
  overflow: hidden;
}

.shell {
  height: 100dvh;
  overflow: hidden;
}

.shell__page {
  display: flex;
  min-height: 0;
  overflow: hidden;
}

.shell__page :deep(.page-grid) {
  flex: 1;
  max-height: 100%;
  overflow-x: hidden;
  overflow-y: auto;
}

.dashboard-workspace-page {
  display: none;
  align-content: start;
}

.dashboard-workspace-page--active {
  display: grid;
}
```

Review points:

- at `1920x1028`, verify `document.documentElement.scrollHeight === document.documentElement.clientHeight`
- verify `getComputedStyle(document.body).overflow === "hidden"`
- verify `getComputedStyle(document.querySelector(".page-grid")).overflowY === "auto"`
- verify `/records`, `/records/3`, `/statistics/gallery`, and the last dashboard workspace page are reachable through the right panel scroll
- verify there is no full-page nested scroll owner competing with `.page-grid`

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
| Letting one inspection image fill the full card width with `object-fit: cover` | Makes evidence previews look oversized and can crop the exact defect contour users need to inspect |
| Adding route-level fixed stage heights to avoid browser scrolling | The app may stop being long, but sections can overlap or become unreachable; keep `.page-grid` as the route scroll owner instead |
