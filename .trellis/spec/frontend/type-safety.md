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

## Scenario: Auxiliary Option Loader Query Limits and 422 Translation

### 1. Scope / Trigger

- Trigger: any change touching `fetchParts(...)`, `fetchDevices(...)`, statistics filter option loading, records filter option loading, or frontend API error normalization
- Affected layers: FastAPI query validation -> frontend API service -> page/composable loaders -> page-level alert or toast rendering

### 2. Signatures

```ts
fetchParts(query?: {
  keyword?: string;
  isActive?: boolean;
  skip?: number;
  limit?: number;
}): Promise<PartListResponseDto>;

fetchDevices(query?: {
  keyword?: string;
  status?: DeviceStatus;
  skip?: number;
  limit?: number;
}): Promise<DeviceListResponseDto>;

function apiRequest<TResponse>(input: string, init?: RequestInit): Promise<TResponse>;
```

```http
GET /api/v1/parts?skip=0&limit=100
GET /api/v1/devices?skip=0&limit=100
```

```json
{
  "detail": [
    {
      "type": "less_than_equal",
      "loc": ["query", "limit"],
      "msg": "Input should be less than or equal to 100",
      "input": "200"
    }
  ]
}
```

### 3. Contracts

| Boundary / field | Contract |
|---|---|
| `parts` list query `limit` | Must stay within the backend route constraint `1 <= limit <= 100` |
| `devices` list query `limit` | Must stay within the backend route constraint `1 <= limit <= 100` |
| Statistics reference loaders | Must not request a larger page size than the route allows just because the page wants a “full” dropdown |
| Records reference loaders | Same rule as statistics: use the backend max, not an arbitrary frontend guess such as `200` |
| `422` FastAPI validation payload | Usually arrives as `detail`, not as project-shaped `{ message, code }`; frontend must translate it into a readable message |
| Page-level partial option failure | A failed auxiliary dropdown load must not be misread as “the whole page API is down” when core data such as records or overview still returned `200` |

Additional boundary rules:

- when a master-data list is used only for filter options, prefer the backend maximum supported `limit` instead of inventing a larger request size
- if the backend maximum changes later, update the frontend service callers and the code-spec together
- generic `"接口请求失败"` is not an acceptable steady-state message for a known `422` validation failure; the UI should explain which request parameter is invalid
- when a page uses `Promise.allSettled(...)` for auxiliary loaders, one `422` must surface as a precise partial-failure message rather than hiding the successful requests

### 4. Validation & Error Matrix

| Condition | Boundary | Expected behavior |
|---|---|---|
| Frontend sends `limit=200` to `/api/v1/parts` | query contract | Backend returns `422`; frontend must treat this as a contract mismatch, not a backend outage |
| Frontend sends `limit=200` to `/api/v1/devices` | query contract | Same as parts; fix the caller to `<= 100` |
| Backend returns FastAPI default `detail[]` payload | API error boundary | Normalize the response into a readable frontend `message` |
| Statistics overview returns `200`, but auxiliary parts/devices loaders return `422` | page state boundary | Keep the overview visible and show a partial auxiliary-load warning only |
| Records list returns `200`, but the parts filter request returns `422` | page state boundary | Keep the records table visible and show a targeted auxiliary-load error instead of implying the records API failed |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | Statistics page loads `/overview`, `/parts?limit=100`, `/devices?limit=100`, and `/settings/ai-models/runtime-options`; if one auxiliary request fails, the warning text explains which option set failed |
| Base | A page only needs up to 100 option rows, so the dropdowns load successfully with the backend-supported maximum |
| Bad | A page requests `limit=200`, receives `422`, and shows a vague “接口请求失败” toast even though the root cause is a frontend query contract violation |

### 6. Tests Required

- frontend API-layer test for validation-payload normalization from FastAPI `detail[]` into a readable `ApiClientError.message`
- page/composable test asserting statistics reference loaders request `limit=100` for parts and devices
- page/composable test asserting records reference loaders request `limit=100` for parts
- UI-state test asserting a partial auxiliary-loader failure does not wipe out already successful primary data

