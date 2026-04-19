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

## Forbidden Patterns

| Pattern | Why it is forbidden |
|---|---|
| Returning HTTP 200 with `{ "success": false }` for real failures | Breaks monitoring and client logic |
| Returning raw tracebacks to clients | Leaks internals |
| Catching and ignoring integration failures | Produces silent data loss |
| Mapping every failure to a generic 500 without context | Makes retries and diagnosis difficult |

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
