# Type Safety

> TypeScript type and boundary conventions for the web frontend.

---

## Overview

The frontend is now implemented with `Vue 3 + Vite + TypeScript`.

Current repository contracts:

- raw backend DTOs live in `src/types/api.ts`
- frontend view models live in `src/types/models.ts`
- DTO-to-view-model conversion lives in `src/services/mappers/commonMappers.ts`
- record list/detail pages and review forms consume mapped models instead of raw snake_case payloads

The highest-risk type boundary in this project is the detection-record flow, because it combines:

- backend route aggregation
- record result semantics
- multiple event timestamps
- manual review data that can override the final displayed result

---

## Type Organization

| Type kind | Location | Contract |
|---|---|---|
| API DTOs | `src/types/api.ts` | Keep backend snake_case exactly as returned by FastAPI |
| View models | `src/types/models.ts` | Expose camelCase fields for components only |
| API payloads | `src/types/api.ts` | Match backend request bodies exactly |
| Feature filters | feature-local composable or page-local type | Stay close to the feature that owns the query |
| Mapping functions | `src/services/mappers/commonMappers.ts` | Single boundary for DTO-to-view-model conversion |

### Mapping Rule

Keep backend DTOs and frontend view models distinct.

| Layer | Example shape |
|---|---|
| API DTO | `effective_result`, `captured_at`, `reviewer_display_name` |
| Frontend model | `effectiveResult`, `capturedAt`, `reviewerDisplayName` |

Do the conversion in the mapper layer, not in components, stores, or templates.

### Timestamp Rule

Keep record timestamps as ISO strings in DTOs and view models until the formatting layer.

Why:

- backend already owns timezone serialization
- current pages only need display and transport, not date arithmetic
- converting to `Date` too early increases timezone drift risk

---

## Validation

These validation rules already apply in the current implementation:

| Rule | Reason |
|---|---|
| Treat all backend responses as untrusted at the API boundary | Prevents UI corruption from malformed payloads |
| Parse route params before issuing detail requests | Prevents meaningless traffic and clearer page-level errors |
| Normalize optional form fields to `null` before submit | Keeps request payloads stable across frontend/backend |
| Keep enums narrow (`good`, `bad`, `uncertain`, `pending`, `reviewed`, `ai_reserved`) | Prevents invalid UI branching |

If a runtime validation library is introduced later, keep it at the API and form boundaries rather than scattering it across components.

---

## Scenario: Detection Record Boundary and Review Flow

### 1. Scope / Trigger

- Trigger: any change touching detection record list/detail, manual review submission, file objects, or statistics derived from final results
- Affected layers: FastAPI route -> response DTO -> frontend API service -> mapper -> page/component

### 2. Signatures

```ts
fetchRecords(params?: {
  partId?: number;
  deviceId?: number;
  result?: DetectionResult;
  reviewStatus?: ReviewStatus;
  skip?: number;
  limit?: number;
}): Promise<DetectionRecordListResponseDto>;

fetchRecordDetail(recordId: number): Promise<DetectionRecordDetailDto>;

createManualReview(
  recordId: number,
  payload: ManualReviewCreateRequestDto,
): Promise<ReviewRecordDto>;
```

```http
GET /api/v1/records
GET /api/v1/records/{id}
POST /api/v1/records/{id}/manual-review
```

```json
{
  "id": 1,
  "record_no": "REC-20260420-0001",
  "result": "uncertain",
  "effective_result": "bad",
  "review_status": "reviewed",
  "captured_at": "2026-04-20T10:00:00Z",
  "detected_at": "2026-04-20T10:00:01Z",
  "uploaded_at": "2026-04-20T10:00:04Z",
  "storage_last_modified": "2026-04-20T10:00:04Z"
}
```

### 3. Contracts

