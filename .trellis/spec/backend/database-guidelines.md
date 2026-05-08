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

## Scenario: MP157 Device Registry and Purge Delete

### 1. Scope / Trigger

- Trigger: any change touching `Device`, `DeviceService`, `/api/v1/devices`, device DTOs, or frontend device management.
- Affected layers: device ORM -> repository usage summary and purge queries -> service validation/COS cleanup -> route schemas -> frontend DTO/model/table/delete confirmation.

### 2. Signatures

```py
class DeviceCreateRequest(BaseModel):
    device_code: str
    name: str
    device_type: DeviceType = DeviceType.MP157
    status: DeviceStatus = DeviceStatus.OFFLINE
    firmware_version: str | None
    ip_address: str | None
    last_seen_at: datetime | None

class DeviceResponse(ORMBaseModel):
    record_count: int = 0
    image_count: int = 0

class DeviceDeleteResponse(BaseModel):
    message: str
    deleted_record_count: int

def delete_device(self, *, company_id: int, device_id: int) -> int: ...
def list_part_ids_by_record_ids(self, *, company_id: int, record_ids: list[int]) -> list[int]: ...
def delete_unreferenced_parts_by_ids(self, *, company_id: int, part_ids: list[int]) -> int: ...
def delete_unused_simulated_parts(self, *, company_id: int) -> int: ...
```

```http
GET /api/v1/devices
POST /api/v1/devices
PUT /api/v1/devices/{device_id}
DELETE /api/v1/devices/{device_id}
```

### 3. Contracts

| Boundary / field | Contract |
|---|---|
| `device_type` | Cloud device records are MP157-only. F4 is not an independent cloud-managed device; its serial data is stored in detection-record context fields through MP157 uploads |
| `DeviceCreateRequest.device_type` | Defaults to `mp157`; service rejects `f4`, `gateway`, and `other` with `device_type_must_be_mp157` |
| `DeviceUpdateRequest.device_type` | If present, must be `mp157`; changing a device into F4/gateway/other is forbidden |
| `DeviceResponse.record_count` | Count of detection records linked to this MP157, used for delete confirmation |
| `DeviceResponse.image_count` | Count of file-object metadata linked through the device's detection records |
| `DELETE /devices/{id}` | Purge delete: delete COS objects first, then file metadata, review records, detection records, and finally the device in one DB transaction |
| Orphan part cleanup after device delete | Before deleting detection records, collect the affected `part_id` values. After deleting those records, delete only those affected parts that no longer have any detection-record reference in the same company |
| `PartService.list_parts(...)` legacy cleanup | Before listing parts, delete `SIM-PART-*` rows in the current company that have no detection-record reference |
| Tenant boundary | Every query and delete path must constrain by `company_id` |

Additional rules:

- object storage cleanup must happen before deleting DB metadata; if COS deletion raises `IntegrationError`, do not commit DB deletion
- deletion returns the number of purged detection records so the UI can report the result
- orphan part cleanup is a scoped follow-up to device delete, not a full-table sweep; newly created manual part definitions that never had records must not be deleted by this path
- if an affected part is still referenced by another device's detection records, keep the part so the remaining history stays traceable
- the list-time legacy cleanup is intentionally limited to `SIM-PART-*` rows, so refreshing the parts page can remove historical simulator leftovers without deleting ordinary manually created part definitions
- do not introduce F4 status management into cloud device pages unless the data model is deliberately redesigned

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Create/update payload uses `device_type="f4"` | Reject with `BadRequestError(code="device_type_must_be_mp157")` |
| Delete target does not exist in current company | Reject with `NotFoundError(code="device_not_found")` |
| Device has no detection records | Delete the device and return `deleted_record_count = 0` |
| Device has detection records, reviews, and file objects | Delete COS objects, file metadata, reviews, records, and device; return deleted record count |
| Deleted device was the only remaining source for a part | Delete the now-unreferenced part after its detection records are removed |
| Deleted device shared a part with another device | Keep the part because another detection record still references it |
| Parts page lists historical `SIM-PART-*` leftovers with zero records | Delete those unused simulated parts before returning the list |
| Manually created part has zero records | Keep it; it may be a valid master-data entry waiting for device upload |
| COS object deletion fails | Raise integration error and leave DB rows untouched |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | MP157 list row shows `record_count=3`, UI confirms purge, backend deletes those records, removes parts that became unreferenced, and returns `deleted_record_count=3` |
| Base | A newly created MP157 with no records can be deleted with normal confirmation |
| Base | Opening `/parts` removes unused `SIM-PART-*` legacy rows while keeping unused `PART-*` manual rows |
| Bad | Device delete removes records but leaves stale `parts` rows with `record_count=0`, `image_count=0`, and no source device |