Assertion points:

- `fetchParts(...)` and `fetchDevices(...)` callers stay within the backend route limit
- FastAPI `422` payloads no longer surface as only `"接口请求失败"`
- statistics and records pages distinguish auxiliary dropdown failure from primary page-data failure

### 7. Wrong vs Correct

#### Wrong

```ts
// Frontend guesses a larger page size than the backend allows.
const [partResponse, deviceResponse] = await Promise.all([
  fetchParts({ limit: 200 }),
  fetchDevices({ limit: 200 }),
]);
```

```ts
if (!response.ok) {
  throw new ApiClientError(response.status, payload ?? {});
}
```

#### Correct

```ts
const [partResponse, deviceResponse] = await Promise.all([
  fetchParts({ limit: 100 }),
  fetchDevices({ limit: 100 }),
]);
```

```ts
if (!response.ok) {
  throw new ApiClientError(
    response.status,
    normalizeApiErrorPayload(payload ?? {}),
  );
}
```

---

## Forbidden Patterns

| Pattern | Why it is forbidden |
|---|---|
| Reusing raw API DTOs directly in components | Makes the UI depend on backend naming and route drift |
| Using `any` to bypass payload uncertainty | Hides contract bugs discovered during real integration |
| Treating `result` and `effective_result` as synonyms | Destroys auditability and breaks statistics |
| Converting timestamps ad hoc in many components | Creates inconsistent timezone behavior |

---

## Scenario: Auth Session and Password Reset Boundary

### 1. Scope / Trigger

- Trigger: any change to login, register, `/auth/me`, runtime auth options, forgot-password, or reset-password pages
- Affected layers: FastAPI auth schemas -> frontend auth API -> mapper -> auth store -> login/reset page

### 2. Signatures

```ts
interface AuthRuntimeOptionsDto {
  registration_enabled: boolean;
  password_reset_enabled: boolean;
  password_policy_hint: string;
}

interface AuthSessionResponseDto {
  session_expires_at: string;
  user: UserProfileDto;
}

interface ResetPasswordRequestDto {
  token: string;
  new_password: string;
}
```

### 3. Contracts

| Boundary / field | Contract |
|---|---|
| `AuthSessionResponseDto` | No readable `access_token` field after moving to cookie auth |
| `UserProfileDto.email` | Nullable because historical seed users may not have email yet |
| `UserProfileDto.password_changed_at` | Present for audit / future account settings flows, but still mapped instead of consumed raw |
| `password_policy_hint` | Backend-owned string shown directly by auth forms; do not duplicate a second policy string in components |
| `ResetPasswordRequestDto.new_password` | Must stay snake_case in DTO and only become camelCase after mapping or page-local form transformation |

Additional rules:

- components must not assume password reset is available without reading `password_reset_enabled`
- pages must not read `dto.display_name` or `dto.password_changed_at` directly after the mapper boundary
- auth store and auth pages must treat cookie ownership as an implicit transport contract, not as a JSON token contract

### 4. Validation & Error Matrix

| Condition | Boundary | Expected behavior |
|---|---|---|
| Backend removes `access_token` from login JSON | API/store boundary | Frontend still works because it reads `response.user`, not a token field |
| Runtime options endpoint disables password reset | page boundary | Forgot-password UI shows a disabled state instead of pretending the feature works |
| Historical user has `email = null` | mapper boundary | UI handles `null` safely and does not crash on profile render |
| Reset-password payload uses camelCase by mistake | API boundary | Type review should reject it; request body must remain `new_password` |

### 5. Tests Required

- store test for login response without any token field
- store test for register response mapping
- auth-page or store-adjacent test covering restore-session failure
- API contract review for `ResetPasswordRequestDto` field naming

### 6. Wrong vs Correct

#### Wrong

```ts
await apiRequest("/api/v1/auth/reset-password", {
  method: "POST",
  body: JSON.stringify({
    token,
    newPassword,
  }),
});
```

#### Correct

```ts
await resetPasswordRequest({
  token,
  new_password: newPassword,
});
```
