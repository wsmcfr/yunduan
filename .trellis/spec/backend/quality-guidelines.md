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

## PDF Layout Quality

### Convention: Direct-Draw PDF Renderers Need Pagination Regression Tests

When a backend service draws PDF pages directly with `reportlab` canvas commands, layout bugs do not fail loudly.
The PDF can still be generated while cards, charts, or bullet lists silently overflow the page bottom.

Implementation contract:

- any renderer that positions panels with explicit `x/y/width/height` values must reserve a stable footer-safe area
- do not keep stacking sections onto the first page once the remaining height is smaller than the next block budget
- split summary, appendix, or AI text into explicit later pages instead of relying on one oversized first page
- unit tests should validate pagination behavior by patching the renderer dependency and using a fake canvas object
- those tests should assert signals such as `showPage()` count, later-page section titles, and successful byte output
- do not make pagination tests depend on the local machine having `reportlab` installed

Example:

```python
with (
    patch.object(renderer, "_load_reportlab", return_value=fake_modules),
    patch.object(renderer, "_ensure_font_registered", return_value="FakeFont"),
):
    pdf_bytes, _ = renderer.build_pdf(overview=overview, ai_analysis=None)

assert pdf_bytes.startswith(b"%PDF")
assert fake_canvas.show_page_calls == 1
assert "关键发现与样本摘要" in fake_canvas.drawn_strings
```

Why:

- raw PDF bytes are poor regression oracles for pagination problems
- local development environments may intentionally omit `reportlab`
- a fake canvas catches the real failure mode here: content stayed on the wrong page or never paged at all

### Common Mistake: Treating "PDF Generated Successfully" as Layout Success

**Symptom**: The lightweight PDF opens, but the lower panels are clipped, crowded, or pushed beyond the printable area.

**Cause**: Direct-draw renderers use absolute vertical coordinates; if the page budget is not recalculated, one more panel can silently overflow A4.

**Fix**: Move supporting sections such as key findings, gallery summary, or AI appendix to dedicated pages and keep a fixed footer-safe area on each page.

**Prevention**:

- add a fake-canvas pagination test whenever a new direct-draw panel is introduced
- assert later-page titles and `showPage()` counts
- if a renderer change is deployed, follow with one real server-side smoke render instead of trusting unit tests alone

---

## Scenario: Cloud Detection Generated Images and AI Context

### 1. Scope / Trigger

- Trigger: changes touching `CloudDetectionService`, `RecordService.run_cloud_detection(...)`, `cloud_detection_context`, COS-generated cloud detection artifacts, or record AI chat context.
- Affected layers: local ONNX runner -> COS object keys -> `FileObject` metadata -> `DetectionRecord.cloud_detection_context` -> AI prompt / schema.

### 2. Signatures

```py
def CloudDetectionService.run_for_record(*, record: DetectionRecord, trigger: str) -> dict[str, Any]: ...
def CloudDetectionService._upload_generated_images(...) -> list[dict[str, Any]]: ...
def RecordService.run_cloud_detection(*, company_id: int, record_id: int, trigger: str = "manual_rerun") -> DetectionRecord: ...
def RecordService._register_cloud_detection_generated_files(*, record: DetectionRecord, context: dict[str, Any]) -> list[dict[str, Any]]: ...
def RecordService._build_ai_chat_context(*, record: DetectionRecord) -> dict: ...
```

Stable generated object keys:

```text
detections/{record_no}/cloud_detection/cloud_unet_overlay.jpg
detections/{record_no}/cloud_detection/cloud_unet_mask.png
detections/{record_no}/cloud_detection/cloud_mobilenetv3_classification.jpg
```

AI context field:

```json
{
  "cloud_detection_context": {
    "status": "success",
    "summary_text": "...",
    "comparison": {"mp157_result": "good", "cloud_result": "bad", "is_conflict": true},
    "generated_files": [{"artifact_type": "cloud_unet_overlay", "object_key": "...", "preview_url": "..."}]
  }
}
```

### 3. Contracts

