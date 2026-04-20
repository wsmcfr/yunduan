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

## Forbidden Patterns

| Pattern | Why it is forbidden |
|---|---|
| Returning HTTP 200 with `{ "success": false }` for real failures | Breaks monitoring and client logic |
| Returning raw tracebacks to clients | Leaks internals |
| Catching and ignoring integration failures | Produces silent data loss |
| Mapping every failure to a generic 500 without context | Makes retries and diagnosis difficult |
| Yielding SSE events with raw `datetime` or other non-JSON values | The stream can fail before the frontend receives the first usable frame |
| Letting a generator exception terminate a stream without an `error` event | The browser only sees a broken response and the UI cannot explain what failed |

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