### 6. Tests Required

- service test rejecting non-MP157 create and update payloads
- service test deleting an unreferenced device
- service test purging a referenced device and asserting detection records, file objects, reviews, and COS objects are deleted
- service test attaching `record_count` and `image_count` to listed devices
- service test deleting a device that leaves one affected part unreferenced and one affected part still shared by another device
- part service test asserting list-time cleanup removes unused `SIM-PART-*` rows only
- route smoke test asserting `DELETE /api/v1/devices/{device_id}` is mounted

Assertion points:

- `DeviceService.delete_device(...)` returns the number of deleted detection records
- device purge stays inside the current company
- affected parts are removed only when no remaining detection record references them
- `PartService.list_parts(...)` removes historical unused `SIM-PART-*` rows but keeps ordinary zero-record parts
- frontend DTOs include `record_count`, `image_count`, and `deleted_record_count`

### 7. Wrong vs Correct

#### Wrong

```py
device = Device(device_type=DeviceType.F4, ...)
self.device_repository.delete(device)
self.db.commit()
```

#### Correct

```py
self._ensure_mp157_device_type(payload.device_type)
record_ids = self.device_repository.list_detection_record_ids(
    company_id=company_id,
    device_id=device_id,
)
affected_part_ids = self.device_repository.list_part_ids_by_record_ids(
    company_id=company_id,
    record_ids=record_ids,
)
self._delete_device_cos_objects(company_id=company_id, record_ids=record_ids)
self.device_repository.delete_detection_records_by_ids(
    company_id=company_id,
    record_ids=record_ids,
)
self.device_repository.delete_unreferenced_parts_by_ids(
    company_id=company_id,
    part_ids=affected_part_ids,
)
self.device_repository.delete(device)
self.db.commit()
```

---

## Scenario: Detection Record Row Delete

### 1. Scope / Trigger

- Trigger: any change touching `DetectionRecord`, `RecordService.delete_record(...)`, `/api/v1/records/{record_id}`, file-object cleanup, or frontend record-row delete.
- Affected layers: record ORM aggregate -> repository delete -> service COS cleanup -> admin route dependency -> frontend delete API and table refresh.

### 2. Signatures

```py
def delete_record(self, *, company_id: int, record_id: int) -> None: ...

def _delete_record_cos_objects(self, *, record: DetectionRecord) -> None: ...

def delete(self, record: DetectionRecord) -> None: ...
```

```http
DELETE /api/v1/records/{record_id}
```

```ts
deleteRecord(recordId: number): Promise<ApiMessageResponseDto>;
```

### 3. Contracts