| Field / boundary | Contract |
|---|---|
| `result` | MP157 initial result. It preserves the edge model decision and must not be repurposed as the final reviewed result |
| `effective_result` | Final result for list display, detail emphasis, and statistics. The latest review overrides `result` |
| `captured_at` | Time when the sample image was captured |
| `detected_at` | Time when MP157 completed local detection |
| `uploaded_at` | Time when file upload or metadata registration completed on the application side |
| `storage_last_modified` | COS last-modified time returned by storage metadata when available |
| DTO fields | Stay snake_case and match backend payloads exactly |
| View models | Stay camelCase and only expose mapped fields |
| Review forms | Submit `null` for empty optional fields, not empty strings |
| Datetime form payloads | Convert Element Plus local `YYYY-MM-DDTHH:mm:ss` values to timezone-aware ISO strings before submit |

Additional boundary rules:

- records tables may show both `result` and `effectiveResult`, but summary badges and final decision displays must use `effectiveResult`
- detail pages must keep both values visible for auditability
- components must never reach into raw DTOs such as `dto.effective_result`
- form helpers such as `normalizeOptionalDateTime()` own the local-datetime -> ISO conversion; pages and components must not hand-roll this logic

### 4. Validation & Error Matrix

| Condition | Boundary | Expected behavior |
|---|---|---|
| Route param is not a finite number | page layer | Stop the request and surface a page-level error |
| Manual-review path is wrong | API service boundary | Request fails with `404`; fix the service path, not the component |
| Backend omits a required record field | type boundary | Fail compilation or mapper contract review; do not patch with `any` |
| Optional review text/time is empty | form boundary | Normalize to `null` before submit |
| Datetime input is local time without timezone | form boundary | Convert to `Date(...).toISOString()` before sending the request |
| Timestamp field is `null` | formatting boundary | Render fallback text such as `Not recorded`, not an invalid date string |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | Records table shows `result` as MP initial result and `effectiveResult` as final status, then detail page reloads after manual review |
| Base | No review exists, so `effective_result === result` |
| Bad | Component edits `result` after manual review or treats `effective_result` as an optional cosmetic field |

### 6. Tests Required

- mapper tests for `DetectionRecordDto -> DetectionRecordModel`, including `effective_result`, review history, and timestamp fields
- API contract test for `POST /api/v1/records/{id}/manual-review`
- page test asserting record detail reload after manual review success
- formatting test for `null` timestamps and missing optional review fields
- form utility test asserting local datetime input is normalized to timezone-aware ISO before submit

Assertion points:

- `result` is preserved after manual review
- `effectiveResult` changes after the latest review changes
- empty `comment`, `defect_type`, and `reviewed_at` are normalized to `null`
- local datetime strings such as `2026-04-20T10:00:00` are converted before crossing the frontend/backend boundary
- components consume mapped camelCase fields only

### 7. Wrong vs Correct

#### Wrong

```ts
// Direct DTO consumption leaks backend naming into the page.
const record = await fetchRecordDetail(id);
title.value = record.effective_result;
```

```ts
// Wrong mounted path: backend does not expose /reviews/records/...
apiRequest(`/api/v1/reviews/records/${recordId}/manual-review`, {
  method: "POST",
  body: JSON.stringify(payload),
});
```

#### Correct

```ts
const dto = await fetchRecordDetail(id);
const record = mapDetectionRecordDetailDto(dto);
title.value = record.effectiveResult;
```

```ts
apiRequest(`/api/v1/records/${recordId}/manual-review`, {
  method: "POST",
  body: JSON.stringify(payload),
});
```

```ts
// Wrong: local datetime string is sent without timezone context.
const payload = {
  reviewed_at: "2026-04-20T10:00:00",
};
```

```ts
const payload = {
  reviewed_at: normalizeOptionalDateTime("2026-04-20T10:00:00"),
};
```

---

## Forbidden Patterns

| Pattern | Why it is forbidden |
|---|---|
| Reusing raw API DTOs directly in components | Makes the UI depend on backend naming and route drift |
| Using `any` to bypass payload uncertainty | Hides contract bugs discovered during real integration |
| Treating `result` and `effective_result` as synonyms | Destroys auditability and breaks statistics |
| Converting timestamps ad hoc in many components | Creates inconsistent timezone behavior |
