# Error Handling

> Error handling conventions for the cloud backend.

---

## Overview

The only explicit backend error-handling example in the repository today is the planning `FastAPI` snippet that raises `HTTPException(status_code=404, detail="记录不存在")` when a record is missing.

This means the current evidence is:

- expected not-found conditions use HTTP 404
- request validation is expected to come from FastAPI/Pydantic
- a central error layer has not been implemented yet

The rules below preserve that behavior while defining the minimum production contract.

---

## Error Types

| Error type | Use for |
|---|---|
| `HTTPException` | Expected API-facing failures such as `404 Not Found`, `403 Forbidden`, `409 Conflict` |
| Validation errors | Request payload and query validation handled by FastAPI/Pydantic |
| Domain exceptions | Service-layer rule violations such as duplicate part type, unsupported review state, or illegal transition |
| Integration exceptions | COS upload failures, AI API failures, timeout failures, webhook failures |

### Bootstrap Rule

Until a central handler exists:

- route handlers may raise `HTTPException` directly for simple expected failures
- service and integration errors should still be raised distinctly, not collapsed into generic strings

---

## Error Handling Patterns

| Situation | Expected handling |
|---|---|
| Resource is missing | Raise `HTTPException(404, ...)` |
| Client sent invalid filters or payload | Let request validation fail with a `4xx` response |
| External service failed temporarily | Raise an integration-specific exception and return a retryable `5xx` or mapped `502/503` |
| Internal invariant is broken | Log with context and fail fast; do not silently continue |

### Catching Rules

- Catch exceptions at the boundary where you can add context or map them to a stable client response.
- Do not catch broad `Exception` just to return `"operation failed"` or `"unknown error"`.
- Do not swallow storage or AI review exceptions after partially writing database state.

---

## API Error Responses

### Current Evidence

The repository snippet returns FastAPI defaults (`detail` for `HTTPException`).

### Production Contract

As soon as real backend code exists, standardize on this error shape:

```json
{
  "code": "record_not_found",
  "message": "Detection record does not exist.",
  "details": null,
  "request_id": "..."
}
```

Required fields:

| Field | Purpose |
|---|---|
| `code` | Stable machine-readable identifier |
| `message` | Human-readable summary |
| `details` | Optional structured context |
| `request_id` | Trace correlation between logs and client reports |

---

## Scenario: SSE Streaming Error Boundary for AI Chat and Statistics

### 1. Scope / Trigger

- Trigger: any change to streaming AI endpoints, SSE helper functions, or payload fields emitted before the first delta chunk
- Affected layers: service generator -> SSE encoder -> FastAPI `StreamingResponse` -> browser SSE parser

### 2. Signatures

```py
def format_sse_event(*, event: str, payload: dict[str, Any]) -> str: ...

def build_sse_error_payload(error: AppError) -> dict[str, Any]: ...
```

```http
POST /api/v1/records/{record_id}/ai-chat/stream
POST /api/v1/statistics/ai-analysis/stream
```

```text
event: meta
data: {...}

event: delta
data: {"text":"..."}

event: done
data: {...}

event: error
data: {"status_code":500,"code":"...","message":"...","details":{...}}
```

### 3. Contracts

| Boundary | Contract |
|---|---|
| `meta` event | Must be emitted first so the frontend can initialize provider, suggestions, and context state |
| `delta` event | Must carry incremental assistant text only |
| `done` event | Must carry the final assembled answer and any final metadata snapshot |
| `error` event | Must be emitted for both mapped domain errors and unhandled generator failures |
| SSE payload encoding | Every payload must be JSON-serializable before `yield` |
| Datetime fields in payloads | Must be converted through `jsonable_encoder(...)` or an equivalent serializer before `json.dumps(...)` |

Additional rules:

- never assume a Python `datetime`, enum, or ORM-derived object can be passed directly to `json.dumps(...)`
- a failure while producing the first `meta` frame is still a user-visible streaming failure and must not fail silently
- unhandled exceptions inside the generator must be converted into a final `error` event whenever possible

### 4. Validation & Error Matrix

