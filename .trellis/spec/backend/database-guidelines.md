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

---

## Scenario: Station-Inside Password Change Approval Storage

### 1. Scope / Trigger

- Trigger: any change to station-inside password approval, admin approval/rejection, user deletion with pending password requests, or the user-table snapshot fields introduced by `20260421_0008_user_password_change_requests.py`
- Affected layers: Alembic migration -> `users` ORM columns -> `SystemUserService` -> settings schemas/routes

### 2. Signatures

```py
# alembic/versions/20260421_0008_user_password_change_requests.py
users.password_change_request_status VARCHAR(32) NULL
users.password_change_request_type VARCHAR(32) NULL
users.password_change_requested_password_encrypted TEXT NULL
users.password_change_requested_at DATETIME NULL
users.password_change_reviewed_at DATETIME NULL
```

```py
DEFAULT_APPROVED_RESET_PASSWORD = "Q123456@"

def submit_password_change_request(
    *,
    company_id: int | None,
    user_id: int,
    request_type: str,
    new_password: str | None,
) -> User: ...

def approve_password_change_request(
    *,
    company_id: int | None,
    current_user_id: int,
    user_id: int,
) -> tuple[User, str | None]: ...

def reject_password_change_request(
    *,
    company_id: int | None,
    current_user_id: int,
    user_id: int,
) -> User: ...
```

### 3. Contracts

| Field / storage boundary | Contract |
|---|---|
| `users.password_hash` | Remains the only persistent password credential field; it is written only when approval really applies a password |
| `users.password_change_request_status` | Snapshot state field: `pending`, `approved`, `rejected`, or `NULL` when no request exists yet |
| `users.password_change_request_type` | Snapshot type field: `reset_to_default` or `change_to_requested`; it remains available for audit after approval/rejection |
| `users.password_change_requested_password_encrypted` | Stores only the encrypted requested password for `change_to_requested`; must be `NULL` for `reset_to_default` and must be cleared after approval/rejection |
| `users.password_change_requested_at` | UTC timestamp when the latest request snapshot was created |
| `users.password_change_reviewed_at` | UTC timestamp when an admin approved or rejected the latest request |
| `DEFAULT_APPROVED_RESET_PASSWORD` | Service constant only; do not persist this literal as plaintext in the database snapshot |
| `users.password_changed_at` | Updates only when approval actually changes the effective password; request submission or rejection must not advance it |
| `users.password_reset_*` | Existing email-reset token state must be cleared when a password request is approved so old reset links cannot remain valid |

Additional rules:

- each user may have only one active `pending` password-request snapshot at a time
- this flow uses a snapshot on `users`, not a separate history table; do not accumulate multiple pending rows elsewhere without a new code-spec update
- `change_to_requested` must pass through `SecretCipher` before storage; plaintext requested passwords must never touch the database
- approval and rejection must keep `requested_at` for traceability while clearing the encrypted pending secret

### 4. Validation & Error Matrix

| Condition | Problem | Expected behavior |
|---|---|---|
| User submits a second request while one is already pending | Pending target password can be silently overwritten | Reject the write and preserve the existing snapshot |
| `reset_to_default` request stores an encrypted payload | Unnecessary secret retention | Persist `password_change_requested_password_encrypted = NULL` |
| `change_to_requested` approval finds no encrypted payload | The snapshot is corrupt and cannot safely apply a password | Fail approval and leave `password_hash` unchanged |
| Request is rejected | Password should not change | Keep `password_hash` and `password_changed_at` unchanged, set status to `rejected`, and clear encrypted pending payload |
| Request is approved | New password becomes effective | Update `password_hash`, set `password_changed_at = reviewed_at`, clear email reset token state, clear encrypted pending payload |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | User submits `change_to_requested`, the DB stores only encrypted pending text, admin approval writes a new `password_hash`, and the encrypted payload is cleared |
| Base | User submits `reset_to_default`, so the DB stores `pending + reset_to_default + NULL encrypted payload`, and approval returns the default password text only in the transient response |
| Bad | Submitted password is written into `password_hash` or a plaintext temp column before approval, effectively bypassing the admin gate |

### 6. Tests Required

- migration smoke test asserting the five password-request columns exist after `20260421_0008`
- service test asserting `submit_password_change_request(..., request_type="change_to_requested")` stores only encrypted pending text
- service test asserting duplicate pending submit is rejected without overwriting the first snapshot
- service test asserting approval updates `password_hash` and `password_changed_at` and clears `password_reset_*`
- service test asserting rejection clears the encrypted payload without changing the effective password

Assertion points:

- only one pending snapshot exists per user
- no plaintext requested password is persisted
- approval and rejection both clear `password_change_requested_password_encrypted`
- `password_changed_at` advances only on approval

### 7. Wrong vs Correct

#### Wrong

```py
# Password changes immediately at submit time, so admin approval becomes meaningless.
user.password_hash = hash_password(new_password)
user.password_change_request_status = "pending"
```

#### Correct

```py
encrypted_password = self.secret_cipher.encrypt(new_password)
self._set_password_request_snapshot(
    user=user,
    status="pending",
    request_type="change_to_requested",
    encrypted_password=encrypted_password,
    requested_at=requested_at,
    reviewed_at=None,
)
```
