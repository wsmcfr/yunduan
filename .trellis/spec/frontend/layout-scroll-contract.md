# Layout Scroll Contract

> Executable contract for the cloud console shell, route pages, and dense workspaces.

---

## Scenario: One-Screen Shell With Internal Route Scrolling

### 1. Scope / Trigger

Use this contract before changing any of these files or patterns:

- `src/components/layout/AppShell.vue`
- `src/components/layout/AppSidebar.vue`
- `src/styles/base.css`
- route root elements such as `.dashboard-page`, `.records-page`, `.parts-page`, `.gallery-page`, `.settings-page`, or `.stats-page`
- dense workspace containers such as `.dashboard-workspace-stage`, `.stats-page__workspace-stage`, or `.stats-gallery__workspace-stage`
- any CSS using `height`, `min-height`, `max-height`, `overflow`, `grid-template-rows`, `height="100%"`, or table `height="100%"`

Why:

- the product should feel like a console fixed to one viewport, not like a long marketing page
- browser-level vertical scrolling makes the sidebar, header, and shell feel unstable
- forcing inner modules into fixed heights can crop content, create double scrollbars, or make sections overlap

### 2. Signatures

The shell contract is expressed through these selectors:

| Selector | Owner | Contract |
|---|---|---|
| `body` | `src/styles/base.css` | must not vertically scroll in the authenticated shell |
| `.shell` | `AppShell.vue` | fixed to one viewport with `height: 100dvh` and `overflow: hidden` |
| `.shell__grid` | `AppShell.vue` | fills the shell interior and has `min-height: 0` |
| `.shell__content` | `AppShell.vue` | flex column with `min-width: 0` and `min-height: 0` |
| `.shell__page` | `AppShell.vue` | right-side panel viewport with `display: flex`, `min-height: 0`, and `overflow: hidden` |
| `.page-grid` | route page root | the only default business-page vertical scroll container |
| `.sidebar` | `AppSidebar.vue` | may scroll internally if the viewport is short |

The browser verification probe is:

```ts
const metrics = await page.evaluate(() => {
  const pageGrid = document.querySelector(".page-grid") as HTMLElement | null;

  return {
    bodyScroll: document.documentElement.scrollHeight,
    bodyClient: document.documentElement.clientHeight,
    bodyOverflow: getComputedStyle(document.body).overflow,
    pageOverflow: pageGrid ? getComputedStyle(pageGrid).overflowY : "",
    pageScroll: pageGrid?.scrollHeight ?? 0,
    pageClient: pageGrid?.clientHeight ?? 0,
  };
});
```

### 3. Contracts

#### Shell Contract

- `body` uses `overflow: hidden` for authenticated pages.
- `.shell` uses `height: 100dvh`, `min-height: 100dvh`, and `overflow: hidden`.
- `.shell__grid` uses `height: calc(100dvh - <shell vertical padding>)` and `min-height: 0`.
- `.shell__content` and `.shell__page` must include `min-height: 0`; otherwise the child scroll container cannot shrink.
- `.shell__page` must use `overflow: hidden` so the right panel frame never leaks into browser scrolling.
- `.page-grid` must use `overflow-y: auto`, `overflow-x: hidden`, `min-height: 0`, `max-height: 100%`, and `flex: 1`.

#### Route Page Contract

- Route root classes should use `align-content: start`; they should not set `height: 100%` just to fill the shell.
- Long route content scrolls through `.page-grid`, not through `body`.
- Management pages such as records, parts, devices, and settings should let sections and tables use natural height unless a smaller nested pane has a clear reason to scroll.
- Avoid `ElTable height="100%"` at route level unless its parent has a deliberately bounded height and the page has a tested internal scroll path.

#### Dense Workspace Contract

- Pager buttons may switch dense sections, but desktop pages must not rely on fixed stage-height tokens to make the whole product feel like one page.
- Avoid fixed variables such as `--dashboard-workspace-stage-height` or `--stats-gallery-workspace-stage-height` unless a specific nested widget must keep a stable viewport.
- If a nested widget scrolls internally, its parent must still fit inside `.page-grid`; never create a nested fixed-height stage that extends below `.shell__page`.
- Active workspace pages should normally use natural height and let `.page-grid` own vertical scrolling.
- Print styles may still force all hidden workspace pages visible with page breaks.

### 4. Validation & Error Matrix