| Condition | Problem | Expected behavior |
|---|---|---|
| `meta` payload contains `datetime` | `json.dumps(...)` raises before the stream really starts | Serialize through `jsonable_encoder(...)` first |
| AI provider raises a mapped `AppError` mid-stream | Frontend gets an abruptly terminated stream | Emit `event: error` with stable `code`, `message`, and `status_code` |
| Unexpected exception happens inside the generator | Browser sees a `200` response with no usable body | Log the exception and emit `stream_internal_error` if the connection is still writable |
| Service emits raw ORM objects or non-JSON values | SSE helper crashes unpredictably | Convert to plain dict / list / primitive payloads before calling the encoder |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | `meta` includes record context with datetime fields, but `format_sse_event()` encodes it safely and the browser receives `meta -> delta -> done` |
| Base | No runtime model is selected, so the service still emits `meta`, text chunks, and `done` from the reserved or fallback path |
| Bad | The generator yields `meta` with raw datetimes, the connection returns `200`, and the frontend shows no answer because the stream died before the first usable event |

### 6. Tests Required

- SSE helper test asserting payloads containing `datetime` are encoded successfully
- service test asserting record chat stream emits `meta` before any `delta`
- service test asserting statistics stream emits `error` when an unhandled exception occurs
- integration test asserting the frontend-observed event order is `meta -> delta* -> done` on success

Assertion points:

- `meta` remains readable by the frontend when context includes timestamps
- `AppError` is mapped through `build_sse_error_payload(...)`
- unexpected exceptions surface as `code="stream_internal_error"` instead of silent disconnects

### 7. Wrong vs Correct

#### Wrong

```py
def format_sse_event(*, event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"
```

#### Correct

```py
from fastapi.encoders import jsonable_encoder

def format_sse_event(*, event: str, payload: dict[str, Any]) -> str:
    serialized_payload = json.dumps(jsonable_encoder(payload), ensure_ascii=False)
    return f"event: {event}\ndata: {serialized_payload}\n\n"
```

---

## Scenario: Statistics PDF Export Mode Error Boundary

### 1. Scope / Trigger

- Trigger: any change to `/api/v1/statistics/export-pdf`, `StatisticsExportService.build_pdf(...)`, the lightweight PDF renderer, or PDF dependency setup on the production host
- Affected layers: request schema -> export service mode dispatch -> WeasyPrint / ReportLab renderer -> production response behavior

### 2. Signatures

```py
class StatisticsExportPdfRequest(BaseModel):
    export_mode: Literal["visual", "lightweight"] = "visual"
    include_ai_analysis: bool = True
    include_sample_images: bool = True
    sample_image_limit: int = Field(default=4, ge=0, le=8)
```

```py
def build_pdf(self, payload: StatisticsExportPdfRequest) -> tuple[bytes, str]: ...
def _load_reportlab(self) -> dict[str, Any]: ...
def _ensure_font_registered(self, *, pdfmetrics: Any, unicode_cid_font: Any) -> str: ...
```

```http
POST /api/v1/statistics/export-pdf
```

### 3. Contracts

| Boundary | Contract |
|---|---|
| `export_mode="visual"` | Must stay on the WeasyPrint HTML rendering path |
| `export_mode="lightweight"` | Must dispatch directly to the ReportLab-based renderer and must not continue into the HTML / sample-image path |
| ReportLab dependency | Missing `reportlab` must surface as a stable integration error, not an unhandled traceback |
| WeasyPrint dependency | Missing `weasyprint` must surface as a stable integration error, not an unhandled traceback |
| Font registration | `pdfmetrics.getRegisteredFontNames()` must be treated as a sequence of font-name strings |
| Lightweight performance path | Lightweight export must not load COS sample images when the mode is `lightweight` |

Additional rules:

- predictable renderer setup failures belong to `IntegrationError`, not raw `500 Internal Server Error`
- lightweight-mode regressions should be caught by service/unit tests before deployment
- frontend export benchmarking should use `include_ai_analysis=false` when the goal is renderer timing only

### 4. Validation & Error Matrix

| Condition | Problem | Expected behavior |
|---|---|---|
| `reportlab` is not installed | Lightweight export cannot initialize its renderer | Raise `IntegrationError(code="lightweight_pdf_renderer_unavailable", ...)` |
| `weasyprint` is not installed | Visual export cannot render HTML to PDF | Raise `IntegrationError(code="pdf_renderer_unavailable", ...)` |
| Lightweight mode still calls sample-image loading | Export becomes slower and loses its intended lightweight behavior | Dispatch directly to the lightweight renderer before sample-image loading |
| Font registration code treats registered font names as objects with `.fontName` | The route returns a raw `500` during lightweight export | Treat `getRegisteredFontNames()` as plain strings and keep the path test-covered |
| Visual benchmark keeps AI analysis enabled | Timing includes model latency instead of renderer cost | Disable AI analysis during renderer benchmark runs |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | `export_mode="lightweight"` skips sample images, initializes ReportLab, accepts string font names, and returns a PDF response |
| Base | `export_mode="visual"` still uses WeasyPrint and embeds only the explicitly requested sample images |
| Bad | A lightweight-renderer refactor accesses `font.fontName`, triggers `AttributeError`, and the API returns a plain `500 Internal Server Error` |

