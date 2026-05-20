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

deleteRecord(recordId: number): Promise<ApiMessageResponseDto>;

createManualReview(
  recordId: number,
  payload: ManualReviewCreateRequestDto,
): Promise<ReviewRecordDto>;
```

```http
GET /api/v1/records
GET /api/v1/records/{id}
DELETE /api/v1/records/{id}
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
| Record delete response | Uses the shared `{ message: string }` response shape; no record DTO is returned after delete |
| Record delete caller | `frontend/src/services/api/records.ts::deleteRecord(recordId)` is the only frontend API wrapper for `DELETE /api/v1/records/{id}` |
| Review forms | Submit `null` for empty optional fields, not empty strings |
| Datetime form payloads | Convert Element Plus local `YYYY-MM-DDTHH:mm:ss` values to timezone-aware ISO strings before submit |

Additional boundary rules:

- records tables may show both `result` and `effectiveResult`, but summary badges and final decision displays must use `effectiveResult`
- detail pages must keep both values visible for auditability
- records table delete actions are admin-only destructive actions; after delete, refresh the current list from the backend instead of locally filtering `items`
- components must never reach into raw DTOs such as `dto.effective_result`
- form helpers such as `normalizeOptionalDateTime()` own the local-datetime -> ISO conversion; pages and components must not hand-roll this logic

### 4. Validation & Error Matrix

| Condition | Boundary | Expected behavior |
|---|---|---|
| Route param is not a finite number | page layer | Stop the request and surface a page-level error |
| Manual-review path is wrong | API service boundary | Request fails with `404`; fix the service path, not the component |
| Delete path uses a non-mounted URL | API service boundary | Request fails with `404`; use `/api/v1/records/{id}`, not `/api/v1/reviews/...` or a list-only endpoint |
| Non-admin user attempts delete | auth/API boundary | Backend returns `403`; UI should normally hide the destructive action for non-admin sessions |
| Backend omits a required record field | type boundary | Fail compilation or mapper contract review; do not patch with `any` |
| Optional review text/time is empty | form boundary | Normalize to `null` before submit |
| Datetime input is local time without timezone | form boundary | Convert to `Date(...).toISOString()` before sending the request |
| Timestamp field is `null` | formatting boundary | Render fallback text such as `Not recorded`, not an invalid date string |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | Records table shows `result` as MP initial result and `effectiveResult` as final status, then detail page reloads after manual review |
| Good | Admin confirms a row delete, `deleteRecord(id)` calls `DELETE /api/v1/records/{id}`, and the records list refreshes from server state |
| Base | No review exists, so `effective_result === result` |
| Bad | Component edits `result` after manual review or treats `effective_result` as an optional cosmetic field |
| Bad | Component hides a deleted row locally without reloading, leaving `total`, pagination, and category counts stale |

### 6. Tests Required

- mapper tests for `DetectionRecordDto -> DetectionRecordModel`, including `effective_result`, review history, and timestamp fields
- API contract test for `POST /api/v1/records/{id}/manual-review`
- API contract test or route smoke test for `DELETE /api/v1/records/{id}`
- page/composable test asserting record delete refreshes the list and keeps pagination state consistent
- page test asserting record detail reload after manual review success
- formatting test for `null` timestamps and missing optional review fields
- form utility test asserting local datetime input is normalized to timezone-aware ISO before submit

Assertion points:

- `result` is preserved after manual review
- `effectiveResult` changes after the latest review changes
- destructive delete actions stay behind admin role checks in the UI and backend dependency
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

```ts
// Wrong: local row filtering leaves pagination totals and category summaries stale.
items.value = items.value.filter((item) => item.id !== recordId);
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
await deleteRecord(recordId);
await refresh();
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

## Scenario: Record AI Chat Reference Image Boundary

### 1. Scope / Trigger

- Trigger: any change touching single-record AI chat context files, `AIContextFile`, record-file selection for multimodal prompts, or the AI chat dialog reference-file UI.
- Affected layers: `RecordService` file selection -> `AIContextFile` schema -> AI prompt snapshot -> frontend DTO/model mapper -> `AiReviewChatDialog`.

### 2. Signatures

```py
class AIContextFile(BaseModel):
    id: int
    file_kind: FileKind
    bucket_name: str
    region: str
    object_key: str
    uploaded_at: datetime | None
    preview_url: str | None
    analysis_purpose: str | None = None
