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

---

## Scenario: User Credential and Password Reset Storage

### 1. Scope / Trigger

- Trigger: any change to user authentication, login session invalidation, registration, or forgot-password flows
- Affected layers: user ORM -> Alembic migration -> auth service -> auth route schemas

### 2. Contracts

| Field | Contract |
|---|---|
| `users.password_hash` | Stores only the adaptive password hash, never plaintext |
| `users.email` | Unique when present, nullable for historical accounts created before email-backed recovery existed |
| `users.password_changed_at` | Tracks when password material last changed so older sessions can be invalidated |
| `users.password_reset_token_hash` | Stores only the reset-token hash, never the raw token sent by email |
| `users.password_reset_sent_at` / `users.password_reset_expires_at` | Bound cooldown and expiration for password recovery |

Additional rules:

- password reset must overwrite or clear the previous token state rather than accumulating multiple plaintext tokens
- adaptive password-hash upgrades may happen transparently on login, but they must still write only the new hash format
- any new auth field must land through Alembic, not through ad-hoc manual SQL in deployment notes

### 3. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | Database stores `password_hash`, `password_changed_at`, and `password_reset_token_hash`, while the raw reset link only exists transiently during email send |
| Base | Legacy admin user has `email = null` but still logs in successfully |
| Bad | Raw password-reset token or plaintext password is inserted into `users` for “convenience” debugging |

### 4. Tests Required

- register test asserting password hashes are not equal to the submitted password
- forgot-password test asserting only a token hash is persisted
- reset-password test asserting old password no longer authenticates
- session-validation test asserting tokens issued before `password_changed_at` are rejected