| Boundary / field | Contract |
|---|---|
| `DELETE /records/{id}` auth | Requires `get_current_company_admin_user`; normal company users may list/detail records but cannot delete them |
| Tenant boundary | `RecordService.delete_record(...)` must load the record by both `company_id` and `record_id` |
| Related data | Deleting a record deletes its file metadata and review history through the record aggregate cascade |
| Object storage | COS objects referenced by `record.files` must be deleted before DB commit |
| Duplicate file references | Delete each unique `(bucket_name, region, object_key)` once even if duplicate metadata rows exist |
| Master data | Deleting one record must not delete the referenced `Part` or `Device`; those remain master data |
| AI dependency | Plain record delete must not instantiate or require AI runtime configuration; AI clients should be created only on AI paths |

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Record is missing or outside the current company | Raise `NotFoundError(code="record_not_found")` |
| Current user is not a company admin | Route dependency returns `403 permission_denied` before service mutation |
| Record has file objects | Delete referenced COS objects first, then delete DB metadata and the record |
| COS object deletion fails | Propagate the integration error and do not commit DB deletion |
| Record has review history | Review rows are removed with the record aggregate |
| Record has duplicate file rows pointing to the same object | Only one remote delete call is issued for that object |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | Admin deletes one bad record; backend removes the COS image, file metadata, review rows, and the detection record, while the part and MP157 device remain |
| Base | Admin deletes a record with no files or reviews; backend deletes only the detection record |
| Bad | A service deletes DB rows before COS cleanup, then COS deletion fails and leaves orphaned storage objects |
| Bad | A record-row delete path reuses device purge logic and removes the part or device master-data row |

### 6. Tests Required

- route smoke test asserting `DELETE /api/v1/records/{record_id}` is mounted
- service test asserting single-record delete removes `DetectionRecord`, `FileObject`, `ReviewRecord`, and unique COS objects
- service test asserting missing or cross-company record returns `record_not_found`
- frontend build/typecheck after adding the `deleteRecord(...)` wrapper and record-table action

Assertion points:

- `RecordService.delete_record(...)` keeps the company boundary
- COS cleanup happens before database commit
- duplicate object keys produce one delete call
- part/device rows survive record deletion
- plain delete tests can run without AI runtime settings

### 7. Wrong vs Correct

#### Wrong

```py
# Deletes database metadata first; a later COS failure would orphan files.
self.record_repository.delete(record)
self.db.commit()
self._delete_record_cos_objects(record=record)
```

```py
# Pulls in AI/COS runtime settings even when the caller only wants list/create/delete behavior.
self.ai_review_client = AIReviewClient()
```

#### Correct

```py
record = self.record_repository.get_by_id(
    record_id,
    company_id=company_id,
    include_related=True,
)
if record is None:
    raise NotFoundError(code="record_not_found", message="检测记录不存在。")

self._delete_record_cos_objects(record=record)
self.record_repository.delete(record)
self.db.commit()
```

```py
@property
def ai_review_client(self) -> AIReviewClient:
    if self._ai_review_client is None:
        self._ai_review_client = AIReviewClient()
    return self._ai_review_client
```

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

- Trigger: any change to station-inside password approval, admin direct password reset, admin approval/rejection, user deletion with pending password requests, or the user-table snapshot fields introduced by `20260421_0008_user_password_change_requests.py`
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

def reset_user_password_to_default(
    *,
    company_id: int | None,
    current_user_id: int,
    user_id: int,
) -> tuple[User, str]: ...

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
| `users.password_changed_at` | Updates only when approval or admin direct reset actually changes the effective password; request submission or rejection must not advance it |
| `users.password_reset_*` | Existing email-reset token state must be cleared when a password request is approved or an admin direct reset succeeds so old reset links cannot remain valid |

Additional rules:

- each user may have only one active `pending` password-request snapshot at a time
- this flow uses a snapshot on `users`, not a separate history table; do not accumulate multiple pending rows elsewhere without a new code-spec update
- `change_to_requested` must pass through `SecretCipher` before storage; plaintext requested passwords must never touch the database
- approval and rejection must keep `requested_at` for traceability while clearing the encrypted pending secret
- admin direct reset is a separate privileged action, not an approve/reject shortcut; it may succeed even when the member never submitted a pending request
- admin direct reset must close any existing pending password-request snapshot by setting it to `approved + reset_to_default` and clearing the encrypted pending secret

### 4. Validation & Error Matrix

