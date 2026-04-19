# Directory Structure

> How the cloud web frontend should be organized.

---

## Overview

The chosen web stack is `Vue 3 + Vite + Element Plus`. No real web app directory exists yet, so this file defines the structure that should be created when frontend scaffolding starts.

Current evidence:

- `工业缺陷检测系统完整方案.md` already defines page routes such as `/login`, `/dashboard`, `/records`, `/record/:id`, `/parts`, `/devices`, `/statistics`, and `/settings`.
- `MainPagePrototype.qml` demonstrates a page split into top status, navigation, main content, result panel, and stats panel.

---

## Directory Layout

```text
frontend/
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── router/
│   │   └── index.ts
│   ├── pages/
│   │   ├── LoginPage.vue
│   │   ├── DashboardPage.vue
│   │   ├── RecordsPage.vue
│   │   ├── RecordDetailPage.vue
│   │   ├── PartsPage.vue
│   │   ├── DevicesPage.vue
│   │   ├── StatisticsPage.vue
│   │   └── SettingsPage.vue
│   ├── features/
│   │   ├── records/
│   │   ├── parts/
│   │   ├── devices/
│   │   └── review/
│   ├── components/
│   │   ├── common/
│   │   ├── layout/
│   │   └── charts/
│   ├── composables/
│   ├── services/
│   │   ├── api/
│   │   └── mappers/
│   ├── stores/
│   ├── types/
│   ├── styles/
│   └── assets/
├── public/
└── tests/
```

If embedded-device UI code remains in the repo, keep it outside the web app, for example:

```text
device-ui/
└── MainPagePrototype.qml
```

Do not mix QML files directly into the web frontend tree.

---

## Module Organization

| Area | Responsibility |
|---|---|
| `pages/` | Route-level containers only |
| `features/` | Domain-specific components, composables, and helpers |
| `components/common/` | Generic reusable UI components |
| `components/layout/` | Navbar, sidebar, page shell, header blocks |
| `services/api/` | HTTP clients and request wrappers |
| `services/mappers/` | DTO-to-view-model transformations |
| `stores/` | Global state only |
| `types/` | Shared types, DTOs, and feature model types |

### Feature Rule

Prefer feature-based grouping over giant global folders. For example:

- detection history logic belongs under `features/records/`
- manual review tools belong under `features/review/`
- device health panels belong under `features/devices/`

---

## Naming Conventions

| Item | Convention |
|---|---|
| Vue components | `PascalCase.vue` |
| Page components | `SomethingPage.vue` |
| Composables | `useSomething.ts` |
| Feature folders | `kebab-case` or `snake_case`, stay consistent within the app |
| Shared utility files | `camelCase.ts` or `snake_case.ts`, but use one style consistently |
| Route names | short resource-oriented names such as `records`, `record-detail`, `devices` |

---

## Forbidden Patterns

| Pattern | Why it is forbidden |
|---|---|
| Keeping the web UI and embedded QML UI in one undifferentiated `src/` tree | Different frameworks, responsibilities, and runtimes |
| Dumping all page logic into `pages/` with no feature modules | Hard to reuse and maintain |
| Storing API mappers in component files | Hides cross-layer contract logic |
| Treating the QML prototype as the final web structure | It is evidence, not the final app skeleton |

---

## Examples

| Repository evidence | What it shows |
|---|---|
| `工业缺陷检测系统完整方案.md` page route list | The app already has clear route-level modules |
| `MainPagePrototype.qml` | UI is already mentally split into status bar, nav, content, result panel, and stats panel |
| `STM32MP157DAA1工业缺陷检测系统综合方案.md` | Cloud frontend is separate from device-facing UI concerns |