### 6. Tests Required

- service test asserting `export_mode="lightweight"` dispatches to the lightweight renderer
- service test asserting lightweight mode does not call sample-image loading
- renderer test asserting missing `reportlab` maps to `lightweight_pdf_renderer_unavailable`
- renderer test asserting `_ensure_font_registered(...)` accepts string names returned by `getRegisteredFontNames()`
- existing visual-path test coverage must still protect cached AI reuse and visual sample-image selection rules

Assertion points:

- the lightweight renderer receives `overview` and `ai_analysis` directly from `StatisticsExportService`
- `_load_sample_images(...)` is not called for lightweight mode
- missing dependencies map to stable error codes instead of plain tracebacks
- registered font names such as `"STSong-Light"` do not require `.fontName` access

### 7. Wrong vs Correct

#### Wrong

```py
registered_fonts = {item.fontName for item in pdfmetrics.getRegisteredFontNames()}
if font_name not in registered_fonts:
    pdfmetrics.registerFont(unicode_cid_font(font_name))
```

#### Correct

```py
registered_fonts = set(pdfmetrics.getRegisteredFontNames())
if font_name not in registered_fonts:
    pdfmetrics.registerFont(unicode_cid_font(font_name))
```

```py
if payload.export_mode == "lightweight":
    return StatisticsLightweightPdfRenderer().build_pdf(
        overview=overview,
        ai_analysis=ai_analysis,
    )
```

---

## Forbidden Patterns

| Pattern | Why it is forbidden |
|---|---|
| Returning HTTP 200 with `{ "success": false }` for real failures | Breaks monitoring and client logic |
| Returning raw tracebacks to clients | Leaks internals |
| Catching and ignoring integration failures | Produces silent data loss |
| Mapping every failure to a generic 500 without context | Makes retries and diagnosis difficult |
| Yielding SSE events with raw `datetime` or other non-JSON values | The stream can fail before the frontend receives the first usable frame |
| Letting a generator exception terminate a stream without an `error` event | The browser only sees a broken response and the UI cannot explain what failed |
| Letting predictable PDF renderer setup failures bubble out as plain `500` errors | The client cannot distinguish dependency issues, renderer regressions, and temporary deployment mistakes |

---

## Examples

| Repository evidence | What it shows |
|---|---|
| `工业缺陷检测系统完整方案.md` `get_record_detail` | Missing record maps to a `404` via `HTTPException` |
| `工业缺陷检测系统完整方案.md` `manual_review` | Same missing-record path is handled consistently |
| `工业缺陷检测系统完整方案.md` `ai_analyze` | Integration boundaries exist and should not be treated as generic route logic |

---

## Common Mistakes

| Mistake | Why it matters |
|---|---|
| Putting storage, AI review, and DB writes in one route without staged failure handling | Hard to recover from partial failures |
| Using human text as the only error identifier | Frontend cannot branch reliably |
| Translating every error too early in lower layers | Reduces observability and reuse |
| Assuming third-party library helper APIs return rich objects without checking the actual return type | Small renderer regressions can escape as production-only `500` errors |

---

## Scenario: Public Auth and Password Reset Error Boundary

### 1. Scope / Trigger

- Trigger: any change to `/api/v1/auth/login`, `/register`, `/logout`, `/forgot-password`, `/reset-password`, or `/me`
- Affected layers: auth route -> JWT/cookie helpers -> auth service -> password-reset mail integration -> frontend auth forms

### 2. Signatures

```http
POST /api/v1/auth/login
POST /api/v1/auth/register
GET /api/v1/auth/me
POST /api/v1/auth/logout
POST /api/v1/auth/forgot-password
POST /api/v1/auth/reset-password
```

```py
def create_access_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, datetime]: ...

def validate_token_freshness(
    token_payload: dict[str, Any],
    *,
    password_changed_at: datetime | None,
) -> None: ...
```