| Condition | Problem | Expected behavior |
|---|---|---|
| User submits a second request while one is already pending | Pending target password can be silently overwritten | Reject the write and preserve the existing snapshot |
| `reset_to_default` request stores an encrypted payload | Unnecessary secret retention | Persist `password_change_requested_password_encrypted = NULL` |
| `change_to_requested` approval finds no encrypted payload | The snapshot is corrupt and cannot safely apply a password | Fail approval and leave `password_hash` unchanged |
| Request is rejected | Password should not change | Keep `password_hash` and `password_changed_at` unchanged, set status to `rejected`, and clear encrypted pending payload |
| Request is approved | New password becomes effective | Update `password_hash`, set `password_changed_at = reviewed_at`, clear email reset token state, clear encrypted pending payload |
| Admin directly resets a member with no pending request | Admins need an emergency recovery path without waiting for member action | Update `password_hash` to the default password hash, set `approved + reset_to_default`, set request/review timestamps to the admin action time, and clear `password_reset_*` |
| Admin directly resets a member with a pending request | Old pending payload could remain approvable after the reset | Apply the default password, keep or create an audit snapshot, clear encrypted pending payload, and make the row no longer render as `pending` |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | User submits `change_to_requested`, the DB stores only encrypted pending text, admin approval writes a new `password_hash`, and the encrypted payload is cleared |
| Base | User submits `reset_to_default`, so the DB stores `pending + reset_to_default + NULL encrypted payload`, and approval returns the default password text only in the transient response |
| Base | Admin directly resets a member who never submitted a request; the DB stores an approved reset snapshot and only returns the plaintext default password in the transient API response |
| Bad | Admin direct reset reuses the approve path or `_require_pending_password_request(...)`, so no-pending members cannot be recovered until they submit a request |
| Bad | Submitted password is written into `password_hash` or a plaintext temp column before approval, effectively bypassing the admin gate |

### 6. Tests Required

- migration smoke test asserting the five password-request columns exist after `20260421_0008`
- service test asserting `submit_password_change_request(..., request_type="change_to_requested")` stores only encrypted pending text
- service test asserting duplicate pending submit is rejected without overwriting the first snapshot
- service test asserting approval updates `password_hash` and `password_changed_at` and clears `password_reset_*`
- service test asserting rejection clears the encrypted payload without changing the effective password
- service test asserting admin direct reset succeeds without a pending request and clears `password_reset_*`
- service test asserting admin direct reset closes an existing pending request so it cannot still be approved

Assertion points:

- only one pending snapshot exists per user
- no plaintext requested password is persisted
- approval and rejection both clear `password_change_requested_password_encrypted`
- admin direct reset clears `password_change_requested_password_encrypted` and never requires `_require_pending_password_request(...)`
- `password_changed_at` advances only on approval or admin direct reset

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

#### Wrong

```py
# Direct reset is not an approval action and must not require a pending request.
user = self._require_pending_password_request(user)
return self.approve_password_change_request(
    company_id=company_id,
    current_user_id=current_user_id,
    user_id=user_id,
)
```

#### Correct

```py
reviewed_at = datetime.now(timezone.utc)
user.password_hash = hash_password(DEFAULT_APPROVED_RESET_PASSWORD)
user.password_changed_at = reviewed_at
self._set_password_request_snapshot(
    user=user,
    status="approved",
    request_type="reset_to_default",
    encrypted_password=None,
    requested_at=reviewed_at,
    reviewed_at=reviewed_at,
)
```

---

## Scenario: AI Gateway Provider URL Data Migration

### 1. Scope / Trigger

- Trigger: any provider host/domain migration for stored AI gateways or model `base_url_override` values.
- Affected layers: Alembic data migration -> `ai_gateways` rows -> `ai_model_profiles.base_url_override` -> runtime model context -> frontend preset catalog.

### 2. Signatures

```py
# alembic/versions/20260421_0010_openclaudecode_micuapi_urls.py
OLD_PRIMARY_BASE_URL = "https://www.openclaudecode.cn"
OLD_SLB_BASE_URL = "https://api-slb.openclaudecode.cn"
NEW_BASE_URL = "https://www.micuapi.ai"
NEW_V1_URL = "https://www.micuapi.ai/v1"
```