| Boundary | Contract |
|---|---|
| COS object key | Cloud-generated detection images use stable keys without timestamps because they represent the current cloud review result. |
| Manual rerun | A manual ONNX rerun overwrites the existing COS object for each artifact type instead of creating historical image versions. |
| `FileObject` metadata | If a generated artifact with the same `object_key` already exists for the record, update that row's `content_type`, `size_bytes`, `etag`, `uploaded_at`, and storage fields; do not insert another row. |
| Board fields | Cloud detection must write only `cloud_detection_context`; it must not overwrite board-side `vision_context`, `sensor_context`, `decision_context`, or `device_context`. |
| AI context | `_build_ai_chat_context(...)` must include `cloud_detection_context` so AI chat can compare MP157 and cloud model conclusions. |
| Compact prompt | Compact OpenClaudeCode/Micu prompts must include readable cloud summary, comparison, classification/segmentation signals when present, and generated artifact URLs or object keys. |

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| First source/annotated upload triggers cloud detection | Generated files are uploaded to COS, registered as `FileObject`, and written back into `cloud_detection_context.generated_files`. |
| Manual rerun happens twice for the same record | COS upload requests use the same keys both times; DB still has one generated file row per artifact key, with updated metadata from the latest run. |
| Cloud detector returns no `generated_files` list | Record still stores failure or summary context; no file rows are created. |
| Existing generated row has stale metadata | Registration updates stale metadata instead of leaving old size/etag visible in the detail page. |
| AI chat uses a compact provider prompt | Prompt contains `云端模型检测上下文`, `summary_text`, `mp157_result`, `cloud_result`, and generated artifact reference. |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | First run uploads `cloud_unet_overlay.jpg`; second manual rerun uploads the same key and updates the existing `FileObject.etag`. |
| Base | Cloud detection fails before generating images; `cloud_detection_context.status="failed"` and the existing board upload files remain unchanged. |
| Bad | Object keys include a timestamp, so every rerun creates new overlay/mask/classification images and the UI shows stale historical outputs as if they were current. |
| Bad | `_build_ai_chat_context(...)` omits `cloud_detection_context`, so the AI only sees MP157 output and cannot reason about cloud/model disagreement. |

### 6. Tests Required

- `test_cloud_detection_service.py`: assert repeated `run_for_record(...)` calls produce the same generated `object_key` list.
- `test_record_service.py`: assert manual rerun reuses the same generated `FileObject.id` and updates `size_bytes` / `etag`.
- `test_record_service.py`: assert `_build_ai_chat_context(...)` includes `cloud_detection_context`.
- `test_ai_review_client.py`: assert compact prompt and context snapshot include cloud detection summary, comparison, and generated artifact URL.

Assertion points:

- generated key names contain `cloud_unet_overlay`, `cloud_unet_mask`, and `cloud_mobilenetv3_classification` without a timestamp prefix
- rerun count changes metadata, not row count
- AI prompt includes both `mp157_result` and `cloud_result`

### 7. Wrong vs Correct

#### Wrong

```py
timestamp = started_at.strftime("%Y%m%dT%H%M%S%fZ")
object_key = f"detections/{record.record_no}/cloud_detection/{timestamp}_{artifact_type}.jpg"
```

#### Correct

```py
object_key = f"detections/{record.record_no}/cloud_detection/{artifact_type}.{extension}"
```

#### Wrong

```py
if object_key in existing_keys:
    return existing_file
```

#### Correct

```py
if existing_file is not None:
    existing_file.size_bytes = item.get("size_bytes")
    existing_file.etag = item.get("etag")
    existing_file.uploaded_at = datetime.now(timezone.utc)
```

---

## Testing Expectations

### Bootstrap baseline

| Area | Minimum expectation |
|---|---|
| Route layer | Smoke tests for primary endpoints |
| Service layer | Unit tests for record creation, review decisions, and integration failure paths |
| Repository layer | Query tests for filtering, sorting, and pagination |
| Integration layer | Mocked tests for COS and AI review clients |
| Server-rendered PDF | Verify both the renderer decision path and the manual-layout pagination path |

### Done means

- code follows the directory and naming guidelines
- lint and type checks pass
- changed API contracts are documented
- at least one good-path and one failure-path test exist for new backend behavior
- direct-draw PDF changes include a pagination regression test that does not rely on optional local PDF libraries

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
