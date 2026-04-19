# Hook Guidelines

> Composable patterns for the Vue frontend.

---

## Overview

This project uses Vue 3, so this file refers to composables even though the file name says "hook".

There are no composables in the repository yet. Guidance here is based on:

- planned route structure in `工业缺陷检测系统完整方案.md`
- grouped screen state in `MainPagePrototype.qml`

Composables should be introduced when logic is reused across pages or when page scripts become too stateful.

---

## Custom Hook Patterns

| Pattern | When to use it |
|---|---|
| Page orchestration composable | A page needs multiple queries, filters, and derived values |
| Feature-specific data composable | A feature needs reusable record, device, or part logic |
| UI-only composable | Reusable view behavior such as dialog state or table selection |

### Recommended split

| Concern | Where it belongs |
|---|---|
| API calls and normalization | composable plus API service |
| Pure formatting | shared utility |
| One-off button toggles | component local state |
| Cross-page filter persistence | composable or store, depending on scope |

---

## Data Fetching

The repository already implies these data domains:

- dashboard statistics
- detection records
- record detail and AI review
- parts catalog
- device status

Recommended composables for the first web scaffold:

| Composable | Reason |
|---|---|
| `useDashboardStats` | Dashboard cards and charts need shared loading and error handling |
| `useRecordsList` | Record list needs filtering, paging, and refresh |
| `useRecordDetail` | Detail page needs one record, review state, and audit actions |
| `useDevicesOverview` | Devices page needs polling or refreshable status summaries |

### Fetching rules

- Keep HTTP details in API modules, not directly in page templates.
- Normalize backend DTOs before exposing them to components.
- Expose loading, empty, and error state explicitly.

---

## Naming Conventions

| Item | Convention |
|---|---|
| Composable files | `useSomething.ts` |
| Feature composables | `useRecordsList`, `useRecordFilters`, `useDashboardStats`, `useDeviceStatus` |
| Returned members | Prefer clear groups such as `state`, `actions`, `loading`, `error` |

Do not create vague names like `useData`, `useCommon`, or `useHelper`.

---

## Examples

| Repository evidence | What it suggests |
|---|---|
| `MainPagePrototype.qml` state groups such as `dailyTotal`, `dailyGood`, `dailyBad` | A future `useDashboardStats` composable is a natural fit |
| `MainPagePrototype.qml` device and connectivity flags | A future `useDeviceStatus` composable is a natural fit |
| `工业缺陷检测系统完整方案.md` route plan for records and details | Record-centric composables should be split by list vs. detail use cases |

---

## Common Mistakes

| Mistake | Why it is a problem |
|---|---|
| Creating a composable for logic that is only used once and stays tiny | Adds indirection without reuse |
| Returning raw backend payloads directly to components | Leaks transport concerns into the UI |
| Hiding loading and error state inside the composable with no public signal | Pages cannot render proper states |
| Mixing record filters, auth, and device polling into one giant composable | Hard to maintain and test |
