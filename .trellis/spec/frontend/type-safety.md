# Type Safety

> TypeScript type and validation conventions for the web frontend.

---

## Overview

No TypeScript project exists in the repository yet, but the planned frontend stack is `Vue 3 + Vite`, so TypeScript is the expected baseline for the first scaffold.

Current evidence that informs type design:

- backend planning snippet uses snake_case fields such as `image_path`, `detect_time`, and `ai_result`
- web pages already imply route params and record-centric DTOs
- `MainPagePrototype.qml` shows clear domain groupings such as device state, stats, and detection results

---

## Type Organization

| Type kind | Recommended location |
|---|---|
| API DTOs | `src/types/api.ts` or feature-specific `types/api.ts` |
| View models | `src/types/view-models.ts` or feature-specific type files |
| Store state | close to the store that owns it |
| Table and filter types | feature-local type files |

### Mapping Rule

Keep backend DTOs and frontend view models distinct.

Example direction:

| Layer | Example shape |
|---|---|
| API DTO | `image_path`, `detect_time`, `ai_result` |
| Frontend model | `imagePath`, `detectTime`, `aiResult` |

Do the conversion in a mapper layer, not in components.

---

## Validation

Runtime validation is not implemented yet, but these rules still apply:

| Rule | Reason |
|---|---|
| Treat all backend responses as untrusted at the API boundary | Prevents UI corruption from malformed payloads |
| Parse and normalize unknown data before exposing it to components | Keeps UI contracts stable |
| Validate form payloads before submit | Prevents avoidable round trips |

If a validation library is introduced later, keep it at the API and form boundaries rather than scattering it through every component.

---

## Common Patterns

The current documents imply these important types:

| Type | Why it matters |
|---|---|
| `DetectionRecordDto` | Main record list and detail pages |
| `DetectionRecordFilters` | Records search, pagination, and date range queries |
| `ManualReviewPayload` | Manual review submission |
| `DeviceStatusDto` | Devices overview page |
| `PartDto` | Part management page |

Baseline rules:

- Do not use `any` for API responses.
- Route params and query params must be typed.
- Use discriminated unions or stable enums for statuses such as `good`, `bad`, `uncertain`, and `pending`.

---

## Forbidden Patterns

| Pattern | Why it is forbidden |
|---|---|
| Reusing raw API DTOs directly in components | Makes UI depend on backend naming choices |
| Using `any` to bypass payload uncertainty | Hides contract problems |
| Storing mixed types in one generic object such as `recordData: any` | Loses discoverability and safety |
| Performing DTO-to-view-model conversion inside templates | Hard to reuse and test |

---

## Examples

| Repository evidence | Type-safety takeaway |
|---|---|
| `工业缺陷检测系统完整方案.md` backend record fields | DTOs should be defined explicitly, not inferred ad hoc |
| `工业缺陷检测系统完整方案.md` `/record/:id` page | Route params must be typed |
| `MainPagePrototype.qml` distinct fields such as `dailyTotal`, `confidenceScore`, `dxPixels` | Domain-specific typed state is clearer than generic dictionaries |