### 3. Contracts

| Boundary / field | Contract |
|---|---|
| `ai_gateways.vendor` | Internal vendor remains `openclaudecode`; do not rename the enum for a host-only migration |
| `ai_gateways.base_url` | Stored OpenClaudeCode rows using old primary or old SLB hosts must migrate to `https://www.micuapi.ai` |
| `ai_gateways.official_url` | Historical `https://docs.openclaudecode.cn/#/` should migrate to `https://www.micuapi.ai` |
| `ai_model_profiles.base_url_override` | Historical old-host `/v1` overrides must migrate to `https://www.micuapi.ai/v1` |
| Runtime URL construction | OpenAI-compatible and Responses paths still append endpoints below `/v1`; Anthropic Messages uses the host without `/v1` and appends `/v1/messages` itself |

Additional rules:

- frontend preset changes for provider host migrations are not enough; existing production rows need a data migration
- only known old provider URLs should be rewritten automatically, so custom user-entered third-party URLs are not unexpectedly changed
- downgrade may return to the old primary host, but must not resurrect the old SLB host unless explicitly required

### 4. Validation & Error Matrix

| Condition | Problem | Expected behavior |
|---|---|---|
| Only `aiSettingsCatalog.ts` changes | Existing server rows still call the old host | Add Alembic data migration |
| Codex override migrates to host without `/v1` | Responses runtime calls the wrong endpoint | Store `https://www.micuapi.ai/v1` for existing override rows |
| OpenClaudeCode vendor enum is renamed | Existing rows and gateway-specific runtime logic break | Keep `vendor='openclaudecode'` and change URLs only |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | Alembic rewrites existing OpenClaudeCode gateway rows from old primary or old SLB hosts to `https://www.micuapi.ai` while keeping `vendor='openclaudecode'` |
| Base | Existing Codex / Responses model overrides using an old `/v1` URL migrate to `https://www.micuapi.ai/v1` |
| Base | Existing Anthropic-style gateway base URL migrates to the host-only `https://www.micuapi.ai`, and runtime code appends the correct endpoint later |
| Bad | Only frontend presets are changed, leaving production database rows and server runtime traffic on the old OpenClaudeCode host |
| Bad | `base_url_override` is migrated to `https://www.micuapi.ai` without `/v1`, so Responses requests are assembled under the wrong path |

### 6. Tests Required

- backend AI client tests asserting OpenClaudeCode runtime URLs use `https://www.micuapi.ai`
- model discovery tests asserting OpenClaudeCode discovery probes Micu API URLs
- frontend catalog tests asserting current preset and template URLs

Assertion points:

- gateway rows with known old OpenClaudeCode hosts are rewritten to `https://www.micuapi.ai`
- model profile override rows with known old `/v1` URLs are rewritten to `https://www.micuapi.ai/v1`
- custom third-party URLs are not rewritten by the data migration
- internal vendor keys stay `openclaudecode`

### 7. Wrong vs Correct

#### Wrong

```py
# Frontend defaults only affect new records; existing production rows stay stale.
NEW_BASE_URL = "https://www.micuapi.ai"
# No Alembic migration updates ai_gateways or ai_model_profiles.
```

#### Correct

```py
op.execute(
    sa.text(
        """
        UPDATE ai_gateways
        SET base_url = :new_base_url, official_url = :new_base_url
        WHERE vendor = 'openclaudecode'
          AND base_url IN (:old_primary_url, :old_slb_url)
        """
    ).bindparams(
        new_base_url=NEW_BASE_URL,
        old_primary_url=OLD_PRIMARY_BASE_URL,
        old_slb_url=OLD_SLB_BASE_URL,
    )
)
```

#### Wrong

```py
# Responses runtime needs the versioned base URL.
NEW_V1_URL = "https://www.micuapi.ai"
```

#### Correct

```py
NEW_V1_URL = "https://www.micuapi.ai/v1"
```
