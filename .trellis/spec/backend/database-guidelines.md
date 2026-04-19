# Database Guidelines

> Database conventions for the cloud backend.

---

## Overview

Current repository evidence points to the following baseline:

- ORM/query layer: `SQLAlchemy`
- Backend framework: `FastAPI`
- Database engine: `MySQL`
- Storage split: relational metadata in MySQL, files in object storage

Evidence:

- `工业缺陷检测系统完整方案.md` imports `Session`, `Base`, `engine`, `get_db`, `DetectionRecord`, `Part`, and `User`.
- The same file uses route-level filtering, ordering, pagination, and `db.refresh()` after insert.

There is no real migration setup in the repository yet. This file therefore records both current evidence and the minimum migration contract for the first scaffold.

---

## Query Patterns

| Rule | Reason |
|---|---|
| Use dependency-injected DB sessions (`Depends(get_db)`) at the route boundary | Matches the current FastAPI snippet and keeps session ownership explicit |
| Keep list endpoints paginated with `skip` and `limit` or an equivalent page abstraction | The planning snippet already uses bounded queries |
| Apply filters explicitly and sort list endpoints deterministically | The current record list example orders by detect time descending |
| Create records through ORM objects, then `commit()` and `refresh()` when generated fields are needed in the response | Matches the repository snippet |
| Move non-trivial query composition into repository modules once code is scaffolded | Prevents route handlers from becoming query builders |

### Current Example Patterns

| Example | Observation |
|---|---|
| `create_record` in `工业缺陷检测系统完整方案.md` | Creates ORM object, adds to session, commits, refreshes, returns generated ID |
| `get_records` in `工业缺陷检测系统完整方案.md` | Uses optional filters, counts total rows, applies descending order and pagination |
| `manual_review` in `工业缺陷检测系统完整方案.md` | Updates a single record by ID and commits the change |

---

## Migrations

### Current State

- No migration directory exists yet.
- The planning snippet uses `Base.metadata.create_all(bind=engine)`.

### Bootstrap Rule

| Rule | Status |
|---|---|
| `Base.metadata.create_all()` is acceptable only in throwaway prototypes and planning snippets | Allowed only during bootstrap |
| Real backend code must introduce Alembic together with the first executable backend scaffold | Required |
| Every schema change must be versioned by a migration file | Required |
| Never edit applied migrations in place after they are shared | Required |

---

## Naming Conventions

| Item | Convention |
|---|---|
| ORM class names | Singular `PascalCase` such as `DetectionRecord`, `Part`, `User` |
| Table names | Plural `snake_case` such as `detection_records`, `parts`, `users` |
| Columns | `snake_case` |
| Foreign keys | `<entity>_id` |
| Timestamp fields | `created_at`, `updated_at`, domain-specific timestamps such as `detect_time`, `review_time` |
| Enum-like string fields | Lowercase stable values such as `good`, `bad`, `pending`, `uncertain` |

---

## Common Mistakes

| Mistake | Why it is a problem |
|---|---|
| Treating `create_all()` as a migration strategy | Loses schema history and makes deployments unsafe |
| Returning unbounded list queries | Detection history will grow quickly |
| Storing large binary payloads directly in MySQL | Object storage is already part of the chosen architecture |
| Mixing file uploads, AI calls, and DB writes in a single transaction block | Makes failure handling and retries unclear |
| Reusing API DTO shapes as ORM models | Causes cross-layer coupling |