```json
{
  "session_expires_at": "2026-04-22T02:05:43.908803Z",
  "user": {
    "id": 5,
    "username": "probe1776737145",
    "password_changed_at": "2026-04-21T02:05:44"
  }
}
```

### 3. Contracts

| Situation | Expected handling |
|---|---|
| Invalid login credentials | `401` with stable code such as `invalid_credentials` |
| Public registration disabled | `403` with stable code such as `public_registration_disabled` |
| Password-reset mail channel unavailable | Stable client-facing error such as `password_reset_channel_unavailable` |
| Forgot-password request for nonexistent email | Return the same generic success message as an existing email when the channel is enabled |
| Invalid reset token | `401` with `invalid_password_reset_token` |
| Expired reset token | `401` with `password_reset_token_expired` |
| Logout without a current cookie | Still return a normal success response after clearing the cookie |
| Register/login returns a fresh session cookie | The same cookie must be accepted by the immediate next `/auth/me` or protected API request |
| Token freshness check compares JWT `issued_at_ms` with `password_changed_at` | The comparison may tolerate a tiny precision skew caused by DB timestamp rounding, ORM serialization, or JWT timestamp granularity |
| `token_revoked` | Only valid when the token was materially issued before the latest password change, not when both timestamps describe the same auth event |

Additional rules:

- forgot-password must not leak whether an email exists in the system once the mail channel is enabled
- backend mail delivery failures should not leave a live reset token in the database without operator visibility
- resetting the password must clear the browser auth cookie in the HTTP response so the UI cannot keep using a stale session accidentally
- do not use a zero-skew freshness rule if `password_changed_at` and JWT issue time come from different precision domains
- freshly registered users must not be forced to log out and log back in only because `password_changed_at` was rounded slightly after the issued token timestamp

### 4. Validation & Error Matrix

| Condition | Problem | Expected behavior |
|---|---|---|
| SMTP config is missing | User cannot actually receive a reset link | Return a stable “channel unavailable” error instead of a generic traceback |
| Mail send fails after token creation | Database may contain an undispatched valid token | Clear token state and re-raise the integration error |
| User submits an expired token | Old link still exists in inbox | Clear the stored token state and return `password_reset_token_expired` |
| Browser calls logout after cookie already expired | Frontend still wants a clean local logout flow | Return success and clear any remaining cookie metadata |
| Register succeeds, but the next protected request arrives milliseconds later with the same session cookie | DB/JWT precision mismatch can make the token look older than `password_changed_at` | Accept the request when the delta stays within the allowed skew window |
| Token issue time is clearly older than the latest password change | This is a real stale-session case | Reject with `401 token_revoked` |
| Request has no cookie and no bearer token | Backend cannot identify a session | Reject with `401 missing_token` |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | `POST /auth/register` returns `Set-Cookie`, then the browser immediately calls `/auth/me` and receives `200` with the same new user |
| Base | Historical user has `password_changed_at = null`, so `/auth/me` only depends on token validity and user activity state |
| Bad | Registration creates `password_changed_at` with slightly newer DB precision than JWT `issued_at_ms`, and an exact comparison revokes the brand-new session |

### 6. Tests Required

- auth integration test asserting `register -> Set-Cookie -> /auth/me` succeeds without a forced re-login
- helper test asserting `validate_token_freshness(...)` accepts a sub-second skew between `issued_at_ms` and `password_changed_at`
- helper test asserting a materially older token is still rejected with `token_revoked`
- forgot-password test asserting mail-send failure clears the stored reset-token state
- logout test asserting the route still returns success when no live cookie remains

Assertion points:

- newly issued register/login sessions survive the first protected request
- the freshness guard still blocks truly stale sessions
- token/cookie absence is distinguishable from token revocation by stable error codes
- password reset failure paths do not leave a valid undispatched reset token behind

### 7. Wrong vs Correct

#### Wrong

```py
normalized_password_changed_at = _normalize_datetime(password_changed_at)
if issued_at < normalized_password_changed_at:
    raise UnauthorizedError(code="token_revoked", message="登录状态已失效，请重新登录。")
```

#### Correct

```py
TOKEN_FRESHNESS_SKEW = timedelta(seconds=1)

normalized_password_changed_at = _normalize_datetime(password_changed_at)
if issued_at + TOKEN_FRESHNESS_SKEW < normalized_password_changed_at:
    raise UnauthorizedError(code="token_revoked", message="登录状态已失效，请重新登录。")
```