```

```py
RecordService._select_ai_reference_files(record: DetectionRecord) -> list[FileObject]
RecordService._resolve_ai_file_analysis_purpose(file_object: FileObject) -> str
```

```ts
export interface AIContextFileDto {
  id: number;
  file_kind: FileKind;
  object_key: string;
  analysis_purpose: string | null;
}

export interface AIContextFile {
  id: number;
  fileKind: FileKind;
  objectKey: string;
  analysisPurpose: string | null;
}
```

### 3. Contracts

| Boundary / field | Contract |
|---|---|
| Backend reference selection | Preserve up to four complementary model artifacts, not only three generic images. |
| Artifact order | Prefer UNet mask, UNet overlay, MobileNetV3-Small classification result, then raw source image. |
| `analysis_purpose` | Must explain what the image means for inspection, for example raw image, UNet mask, UNet overlay, or MobileNetV3-Small classification evidence. |
| AI prompt snapshot | Must include `analysis_purpose` inside `referenced_files` so the model understands how to use each image. |
| Good/bad user questions | Prompts must ask the model to give a direct good/bad/evidence-insufficient tendency before discussing audit status. |
| Board correction prompt | If the AI's evidence-based recommendation differs from `record_context.result`, the answer must include a `修正板端结果填写建议` section with `decision`, `defect_type`, and `cloud_reason` values that map to the board-correction dialog. |
| Follow-up memory | The frontend sends recent `history`, and the backend must also embed a readable recent-history block in the current user prompt so provider gateways that mishandle message arrays still preserve follow-up context. |
| Prompt cache order | The readable history block must be appended after the stable record prompt and context snapshot, not prepended before them, so stable instructions and record context remain a cacheable prefix. |
| Pending manual review | `review_status="pending"` is a risk boundary and next-step suggestion, not a reason to avoid image-based advice. |
| Frontend mapper | `analysis_purpose -> analysisPurpose` must happen in `commonMappers.ts`; components must not read snake_case directly. |
| Reference-file UI | Use short file labels plus tooltip/full detail; do not render full COS paths in tags where they can overflow the dialog. |

### 4. Validation & Error Matrix

| Condition | Boundary | Expected behavior |
|---|---|---|
| Record has mask, overlay, classification, raw, and thumbnail files | service selection | Return the four evidence files and omit the thumbnail. |
| File name ends with `_mask.png` | service metadata | `analysis_purpose` identifies it as a UNet mask. |
| File name ends with `_overlay.jpg` | service metadata | `analysis_purpose` identifies it as a UNet overlay image. |
| File name contains `mobilenet`, `classification`, `classify`, or `classifier` | service metadata | `analysis_purpose` identifies it as MobileNetV3-Small classification evidence. |
| User asks "is this good or bad" while review is pending | prompt boundary | Answer should first state the current evidence-based tendency, then explain uncertainty and review action. |
| AI recommendation conflicts with MP157 initial result | prompt boundary | Add `修正板端结果填写建议`: for `good -> bad`, use `decision=bad`, defect type, and a copyable bad-result reason; for `bad -> good`, use `decision=good`, `defect_type=null` or `无明显缺陷`, and a copyable good-result reason. |
| User follow-up says "this position", "why", or "continue" | prompt boundary | Current model request includes recent user/assistant turns in a `同一弹窗历史对话` block appended after the stable current-record prompt. |
| Long COS object key appears in referenced files | UI boundary | The dialog stays within its width; full path remains accessible by tooltip. |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | AI receives four images: `*_mask.png`, `*_overlay.jpg`, `*classification*.jpg`, and `*_raw.jpg`, each with a purpose sentence. |
| Good | The model answer explains why the current evidence leans good or bad, then notes whether manual review is still needed. |
| Good | MP157 initially says `good`, but AI recommends `bad`; the answer says the correction dialog should use `decision=bad`, a concrete `defect_type`, and a copyable `cloud_reason`. |
| Good | The user asks a second question using "这个位置"; the backend prompt includes the previous assistant answer so the model can resolve the reference. |
| Base | Only source and annotated images exist; both still get purpose text and are sent in stable order. |
| Bad | Backend slices reference files to three images and drops the raw image or classifier result. |
| Bad | UI renders `标注图 / detections/.../very-long-object-key.png` as an unbounded tag and expands the chat dialog horizontally. |
| Bad | Prompt tells the user only "manual review has not happened yet" when the question asks for a quality recommendation. |
| Bad | AI says "it may be bad" but does not tell the operator what to put in `decision`, `defect_type`, and `cloud_reason`. |
| Bad | The frontend displays previous bubbles but the current backend model request only contains the newest question, so the model cannot know what "这个" refers to. |

### 6. Tests Required

- Backend service test asserting four model artifact images are selected in the expected order.
- Backend AI client test asserting chat prompts include artifact meanings and the direct good/bad advice requirement.
- Backend AI client test asserting chat/review prompts include board-correction field recommendations when AI advice can conflict with the MP157 initial result.
- Backend AI client tests asserting non-streaming and streaming single-record chat requests embed recent previous turns in the current user prompt.
- Frontend utility test asserting evidence image sorting keeps mask, overlay, classifier, and raw images together.
- Frontend build/typecheck after changing `AIContextFileDto` or `AIContextFile`.

Assertion points:

- `referenced_files[].analysis_purpose` survives backend schema serialization.
- `mapAIContextFileDto(...)` maps `analysis_purpose` to `analysisPurpose`.
- Reference tags use bounded labels and keep full object keys in a detail surface.
- `review_status` remains visible but does not replace the AI's evidence-based recommendation.
- Follow-up prompts include recent history both as structured `history` messages and as a readable prompt block appended after the stable record context.

### 7. Wrong vs Correct

#### Wrong

```py
return sorted(record.files, key=... )[:3]
```

```ts
// Full object key is rendered directly inside a tag and can stretch the dialog.
{{ getAiFileKindLabel(file.fileKind) }} / {{ file.objectKey }}
```

#### Correct

```py
return sorted(
    record.files,
    key=lambda item: (
        self._resolve_ai_file_artifact_priority(file_object=item),
        self._ai_file_priority.get(item.file_kind, 99),
    ),
)[:4]
```

```ts
function buildReferenceFileLabel(file: AIContextFile): string {
  const fileName = file.objectKey.split("/").filter(Boolean).at(-1) ?? file.objectKey;
  return `${getAiFileKindLabel(file.fileKind)} / ${fileName}`;
}
```

---

## Scenario: Board Review Sync DTO Boundary

### 1. Scope / Trigger

- Trigger: any change touching board-review synchronization from record detail, device board-review configuration, `src/services/api/reviews.ts`, `src/services/api/devices.ts`, or detection-record/device DTO fields.
- Affected layers: backend response DTO -> `src/types/api.ts` -> mapper -> `src/types/models.ts` -> `RecordDetailPage.vue` and `DevicesPage.vue`.

### 2. Signatures

```ts
export type BoardSyncStatus = "not_required" | "pending" | "success" | "failed";

