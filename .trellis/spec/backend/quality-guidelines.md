# Quality Guidelines

> Backend quality standards and review criteria.

---

## Overview

Because the backend has not been scaffolded yet, quality in this project means two things:

1. stay aligned with the confirmed cloud stack (`FastAPI + SQLAlchemy + MySQL + COS`)
2. avoid turning planning snippets into production architecture

These rules are the minimum standard for the first backend implementation.

---

## Code Review Checklist

| Check | Expected standard |
|---|---|
| Layering | Routes stay thin; services own workflows; repositories own DB access |
| Type hints | Public functions and service entry points are typed |
| Config | Secrets and endpoints come from config or env, not inline literals |
| Payload contracts | Request and response schemas are explicit and reviewed when changed |
| Failure handling | Storage, AI, and DB failures are handled deliberately |
| Pagination | List endpoints are bounded and ordered |
| Naming | Files, modules, and DB entities follow the naming rules in this spec |

---

## Forbidden Patterns

| Pattern | Why it is forbidden |
|---|---|
| Shipping prototype code straight from Markdown into production | Prototype snippets are intentionally simplified |
| Writing business logic directly inside FastAPI route functions | Makes testing and reuse harder |
| Hard-coding COS credentials, AI API keys, or DB URLs | Unsafe and not deployable |
| Returning raw ORM objects without schema review | Leaks internal fields and couples layers |
| Using object storage as a database or vice versa | Breaks separation of concerns |

---

## Testing Expectations

### Bootstrap baseline

| Area | Minimum expectation |
|---|---|
| Route layer | Smoke tests for primary endpoints |
| Service layer | Unit tests for record creation, review decisions, and integration failure paths |
| Repository layer | Query tests for filtering, sorting, and pagination |
| Integration layer | Mocked tests for COS and AI review clients |

### Done means

- code follows the directory and naming guidelines
- lint and type checks pass
- changed API contracts are documented
- at least one good-path and one failure-path test exist for new backend behavior

---

## Examples

| Repository evidence | Quality takeaway |
|---|---|
| `工业缺陷检测系统完整方案.md` imports `database`, `models`, and `schemas` separately | The intended shape already separates concerns |
| `工业缺陷检测系统完整方案.md` uses paginated list retrieval with ordering | Bounded queries are already part of the plan |
| `STM32MP157DAA1工业缺陷检测系统综合方案.md` separates backend, storage, and cloud roles | Cross-layer boundaries matter from the first scaffold |

---

## Common Mistakes

| Mistake | Why it matters |
|---|---|
| Keeping all first-pass backend code in one file because "the project is still small" | Small projects become large quickly |
| Building frontend payloads straight from ORM fields without DTO review | Creates brittle coupling |
| Treating AI review as synchronous route-only logic | Makes latency and retries painful |
