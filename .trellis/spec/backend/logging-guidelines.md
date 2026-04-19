# Logging Guidelines

> Logging conventions for the cloud backend.

---

## Overview

No backend logging implementation exists in the repository yet. This file is therefore a bootstrap observability contract derived from the current architecture:

- HTTP APIs for records, review, devices, and administration
- object storage uploads
- AI review requests
- device-to-cloud record ingestion

The project should start with structured logs from day one. Plain ad-hoc print statements are not enough for uploads, AI review retries, or production support.

---

## Log Levels

| Level | Use for |
|---|---|
| `INFO` | Request completion, record creation, manual review completion, upload success, worker lifecycle |
| `WARN` | Retryable external failure, invalid but non-fatal device payload, unexpected empty result sets, degraded dependency |
| `ERROR` | Failed upload, failed AI review, failed DB transaction, unhandled exceptions, corrupted payloads |
| `DEBUG` | Local development only; payload shape debugging, query timing, retry attempts |

Do not log normal request flow at `ERROR`.

---

## Structured Logging

Every non-trivial log entry should include as many of these fields as are available:

| Field | Why it matters |
|---|---|
| `event` | Stable log name such as `record.created` or `ai_review.failed` |
| `request_id` | Correlates client reports with logs |
| `record_id` | Identifies the detection record |
| `part_type` | Helps diagnose class-specific issues |
| `device_id` | Links uploads to the edge device |
| `object_key` | Identifies the stored file in COS |
| `duration_ms` | Helps spot latency regressions |
| `status_code` | Useful for API summaries |

---

## What to Log

Use stable event names instead of free-form sentences:

| Event | When to log |
|---|---|
| `record.created` | Detection record inserted successfully |
| `record.upload_failed` | Storage upload failed |
| `record.review_completed` | Manual review saved |
| `ai_review.started` | Outbound AI review request begins |
| `ai_review.failed` | AI review request failed |
| `device.sync_received` | Edge device pushed a new detection result |
| `auth.login_failed` | Login failure |

Current repository evidence is architectural rather than executable:

| Repository evidence | Logging implication |
|---|---|
| `工业缺陷检测系统完整方案.md` record creation route | Log record creation and object storage upload outcome separately |
| `工业缺陷检测系统完整方案.md` AI analyze route | Log outbound provider call lifecycle and failure reason |
| `STM32MP157DAA1工业缺陷检测系统综合方案.md` cloud stack | Log storage, review, and upload workflow with record IDs and durations |

---

## What NOT to Log

Never log:

| Data | Reason |
|---|---|
| Full access tokens or secret keys | Credential leakage |
| Raw uploaded image bytes | Huge payloads and privacy risk |
| Full AI provider request or response bodies in production | May contain sensitive prompts or billable payloads |
| User passwords or password hashes | Security violation |

If debugging requires payload inspection, log metadata only:

- content type
- file size
- record ID
- provider response status

---

## Common Mistakes

| Mistake | Why it is a problem |
|---|---|
| Using `print()` in production paths | No structure, no filtering, poor traceability |
| Logging Chinese or English free-form sentences only | Hard to search or aggregate |
| Logging success and failure with the same vague message | Makes alerting unreliable |
| Logging request data without redaction | Leaks secrets and bloats logs |
