# State Management

> State management rules for the Vue frontend.

---

## Overview

No store implementation exists yet. Current UI evidence comes from `MainPagePrototype.qml`, where state is grouped at page level through descriptive root properties.

Bootstrap decision for the web app:

- use component local state first
- use Pinia only when state truly crosses pages or lifecycles
- treat backend data as server state, not generic global state

---

## Local vs Global State

| State type | Where it belongs |
|---|---|
| One-page toggles, dialog visibility, table sorting UI | local component state |
| Filters shared by one feature page and its child components | feature composable or page-level state |
| Auth session, user identity, app shell preferences | global store |
| Live device summary shown across multiple pages | global store if multiple pages need it |
| Detection records, parts list, review detail | server state fetched from the backend |

### Evidence from current prototype

The QML prototype keeps screen-specific data close to the page:

- `currentStateText`
- `dxPixels`
- `confidenceScore`
- `dailyTotal`

That is the right default mindset for the web app as well.

---

## Store Structure

If Pinia is introduced, prefer small stores by domain:

| Store | Responsibility |
|---|---|
| `useAuthStore` | login state, user identity, permissions |
| `useUiStore` | shell preferences, sidebar state, theme mode if added |
| `useDeviceStore` | shared connectivity summary for edge devices |

Do not create a single catch-all `useAppStore` for every concern.

---

## Server State

| Rule | Reason |
|---|---|
| Keep server data close to the feature that owns it | Reduces accidental coupling |
| Cache list and detail data separately | Different invalidation behavior |
| Normalize DTOs before storing or exposing them | Keeps UI models stable |
| Treat filters, pagination, and sorting as first-class state | The planned records page depends on them |

Recommended first server-state domains:

- dashboard stats
- records list
- record detail plus review data
- parts list
- devices overview

---

## Examples

| Repository evidence | What it suggests |
|---|---|
| `MainPagePrototype.qml` | Page state is grouped by domain, not one giant anonymous object |
| `工业缺陷检测系统完整方案.md` route plan | Records, devices, parts, and settings should not share one global store |
| `STM32MP157DAA1工业缺陷检测系统综合方案.md` | Cloud UI and device UI are separate concerns and should not share one state model blindly |

---

## Common Mistakes

| Mistake | Why it is a problem |
|---|---|
| Putting every fetched response into one global store | Creates stale duplicated state |
| Treating URL filters as hidden store state | Makes sharing and refresh behavior poor |
| Mixing auth state with page-specific table state | Unclear ownership |
| Mirroring backend DTO shape everywhere instead of mapping once | Cross-layer coupling spreads quickly |
