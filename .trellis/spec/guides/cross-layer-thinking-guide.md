# Cross-Layer Thinking Guide

> **Purpose**: Think through data flow across layers before implementing.

---

## The Problem

**Most bugs happen at layer boundaries**, not within layers.

Common cross-layer bugs:

- API returns format A, frontend expects format B
- database stores X, service transforms to Y, but loses data
- multiple layers implement the same logic differently

---

## Before Implementing Cross-Layer Features

### Step 1: Map the Data Flow

Draw out how data moves:

```text
Source -> Transform -> Store -> Retrieve -> Transform -> Display
```

For each arrow, ask:

- what format is the data in?
- what could go wrong?
- who is responsible for validation?

### Step 2: Identify Boundaries

| Boundary | Common Issues |
|----------|---------------|
| API <-> Service | Type mismatches, missing fields |
| Service <-> Database | Format conversions, null handling |
| Backend <-> Frontend | Serialization, date formats |
| Component <-> Component | Props shape changes |

### Step 3: Define Contracts

For each boundary:

- what is the exact input format?
- what is the exact output format?
- what errors can occur?

---

## Common Cross-Layer Mistakes

### Mistake 1: Implicit Format Assumptions

**Bad**: Assuming date format without checking

**Good**: Explicit format conversion at boundaries

### Mistake 2: Scattered Validation

**Bad**: Validating the same thing in multiple layers

**Good**: Validate once at the entry point

### Mistake 3: Leaky Abstractions

**Bad**: Component knows about database schema

**Good**: Each layer only knows its neighbors

---

## Checklist for Cross-Layer Features

Before implementation:

- [ ] Mapped the complete data flow
- [ ] Identified all layer boundaries
- [ ] Defined format at each boundary
- [ ] Decided where validation happens
- [ ] Verified the final mounted backend path after all router prefixes are applied
- [ ] Verified each event timestamp means a different lifecycle step, not the same moment with different names

After implementation:

- [ ] Tested with edge cases (null, empty, invalid)
- [ ] Verified error handling at each boundary
- [ ] Checked data survives round-trip
- [ ] Verified the first SSE frame can be serialized before the browser waits on streaming UI initialization
- [ ] Verified approval-flow features allow only one pending snapshot per entity and clear encrypted pending secrets on terminal states such as approve/reject

---

## Router Aggregation Checklist

When frontend services call backend APIs, do not infer the final path from:

- the route file name
- the feature folder name
- a tag name in OpenAPI

Instead, verify the fully mounted path from the top-level router aggregation.

Example from this project:

- `reviews.router` is mounted without a `/reviews` prefix
- the final manual-review path is `POST /api/v1/records/{id}/manual-review`
- `/api/v1/reviews/records/{id}/manual-review` is wrong even though the file lives in `routes/reviews.py`

Quick check:

1. Read the route definition.
2. Read the top-level `include_router(...)` call.
3. Concatenate the real prefixes.
4. Match the frontend service path to that mounted result.

---

## Event-Time Checklist

When a feature stores multiple timestamps, require a sentence-level definition for each one before coding.

Detection-record example:

- `captured_at`: sample image capture time
- `detected_at`: local MP157 detection completion time
- `uploaded_at`: application-side upload or metadata registration completion time
- `storage_last_modified`: COS object last-modified time from storage metadata

Cross-layer warning:

- do not collapse these fields into one generic `time`
- do not reuse `uploaded_at` as a fake storage timestamp
- do not assume object storage metadata replaces application event timestamps
- do not send Element Plus local datetime strings such as `2026-04-20T10:00:00` across the API boundary without converting them to timezone-aware ISO first

If a page, API, or database field cannot explain which lifecycle step it represents, the contract is still incomplete.

### Frontend Datetime Submit Boundary

When the frontend uses `ElDatePicker` with `value-format="YYYY-MM-DDTHH:mm:ss"`, the emitted value is a local datetime string without timezone metadata.

Required contract in this project:

- input owner: `frontend/src/features/**` form components
- normalization owner: `frontend/src/utils/form.ts`
- outbound API payload: timezone-aware ISO string such as `2026-04-20T02:00:00.000Z`
- backend request field: `captured_at`, `detected_at`, `uploaded_at`, `reviewed_at`, or `last_seen_at`

Validation matrix:

| Condition | Expected handling |
|---|---|
| User clears the field | Normalize to `null` when the field is optional |
| User selects a local datetime | Convert it to ISO before `JSON.stringify(payload)` |
| Caller already has an ISO string with timezone | Preserve the same instant and emit normalized ISO |
| Invalid datetime text reaches the helper | Return `null` or block submit; do not send ambiguous raw text |

Good / Base / Bad:

| Case | Example |
|---|---|
| Good | `normalizeOptionalDateTime("2026-04-20T10:00:00")` returns `new Date(2026, 3, 20, 10, 0, 0).toISOString()` |
| Base | optional `uploaded_at` is blank, so request payload sends `null` |
| Bad | component sends `"2026-04-20T10:00:00"` directly to FastAPI and assumes backend or browser will interpret timezone the same way |

---

## SSE First-Frame Checklist

When a feature depends on streaming UI initialization, the first SSE frame becomes a cross-layer contract, not just an implementation detail.

Checklist:

- confirm the frontend can render its initial streaming state from `meta` alone
- confirm the backend `meta` payload contains only JSON-serializable values
- confirm generator exceptions can still surface as a structured `error` event
- confirm the frontend patches streamed content by a stable message id rather than timestamp coincidence

Typical failure pattern in this project:

- backend returns `200`
- `meta` serialization fails before the first usable frame
- frontend appears to “not output anything” even though the request reached the route

If the product relies on streamed chat or streamed statistics analysis, treat the first emitted event as a required contract review item.

---

## When to Create Flow Documentation

Create detailed flow docs when:

- feature spans 3+ layers
- multiple teams are involved
- data format is complex
- feature has caused bugs before
