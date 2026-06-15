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
- when two same-level panels are placed side by side for comparison, give their outer containers the same explicit height or shared size token; do not let one panel use a different fixed height because its current content looks taller
- avoid accidental asymmetry caused by one card growing with text while neighboring cards keep short content; use equal-height cards, clamped text, or separated header/body/footer regions when the cards are meant to look like one set
- pagination, long text, generated images, COS paths, and metadata must be constrained inside the panel body/footer; switching pages must never change the outer panel bounding box
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

.record-detail-pair {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.record-detail-panel,
.record-detail-context-panel {
  /* Same-row comparison panels share one outer-frame contract. */
  height: 560px;
  grid-template-rows: auto minmax(0, 1fr);
  overflow: hidden;
}

.record-detail-panel__body {
  min-height: 0;
  overflow: hidden;
}
</style>
```

Wrong:

```css
.record-detail-panel {
  height: 640px;
}

.record-detail-context-panel {
  height: 560px;
}
```

Why wrong:

- the two panels may both be individually bounded, but they no longer align as a pair
- users read the mismatched bottom edge as a broken layout, especially in review screens where evidence and context are compared side by side
- pagination can look like it is changing the layout even when only the inner content changed

Why:

- symmetry makes repeated management cards feel intentional rather than patched together
- context-specific density prevents admin screens from looking like dashboards and prevents dashboards from feeling lifeless
- natural-height side panels avoid the common “large empty column” defect that users read as broken design instead of deliberate whitespace
- fixed comparison panels must be fixed as a set, not as isolated boxes; the visual contract is the row alignment, not only each panel's internal overflow behavior

## Scenario: Public Auth Page Visual Balance And Element Plus Tabs Flow

Public auth pages such as `LoginPage.vue` are first-screen product surfaces. They must read as a cloud inspection system entry, not as a contest poster, temporary helper page, or decorative empty frame.

### 1. Scope / Trigger

| Trigger | Required response |
|---|---|
| Changing login, registration, forgot-password, or public auth copy | Re-check the public auth page copy against production cloud inspection terminology. |
| Changing `.login-page` desktop layout | Preserve two equal desktop panels that fill the first viewport. |
| Changing Element Plus tabs inside the auth card | Verify tab content is not compressed by a parent grid row and does not overlap helper sections below. |
| Adding decorative layers to the hero panel | Verify they do not look like stray background boxes behind process cards. |
| Adding or removing filler modules | Keep empty areas filled with useful system context, not ornamental space. |

### 2. Signatures

| Selector / source contract | Required signature |
|---|---|
| `.login-page` | Desktop grid uses `grid-template-columns: repeat(2, minmax(0, 1fr))`. |
| `.login-page__hero` and `.login-page__form-card` | Both stretch to the same viewport-derived height, for example `height: calc(100dvh - 56px)` and `min-height: calc(100dvh - 56px)`. |
| `.login-page__title` | Title text is `云端检测系统`; desktop size is capped with `font-size: clamp(32px, 3.2vw, 48px)`. |
| `.login-page__process-strip` | Four-step business flow stays visible in the left panel. |
| `.login-page__form-card` | Uses `display: flex` and `flex-direction: column`; do not use a compressed parent grid for the full auth card. |
| `.login-page__tabs :deep(.el-tabs__content)` | Uses `overflow: visible` so Element Plus tab panes keep natural height. |
| `.login-page__login-grid` | Desktop login form uses `grid-template-columns: repeat(2, minmax(0, 1fr))`; the submit button spans `grid-column: 1 / -1`. |
| `.login-page__mode-switch :deep(.el-radio-group)` | Registration mode choices fill the card width in two equal columns. |
| `.login-page__auth-paths` | Explains account paths with business language, not security-feature marketing. |
| `.login-page__workspace-preview` | Uses `flex: 1 0 auto` or equivalent to absorb right-panel remaining height with useful workspace context. |
| `.login-page__hero::before` | Forbidden for bordered decorative frames behind process cards; use only non-box-like ambience such as `.login-page__hero::after` when needed. |

### 3. Contracts

| Contract | Required behavior |
|---|---|
| Product naming | Public title is `云端检测系统`; avoid `检测云控台` unless explicitly requested, and never use contest names on production pages. |
| Dashboard wording | Dashboard page title uses operating-console semantics such as `运营态势总览`, not `比赛项目总览` or placeholder-copy language. |
| Desktop panel geometry | Left and right panels are visually equal-width, equal-height, and fill the first viewport. |
| Left-panel content | The hero panel includes workflow, run snapshot, coverage, and capability blocks so bottom/top gaps carry useful inspection-system meaning. |
| Right-panel content | Login/register controls are sized for the half-screen card, and remaining height is filled by account paths and workspace preview. |
| Element Plus tab flow | Tabs participate in normal document flow inside the form card. Helper sections below tabs must move down naturally instead of covering forms. |
| Decorative layers | A pseudo-element must not create a visible bordered rectangle behind cards; users read that as a broken layout frame. |
| Short desktop height | Around `1280x720` and `1360x768`, keep the two-column layout but tighten copy, cards, and secondary text so the left panel is not clipped. |

### 4. Validation & Error Matrix

| Check | Failure signal | Required fix |
|---|---|---|
| Public copy scan | Mentions `比赛`, `第九届`, `占位`, or temporary helper framing | Replace with cloud inspection operations language. |
| Panel equality | Left and right panel widths or heights differ on desktop | Restore equal `1fr` columns and shared viewport-derived card height. |
| Title scale | `云端检测系统` looks like a poster headline or exceeds the intended cap | Restore the title clamp and short-height override. |
| Tabs layout | `.login-page__auth-paths` or `.login-page__workspace-preview` overlaps form fields | Remove compressed grid rows from `.login-page__form-card`; keep tab content `overflow: visible`. |
| Empty slabs | A panel has large unused space below sparse text | Add or rebalance business modules such as snapshots, account paths, or workspace preview. |
| Decorative frame | A bordered pseudo-element appears behind the fourth process card or hero content | Remove `.login-page__hero::before` and avoid box-like background frames. |
| Short viewport | Left capability cards or bottom content are cut off at `1280x720` | Add short-height media rules that reduce density without changing product copy. |

### 5. Good / Base / Bad Cases

| Case | Expected result |
|---|---|
| Good | `1920x1028`, `1360x768`, and `1280x720` show two equal panels, no overlap, no body scroll, title capped, and business modules filling both sides. |
| Base | Narrow layouts collapse to a single column with readable auth flow and no clipped form controls. |
| Bad | A right-side form card uses only a narrow column inside a half-screen panel, leaving an empty box-like area. |
| Bad | Left hero has a big title plus sparse copy and a decorative rectangle behind process cards. |
| Bad | A parent grid uses `1fr` rows around `ElTabs`, causing tab content to be squeezed and lower sections to cover the form. |

### 6. Tests Required

| Test type | Assertion points |
|---|---|
| Source contract test | Assert `DashboardPage.vue` title is `运营态势总览` and does not contain contest or placeholder wording. |
| Source contract test | Assert `LoginPage.vue` title is `云端检测系统`, title clamp is present, and contest copy is absent. |
| Source contract test | Assert `.login-page` equal columns, shared viewport height, and stretched panels are present. |
| Source contract test | Assert `.login-page__form-card` is flex column and `.login-page__tabs :deep(.el-tabs__content)` uses `overflow: visible`. |
| Source contract test | Assert login grid, registration mode grid, process strip, snapshot, coverage, account paths, and workspace preview selectors exist. |
| Source contract test | Assert `.login-page__hero::before` is absent and `.login-page__hero::after` may remain only as non-box ambience. |
| Browser visual probe | At `1920x1028`, `1360x768`, and `1280x720`, assert left/right panel bounding boxes are equal, no key sections overlap, and body overflow remains locked. |

### 7. Wrong vs Correct

#### Wrong

```vue
<style scoped>
.login-page {
  /* 错误：右侧固定宽度会让两块主面板大小不一致。 */
  grid-template-columns: minmax(0, 1fr) minmax(380px, 560px);
}

.login-page__form-card {
  /* 错误：父级网格行压缩 Element Plus tabs，容易让下方模块覆盖表单。 */
  display: grid;
  grid-template-rows: auto auto auto minmax(max-content, 1fr);
}

.login-page__tabs :deep(.el-tabs__content) {
  /* 错误：裁切 tab 内容会隐藏表单高度，后续模块无法正确避让。 */
  overflow: hidden;
}

.login-page__hero::before {
  /* 错误：边框型伪元素会被误读成多余背景框。 */
  content: "";
  position: absolute;
  border: 1px solid rgba(148, 163, 184, 0.24);
}
</style>
```

#### Correct

```vue
<style scoped>
.login-page {
  /* 正确：桌面端左右均分，两个主面板像同一个入口工作台。 */
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.login-page__hero,
.login-page__form-card {
  /* 正确：左右主面板使用相同的首屏高度契约。 */
  min-height: calc(100dvh - 56px);
  height: calc(100dvh - 56px);
  justify-self: stretch;
}

.login-page__form-card {
  /* 正确：认证卡按自然流纵向排列，避免压缩 Element Plus tabs。 */
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.login-page__tabs :deep(.el-tabs__content) {
  /* 正确：tab 面板自然撑开，账号路径和工作区预览跟随下移。 */
  overflow: visible;
}

.login-page__workspace-preview {
  /* 正确：用工作区信息吸收剩余高度，而不是留下空白。 */
  flex: 1 0 auto;
}
</style>
```

### Convention: Compact Management Table Row Actions

Management tables such as `RecordsPage`, `PartsPage`, and `DevicesPage` should render row actions as a compact horizontal action group, not as loose Element Plus text buttons stacked inside a narrow column.

#### Scope / Trigger

- Trigger: any change to an `ElTableColumn label="操作"` in management-style pages.
- Applies to list pages that combine dense data scanning with quick row commands, including records, parts, devices, users, companies, gateway/model lists, and similar admin tables.
- Applies when adding actions such as edit, delete, review, detail, enable/disable, sample/gallery, approve/reject, reset, or status toggles.

#### Signatures

| Selector / Attribute | Required Contract |
|---|---|
| `ElTableColumn label="操作"` | Use a natural `min-width` large enough for one row of actions and `align="center"` when the column is action-only. |
| `.table-actions` | Flex container for row action buttons. Desktop default is centered, one-line, and gap-controlled. |
| `.table-action-button` | Local class applied to every row action `ElButton` in the column. |
| `.table-actions :deep(.el-button + .el-button)` | Must reset Element Plus adjacent-button margin so the group spacing is predictable. |

#### Contracts

| Contract | Required Behavior |
|---|---|
| Desktop row actions | Keep short labels in one horizontal row: examples are `详情`, `复核`, `删除`, `编辑`, `样本`, `停用`. |
| Button sizing | Use a low-height pill style, typically `height: 28px`, `min-width: 42px`, and horizontal padding around `10px`. |
| Spacing owner | Use `gap` on `.table-actions`; do not rely on Element Plus default `.el-button + .el-button` margin. |
| Column sizing | Choose a `min-width` that fits the expected action count: two short actions usually need about `156px`; three short actions usually need about `204px`. |
| Destructive actions | Keep semantic button type such as `type="danger"` while using the same compact visual structure. |
| Narrow layouts | If a management table truly cannot fit, prefer table-level horizontal overflow inside `.page-grid`; do not make the browser document scroll. |

Example:

```vue
<ElTableColumn label="操作" min-width="156" align="center">
  <template #default="{ row }">
    <div class="table-actions">
      <ElButton class="table-action-button" text type="primary" @click="openDetail(row.id)">
        详情
      </ElButton>
      <ElButton class="table-action-button" text type="danger" @click="deleteRow(row)">
        删除
      </ElButton>
    </div>
  </template>
</ElTableColumn>

<style scoped>
.table-actions {
  align-items: center;
  justify-content: center;
  flex-wrap: nowrap;
  gap: 6px;
  min-width: max-content;
}

.table-action-button {
  height: 28px;
  min-width: 42px;
  padding: 0 10px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.34);
  font-weight: 700;
}

.table-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
</style>
```

#### Validation & Error Matrix

| Symptom | Likely Cause | Required Fix |
|---|---|---|
| Actions appear as a tall vertical block | Column is too narrow, labels are too long, or `.table-actions` wraps | Shorten labels, increase `min-width`, and use `flex-wrap: nowrap` for desktop. |
| Button spacing looks uneven | Element Plus adjacent-button margin is mixing with flex gap | Add `.table-actions :deep(.el-button + .el-button) { margin-left: 0; }`. |
| Right side looks like a separate gray strip | `fixed="right"` creates a detached table layer in the dark console | Remove `fixed="right"` and let the table scroll naturally within the route panel. |
| Operation column dominates the table | Long button text such as `查看该类型样本` or `进入复核` is used in row actions | Use short labels such as `样本`, `复核`, or `详情`; longer explanation belongs in detail views or tooltips. |
| Mobile fix makes desktop worse | The same wrapping rule is used for all widths | Keep desktop one-line; only allow wrapping in a deliberate narrow breakpoint if the table design needs it. |

#### Good / Base / Bad Cases

| Case | Expected Result |
|---|---|
| Good: records table with `复核/详情` and `删除` | Both buttons are centered on one line and keep semantic colors. |
| Good: parts table with `样本`, `编辑`, `停用` | Three short buttons fit in one row without a tall action slab. |
| Base: non-admin records table | Only the visible action still uses `.table-action-button`, so the row height stays stable. |
| Bad: `fixed="right"` action column | The dark table shows a detached fixed area and breaks visual continuity. |
| Bad: raw Element Plus text buttons | Default margins and line height make row actions look loose or vertically stacked. |

#### Tests Required

- Add or update a page/source contract test for every management page that owns an operation column.
- Assert that the page source includes `table-action-button`.
- Assert that `.table-actions` uses `flex-wrap: nowrap;` for the desktop contract.
- Assert that `.table-actions :deep(.el-button + .el-button)` exists when scoped styles style Element Plus buttons locally.
- Assert management action columns do not reintroduce `fixed="right"` unless a separate visual probe proves it is acceptable in the authenticated dark shell.

Current example assertion points:

```ts
expect(source).toContain("table-action-button");
expect(source).toContain("flex-wrap: nowrap;");
expect(source).toContain(".table-actions :deep(.el-button + .el-button)");
expect(source).not.toContain('fixed="right"');
```

#### Wrong vs Correct

Wrong:

```vue
<ElTableColumn label="操作" min-width="146">
  <template #default="{ row }">
    <ElButton text type="primary">进入复核</ElButton>
    <ElButton text type="danger">删除</ElButton>
  </template>
</ElTableColumn>
```

Why wrong:

- raw text buttons inherit default spacing and can wrap or stack in narrow columns
- long labels increase the chance of a tall operation block
- the column has no explicit visual contract shared with other management pages

Correct:

```vue
<ElTableColumn label="操作" min-width="156" align="center">
  <template #default="{ row }">
    <div class="table-actions">
      <ElButton class="table-action-button" text type="primary">复核</ElButton>
      <ElButton class="table-action-button" text type="danger">删除</ElButton>
    </div>
  </template>
</ElTableColumn>
```

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

---

## Convention: MP157 Part Category And Detail Text Display

### Scope / Trigger

- Trigger: pages render MP157 part master data, record detail review text, board sync errors, model diagnostics, or long operator reasons.
- Affected pages include `PartsPage`, `RecordsPage`, `RecordDetailPage`, and statistics/gallery routes that display part filters or review detail.

### Signatures

| UI / Function | Required Behavior |
|---|---|
| `normalizePartCategoryLabel(category)` | Normalizes washer category aliases to `垫圈类` |
| `normalizePartDisplayName(partCode, rawName)` or equivalent mapper | Shows legacy `gasket` as `波形垫圈` |
| `groupPartsByCategory(parts)` | Groups by category while preserving each physical part row |
| Long text detail surface | Uses dialog/detail drawer/scroll area, not a clipped table cell only |

### Contracts

| Boundary | Contract |
|---|---|
| Category vs part | `垫圈类` is a grouping entry; it must not replace the actual part type. `波形垫圈`, `平垫圈`, and `弹性垫圈` remain separate rows. |
| Legacy model code | `gasket` and `gasket_good/gasket_bad` display as `波形垫圈`, never as `垫片`. |
| Outcome suffix | `_good` and `_bad` change the detection result, not the part name or category. |
| Long detail text | Cloud review reason, board sync error, model explanation, and raw output may be summarized in cards/tables, but the full value must be accessible in a scrollable detail view. |
| Gallery/filter navigation | Opening a category gallery should pass the normalized category (`垫圈类`) while opening a part gallery should pass the specific part name/code. |

### Validation & Error Matrix

| Check | Good Result | Bad Result |
|---|---|---|
| Parts category rail | One `垫圈类` category contains distinct wave/flat/spring washer rows | Category card is mistaken for one concrete part |
| Part display name | `gasket` row shows `波形垫圈` | `gasket` row shows `垫片` |
| Flat washer display | `washer` row shows `平垫圈` inside `垫圈类` | `washer` is merged into `gasket` |
| Long cloud reason | Table/card shows concise text and detail view shows full text | Text is permanently clipped with ellipsis and no detail path |

### Tests Required

- `partCategories.test.ts` must assert washer aliases normalize to `垫圈类`.
- Frontend mapper tests must assert backend category aliases do not leak as `垫片`.
- Page tests for `PartsPage` must assert selecting a category does not remove individual part rows.
- Record/detail UI tests should use a long cloud reason or board sync error and assert a full scrollable view is reachable.

### Wrong vs Correct

#### Wrong

```ts
const partName = dto.part_code === "gasket" ? "垫片" : dto.name;
```

#### Correct

```ts
const partName = normalizePartDisplayName(dto.part_code, dto.name);
```

#### Wrong

```vue
<ElTableColumn prop="cloud_reason" show-overflow-tooltip />
```

This may expose only a browser tooltip and is not enough for long production review text.

#### Correct

```vue
<ElTableColumn prop="cloud_reason" />
<ElButton @click="openReviewDetail(row)">查看详情</ElButton>
```

The detail dialog/drawer owns the scrollable full text.