export interface BoardReviewSyncRequestDto {
  decision: DetectionResult;
  cloud_reason: string;
  defect_type: string | null;
  reviewed_at: string | null;
}

export interface BoardReviewSyncResponseDto {
  review: ReviewRecordDto;
  board_sync_status: BoardSyncStatus;
  board_sync_time: string | null;
  board_sync_error: string | null;
}

export interface DetectionRecordDto {
  board_sync_status: BoardSyncStatus | null;
  board_sync_time: string | null;
  board_sync_error: string | null;
  board_last_synced_review_id: number | null;
}

export interface DeviceDto {
  board_review_url: string | null;
  has_board_review_token: boolean;
}

syncBoardReview(recordId: number, payload: BoardReviewSyncRequestDto): Promise<BoardReviewSyncResponseDto>;
```

### 3. Contracts

| Boundary / field | Contract |
|---|---|
| `cloud_reason` | Frontend must trim and block empty text before calling the API; backend still validates again. |
| `reviewed_at` | If generated by the browser, send timezone-aware ISO such as `new Date().toISOString()`, not Element Plus local datetime text. |
| AI correction recommendation | AI text may suggest the operator-filled values, but the dialog still submits only `decision`, `cloud_reason`, `defect_type`, and `reviewed_at`; it must not invent extra payload fields. |
| `DetectionRecordModel.boardSync*` | All sync fields must be mapped through `mapDetectionRecordDto(...)`; components must not read snake_case DTOs directly. |
| `DeviceModel.hasBoardReviewToken` | UI can display configured/not configured, but must not expose token plaintext. |
| Device edit token field | Empty edit value means "do not update existing token"; only send `board_review_token` when the admin fills it. |
| Detail action count | Record detail should provide one board-correction button that opens a reason dialog, not several quick-action reason buttons. |
| Button placement | Board correction belongs to `RecordDetailPage` review workspace, not master-data pages or the records table. |

### 4. Validation & Error Matrix

| Condition | Boundary | Expected behavior |
|---|---|---|
| Reason input is blank after trim | page layer | Show "请填写修正原因" and do not call `syncBoardReview(...)`. |
| Backend returns `board_sync_status="success"` | page layer | Show success toast and reload record detail so effective result, reviews, and sync status converge. |
| Backend returns `board_sync_status="failed"` | page layer | Show warning/error message from `board_sync_error`, close the dialog, and reload detail. |
| Device has existing token and admin only edits URL | form layer | Send no `board_review_token` field, preserving the existing backend token. |
| Device list renders token state | table layer | Render only configured/not configured; never render the token string. |
| New DTO fields are added | mapper boundary | Update both `api.ts`, `models.ts`, and `commonMappers.ts`; update test fixtures that construct `DetectionRecordModel`. |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | Detail page opens "修正板端结果", submits `{ decision, cloud_reason, defect_type, reviewed_at }`, then reloads the record. |
| Base | Latest sync failed because the board was offline; page shows the saved failure summary and allows the user to retry with a reason. |
| Base | Device list shows "地址已配置" and "密钥已配置" badges without token text. |
| Bad | A component reads `dto.board_sync_error` directly and bypasses the mapper. |
| Bad | Device edit sends `board_review_token: null` whenever the password field is blank, accidentally clearing the stored token. |

### 6. Tests Required

- frontend build/typecheck after DTO/model/mapper changes
- API wrapper test or source review asserting `syncBoardReview(...)` calls `/api/v1/records/{id}/sync-board-review`
- mapper test/fixture update asserting `board_sync_status -> boardSyncStatus`
- form behavior check asserting blank board-token edit does not clear the stored token
- detail-page behavior check asserting blank reason blocks submit and sync success/failure reloads detail

Assertion points:

- all snake_case fields stop at `src/types/api.ts` and `commonMappers.ts`
- browser never receives or renders `board_review_token`
- record detail keeps exactly one board correction entry point

### 7. Wrong vs Correct

#### Wrong

```ts
await apiRequest("http://192.168.1.250:18080/api/v1/review-result", {
  method: "POST",
  body: JSON.stringify({ cloud_reason: reason }),
});
```

#### Correct

```ts
await syncBoardReview(record.value.id, {
  decision: boardSyncDecision.value,
  cloud_reason: reason,
  defect_type: record.value.defectType,
  reviewed_at: new Date().toISOString(),
});
```

#### Wrong

```ts
const updatePayload = {
  ...payloadBase,
  board_review_token: normalizeOptionalText(formState.boardReviewToken),
};
```

#### Correct

```ts
const updatePayload = {
  ...payloadBase,
  board_review_token: normalizeOptionalText(formState.boardReviewToken) ?? undefined,
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

---

## Scenario: Password Change Request DTO Boundary

### 1. Scope / Trigger

- Trigger: any change touching the settings password-request card, admin user-management password actions, or the password-request-related API contracts
- Affected layers: FastAPI settings schemas -> frontend `src/types/api.ts` -> mapper -> `src/types/models.ts` -> `SettingsPage.vue`

### 2. Signatures

```ts
export interface UserPasswordChangeRequestInfoDto {
  password_change_request_status: PasswordChangeRequestStatus | null;
  password_change_request_type: PasswordChangeRequestType | null;
  password_change_requested_at: string | null;
  password_change_reviewed_at: string | null;
  default_reset_password: string;
}

export interface SubmitPasswordChangeRequestDto {
  request_type: PasswordChangeRequestType;
  new_password: string | null;
}

export interface ApprovePasswordChangeRequestResponseDto {
  message: string;
  applied_password: string | null;
}

export interface AdminPasswordResetResponseDto {
  message: string;
  applied_password: string;
}
```

```ts
export interface UserPasswordChangeRequestInfo {
  passwordChangeRequestStatus: PasswordChangeRequestStatus | null;
  passwordChangeRequestType: PasswordChangeRequestType | null;
  passwordChangeRequestedAt: string | null;
  passwordChangeReviewedAt: string | null;
  defaultResetPassword: string;
}

export interface SystemUserListItem {
  passwordChangeRequestStatus: PasswordChangeRequestStatus | null;
  passwordChangeRequestType: PasswordChangeRequestType | null;
  passwordChangeRequestedAt: string | null;
  passwordChangeReviewedAt: string | null;
}
```

### 3. Contracts

| Boundary / field | Contract |
|---|---|
| `SubmitPasswordChangeRequestDto.request_type` | Must stay snake_case in the outbound JSON body |
| `SubmitPasswordChangeRequestDto.new_password` | Nullable in DTO because `reset_to_default` does not submit a new password |
| `UserPasswordChangeRequestInfoDto.default_reset_password` | Backend-owned display value for the "reset to default" path; frontend may render it but must not infer it from unrelated constants once DTO data exists |
| `ApprovePasswordChangeRequestResponseDto.applied_password` | Nullable because only `reset_to_default` returns the applied temporary password; `change_to_requested` returns `null` |
| `AdminPasswordResetResponseDto.applied_password` | Non-null because admin direct reset always applies the default temporary password and the UI must show it only from the success response |
| `SystemUserListItemDto.password_change_request_*` | Nullable summary fields used for the admin table only; components must handle `null` safely |
| Mapper boundary | `mapUserPasswordChangeRequestInfoDto(...)` and `mapSystemUserListItemDto(...)` are the only snake_case -> camelCase conversion points for these password-request fields |

Additional rules:

- do not let components read fields such as `password_change_request_status` or `default_reset_password` directly
- keep `PasswordChangeRequestType` narrow to `"reset_to_default" | "change_to_requested"`
- do not widen approval responses to `any` just because one branch returns `applied_password = null`
- admin direct reset uses `/settings/users/{userId}/password-reset`; it does not require a pending request and should type its response separately from approval because `applied_password` is always present

### 4. Validation & Error Matrix

| Condition | Boundary | Expected behavior |
|---|---|---|
| Frontend sends `requestType` instead of `request_type` | API boundary | Request is wrong; keep DTO field names aligned with backend schema |
| Component consumes `dto.password_change_request_status` directly | mapper boundary is bypassed | Fix the caller to map first and use camelCase |
| Approval response is treated as always having `applied_password` | branch-specific contract is ignored | Handle `null` for `change_to_requested` |
| Admin direct reset response is treated like approval and nullable | UI can hide the password even though the reset succeeded | Use `AdminPasswordResetResponseDto` and render the non-null `applied_password` from that response |
| Password-request timestamps are `null` | rendering boundary | Render fallback text instead of an invalid date |
| DTO enum is widened to `string` | UI loses exhaustiveness for request-type/status rendering | Keep literal unions in `src/types/api.ts` and `src/types/models.ts` |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | Page submits `{ request_type: "change_to_requested", new_password: "..." }`, then maps the returned request snapshot into camelCase before rendering |
| Base | `password_change_request_status` is `null`, so the account card shows "no active request" without crashing |
| Base | Admin directly resets a member without a pending request, and the UI shows the returned default password from `AdminPasswordResetResponseDto.applied_password` |
| Bad | Component mixes snake_case and camelCase fields in the same branch and special-cases `applied_password` with `as any` |

### 6. Tests Required

- mapper test for `mapUserPasswordChangeRequestInfoDto(...)`, including all-null status fields and a populated `default_reset_password`
- mapper test for `mapSystemUserListItemDto(...)`, including password-request summary fields
- API payload test asserting the submit body uses `request_type` and `new_password`
- consumer test asserting approval-result UI handles `applied_password = null` safely
- consumer/API test asserting admin direct reset calls `/password-reset` and handles non-null `applied_password`

Assertion points:

- snake_case stays at the API boundary only
- frontend models expose camelCase only
- approval branches remain type-safe without `any`

### 7. Wrong vs Correct

#### Wrong

```ts
await apiRequest("/api/v1/settings/users/me/password-request", {
  method: "POST",
  body: JSON.stringify({
    requestType: "change_to_requested",
    newPassword,
  }),
});
```

#### Correct

```ts
await submitCurrentUserPasswordChangeRequest({
  request_type: "change_to_requested",
  new_password: newPassword,
});
```

---

## Scenario: AI Gateway Preset URL Boundary

### 1. Scope / Trigger

- Trigger: any change touching `aiSettingsCatalog.ts`, `AIGatewayFormDialog.vue`, AI gateway default URLs, model template `base_url_override`, or gateway vendor docs/placeholder text.
- Affected layers: frontend preset catalog -> gateway form defaults/placeholders -> backend stored gateway/model URLs -> runtime AI request URL construction.

### 2. Signatures

```ts
export const aiGatewayPresets: AIGatewayPreset[] = [
  {
    id: "openclaudecode-relay",
    payload: {
      vendor: "openclaudecode",
      official_url: "https://www.micuapi.ai",
      base_url: "https://www.micuapi.ai",
    },
  },
];

export const aiModelTemplates: AIModelTemplate[] = [
  {
    id: "openclaudecode-codex",
    payload: {
      base_url_override: "https://www.micuapi.ai/v1",
    },
  },
];
```

### 3. Contracts

| Boundary / field | Contract |
|---|---|
| OpenClaudeCode preset `official_url` | Must point to `https://www.micuapi.ai` after the provider migration |
| OpenClaudeCode preset `base_url` | Must point to `https://www.micuapi.ai`; do not reintroduce `www.openclaudecode.cn` or `api-slb.openclaudecode.cn` in new presets |
| OpenClaudeCode Codex `base_url_override` | Must keep `/v1` as `https://www.micuapi.ai/v1` because Responses runtime appends `/responses` |
| Gateway form placeholders | Must use the same current host as presets so manual creation does not guide users back to the old host |
| Vendor enum | The stable internal vendor remains `"openclaudecode"` even when the external service host is Micu API |

### 4. Validation & Error Matrix

| Condition | Boundary | Expected behavior |
|---|---|---|
| Preset host changes | frontend catalog boundary | Update gateway preset, Codex model template override, form placeholders, and catalog tests together |
| Existing stored gateways still use old host | backend migration boundary | Add an Alembic data migration rather than only changing frontend defaults |
| Responses template omits `/v1` | runtime URL boundary | Tests should catch missing `/v1` because requests would go to `/responses` instead of `/v1/responses` |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | `aiGatewayPresets` sets OpenClaudeCode `official_url` and `base_url` to `https://www.micuapi.ai`, and `aiModelTemplates` sets Codex `base_url_override` to `https://www.micuapi.ai/v1` |
| Base | Gateway form placeholders use the same Micu API host as the preset catalog, so manual gateway creation follows the current provider URL |
| Base | The internal vendor value stays `"openclaudecode"` even though the displayed provider host is Micu API |
| Bad | A template stores `base_url_override: "https://www.micuapi.ai"` for Responses-compatible models and drops the required `/v1` segment |
| Bad | Only label, docs text, or placeholders are changed, while the actual preset payload still writes the old OpenClaudeCode host |

### 6. Tests Required

- catalog test asserting OpenClaudeCode preset `official_url` and `base_url` equal `https://www.micuapi.ai`
- catalog test asserting OpenClaudeCode Codex template `base_url_override` equals `https://www.micuapi.ai/v1`
- backend AI client tests asserting runtime URLs are built from the Micu API host

Assertion points:

- no current frontend preset or placeholder guides users to `www.openclaudecode.cn` or `api-slb.openclaudecode.cn`
- Responses/Codex template overrides include `/v1`
- host migration does not widen `vendor` to arbitrary strings or rename `"openclaudecode"`
- frontend catalog tests fail if the real payload changes but labels remain current

### 7. Wrong vs Correct

#### Wrong

```ts
payload: {
  vendor: "openclaudecode",
  official_url: "https://www.micuapi.ai",
  base_url: "https://www.micuapi.ai",
  base_url_override: "https://www.micuapi.ai",
}
```

#### Correct

```ts
payload: {
  vendor: "openclaudecode",
  official_url: "https://www.micuapi.ai",
  base_url: "https://www.micuapi.ai",
  base_url_override: "https://www.micuapi.ai/v1",
}
```

#### Wrong

```ts
// Placeholder text is updated, but the actual preset still persists old rows for new gateways.
placeholder: "https://www.micuapi.ai"
payload: {
  base_url: "https://www.openclaudecode.cn",
}
```

#### Correct

```ts
placeholder: "https://www.micuapi.ai"
payload: {
  base_url: "https://www.micuapi.ai",
}
```

---

## Scenario: MP157 Device Management DTO Boundary

### 1. Scope / Trigger

- Trigger: any change touching `src/pages/DevicesPage.vue`, `DeviceFormDialog.vue`, `src/services/api/devices.ts`, device DTO/model types, or backend device schemas.
- Affected layers: FastAPI device response -> `src/types/api.ts` -> mapper -> `src/types/models.ts` -> table/delete confirmation/form payload.

### 2. Signatures

```ts
export type DeviceType = "mp157" | "f4" | "gateway" | "other";

export interface DeviceDto {
  id: number;
  device_code: string;
  name: string;
  device_type: DeviceType;
  status: DeviceStatus;
  record_count: number;
  image_count: number;
}

export interface DeviceModel {
  id: number;
  deviceCode: string;
  name: string;
  deviceType: DeviceType;
  status: DeviceStatus;
  recordCount: number;
  imageCount: number;
}

export interface DeviceDeleteResponseDto {
  message: string;
  deleted_record_count: number;
}

deleteDevice(deviceId: number): Promise<DeviceDeleteResponseDto>;
```

### 3. Contracts

| Boundary / field | Contract |
|---|---|
| `DeviceType` union | May remain wide for compatibility with old rows and backend enum values, but create/update UI must only submit `mp157` |
| `deviceTypeOptions` | Must only expose MP157 in device-management forms |
| `DeviceFormDialog` | Displays device type as read-only MP157 and submits `device_type: "mp157"` |
| `record_count` / `image_count` | Required DTO fields used to build delete confirmation text |
| `deleted_record_count` | DELETE response field used for the success toast |
| F4 data | Display copy should say F4 data arrives through MP157 serial upload and detection-record context, not as a separate cloud device |

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Backend returns `record_count > 0` | Delete confirm title/button should use "彻底删除" and mention record/image cleanup |
| Backend returns `record_count = 0` | Delete confirm can use normal device-delete wording |
| User confirms purge | Frontend calls `DELETE /api/v1/devices/{id}` and reloads the table |
| Backend rejects non-MP157 payload | Surface API error instead of widening frontend options |
| Old row has `device_type="f4"` | Type can parse it, but form should not offer F4 as a selectable target |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | Table row shows record count; delete dialog says F4 serial data will be removed with the MP157 detection records |
| Base | New device form shows read-only `MP157 主控设备` |
| Bad | Form reintroduces a device-type dropdown with STM32F4, gateway, and other options |

### 6. Tests Required

- frontend build/typecheck after changing DTOs and mapper
- backend service tests for MP157-only validation and purge response fields
- manual or browser check for `/devices` delete dialog at rows with and without records

Assertion points:

- `mapDeviceDto(...)` maps `record_count -> recordCount` and `image_count -> imageCount`
- `deleteDevice(...)` expects `deleted_record_count`
- no visible device form lets the user create F4/gateway/other devices

### 7. Wrong vs Correct

#### Wrong

```ts
export const deviceTypeOptions = [
  { label: "MP157", value: "mp157" },
  { label: "STM32F4", value: "f4" },
];
```

#### Correct

```ts
export const deviceTypeOptions = [
  { label: "MP157", value: "mp157" },
];
```