| Symptom | Likely Cause | Required Fix |
|---|---|---|
| Browser has a right-side page scrollbar | `body` or `.shell` is allowing natural document height | restore shell viewport lock and move scroll to `.page-grid` |
| Sidebar/header move while reading records | outer document scrolls | set `body { overflow: hidden; }`, `.shell { height: 100dvh; overflow: hidden; }` |
| Detail page bottom is unreachable | `.page-grid` or `.shell__page` has hidden overflow without an internal scroll path | keep `.shell__page` hidden, but make `.page-grid` `overflow-y: auto` |
| Gallery pager overlaps category details | fixed stage height is smaller than content | remove fixed stage height and let `.page-grid` scroll |
| Table area is tiny or clipped | route table uses `height="100%"` inside a compressed grid row | remove table `height="100%"` or define a tested bounded table wrapper |
| Two vertical scrollbars appear in the content pane | both `.page-grid` and a full-page child stage scroll | keep one full-page scroll owner; nested scroll only for small widgets |

### 5. Good / Base / Bad Cases

| Case | Expected Result |
|---|---|
| Good: `/records` at `1920x1028` with 10 rows | document height equals viewport height; `.page-grid` scrolls if the list is taller than the panel |
| Good: `/records/3` detail page | evidence, context, review, and file sections are reachable through the right panel scroll |
| Good: `/statistics/gallery` | gallery sections do not overlap; the right panel scrolls when the gallery is taller than one screen |
| Good: `/dashboard` third workspace page | findings section is reachable through the right panel scroll |
| Base: `/parts` with little data | `.page-grid` may not need actual scrolling, but it remains the configured scroll container |
| Bad: `documentElement.scrollHeight > documentElement.clientHeight` | the outer browser page is scrolling and violates the console shell contract |
| Bad: active workspace page bottom is below `.shell__page` while `.page-grid` is not scrollable | content will be clipped |

### 6. Tests Required

Run normal frontend verification:

```bash
npm run test
npm run build
```

Run a browser layout probe for any change touching this contract:

```ts
expect(metrics.bodyScroll).toBe(metrics.bodyClient);
expect(metrics.bodyOverflow).toBe("hidden");
expect(metrics.pageOverflow).toBe("auto");
```

Check at least these routes at a desktop viewport around `1920x1028`:

- `/parts`
- `/records`
- `/records/3`
- `/statistics/gallery`
- `/dashboard`, including the last workspace page

Manual QA points:

- the browser window itself should not vertically scroll
- the right content panel should scroll when content is long
- the sidebar should stay inside the shell and may scroll internally only when the viewport is too short
- no page should depend on browser zoom to reveal hidden content

### 7. Wrong vs Correct

#### Wrong: Natural Document Scroll

```css
body {
  overflow-y: auto;
}

.shell {
  min-height: 100vh;
}

.shell__page {
  overflow: visible;
}
```

Why wrong:

- long records and detail pages make the whole browser scroll
- the product feels like a long page instead of a fixed console
- sidebar and content no longer share a stable shell viewport

#### Correct: Fixed Shell, Internal Route Scroll

```css
body {
  overflow: hidden;
}

.shell {
  height: 100dvh;
  min-height: 100dvh;
  overflow: hidden;
}

.shell__grid,
.shell__content,
.shell__page {
  min-height: 0;
}

.shell__page {
  display: flex;
  overflow: hidden;
}

.shell__page :deep(.page-grid) {
  flex: 1;
  max-height: 100%;
  overflow-x: hidden;
  overflow-y: auto;
}
```

#### Wrong: Fixed Stage That Outgrows The Shell

```css
.dashboard-page {
  --dashboard-workspace-stage-height: clamp(360px, calc(100vh - 500px), 620px);
  height: 100%;
  overflow-y: auto;
}

.dashboard-workspace-page {
  height: var(--dashboard-workspace-stage-height);
  overflow-y: auto;
}
```

Why wrong:

- the page root and the active workspace both scroll, creating nested full-page scroll behavior
- stage height calculations drift when header, filter, or pager height changes
- bottom sections can be clipped or appear to overlap under production viewport sizes

#### Correct: Natural Workspace Inside The Route Scroll Container

```css
.dashboard-page {
  align-content: start;
}

.dashboard-workspace-page {
  display: none;
  align-content: start;
}

.dashboard-workspace-page--active {
  display: grid;
}
```

Why correct:

- one full-page scroll owner remains `.page-grid`
- dense workspace pages can still be switched with buttons
- content height can grow without being clipped by a stale stage-height formula

---

## Incident Memory: April 30, 2026

The shell was changed twice while debugging production screenshots:

1. First attempt: fixed the overlap by allowing natural document scroll.
2. User feedback: this violated the product feel because the whole browser became a long page.
3. Final fix: lock `body` and `.shell` to one viewport, then make `.page-grid` the internal scroll container.

Do not repeat the first attempt. The correct invariant is:

```text
outer browser scroll = never
right content panel scroll = yes, when route content is long
nested full-page stage scroll = avoid
```
