# Board Review Sync Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add cloud-to-STM32MP157 board review-result synchronization while keeping cloud manual review as the final source of truth.

**Architecture:** The frontend submits a cloud review decision and reason to a new backend endpoint. The backend saves a normal manual review, then proxies a short HTTP request to the configured board URL and records success or failure on the detection record.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, httpx, Vue 3, Element Plus, TypeScript.

---

### Task 1: Backend Sync Contract

**Files:**
- Modify: `backend/tests/test_review_service.py`
- Modify: `backend/src/services/review_service.py`
- Modify: `backend/src/schemas/review.py`
- Modify: `backend/src/api/routes/reviews.py`

**Steps:**
1. Write failing service tests for success, missing URL/token, empty reason, HTTP error, and `uncertain -> review`.
2. Add board sync request/response schemas.
3. Implement `ReviewService.sync_board_review(...)` and a small board-result mapper/helper.
4. Add `POST /api/v1/records/{record_id}/sync-board-review`.

### Task 2: Database Fields

**Files:**
- Modify: `backend/src/db/models/device.py`
- Modify: `backend/src/db/models/detection_record.py`
- Modify: `backend/src/schemas/device.py`
- Modify: `backend/src/schemas/detection_record.py`
- Add: `backend/alembic/versions/20260519_0011_board_review_sync.py`

**Steps:**
1. Add board review URL/token fields to devices.
2. Add sync-status fields to detection records.
3. Expose safe response fields, including `has_board_review_token` instead of token plaintext.
4. Add Alembic migration.

### Task 3: Frontend Contract And UI

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/types/models.ts`
- Modify: `frontend/src/services/mappers/commonMappers.ts`
- Modify: `frontend/src/services/api/reviews.ts`
- Modify: `frontend/src/features/devices/DeviceFormDialog.vue`
- Modify: `frontend/src/pages/DevicesPage.vue`
- Modify: `frontend/src/pages/RecordDetailPage.vue`

**Steps:**
1. Add DTO/model fields and mapper coverage for sync status and safe device config fields.
2. Add `syncBoardReview(...)` API wrapper.
3. Add device form fields for board URL/token, with list badges that do not reveal token.
4. Add one detail-page button plus a reason dialog and sync status display.

### Task 4: Verification

**Commands:**
- `python -m pytest tests/test_review_service.py`
- `python -m pytest tests`
- `npm run build`
- `npx tsc -p tsconfig.json --noEmit`
