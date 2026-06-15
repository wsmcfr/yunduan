# Cloud Detection Context Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add on-demand cloud-side model detection for images uploaded by STM32MP157, store the result as readable cloud detection context, upload the generated cloud model result images to COS, show the text and images in the review page, and include them in AI analysis prompts.

**Architecture:** The backend keeps board-uploaded context fields unchanged and adds a separate `cloud_detection_context` JSON field on `DetectionRecord`. A new cloud detection service downloads the best record image from COS, runs the local UNet and MobileNetV3 ONNX models from `D:\model_picture`, uploads cloud-generated mask / overlay / classification result images back to COS, writes a structured and human-readable result, and exposes both automatic and manual trigger paths. The frontend maps this new field, renders it as a fifth context card, shows cloud-generated result images, and adds a "重新进行云端检测" action that reloads the detail page after completion.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, onnxruntime, OpenCV, NumPy, Tencent COS SDK, Vue 3, TypeScript, Element Plus, Vitest, pytest.

---

## Current Code Facts

| Area | Existing Contract |
|---|---|
| Record storage | `backend/src/db/models/detection_record.py` already stores `vision_context`, `sensor_context`, `decision_context`, and `device_context` as JSON. |
| Record create | `RecordService.create_record()` creates the metadata row before images are registered. |
| File registration | `RecordService.create_file_object()` registers image metadata and updates `uploaded_at` for `source` / `annotated`. |
| COS download | `CosClient.read_file_bytes()` already downloads object bytes through signed/public URL. |
| Detail page | `frontend/src/pages/RecordDetailPage.vue` renders four context panels through `flattenStructuredContext()`. |
| AI context | `RecordService._build_ai_chat_context()` passes structured contexts into `AIReviewClient`. |
| Model project | `D:\model_picture` has `infer_classify.py`, `infer_camera_onnx.py`, classification ONNX + labels, and UNet ONNX models. |

## Final Data Flow

| Step | Owner | Data |
|---|---|---|
| 1 | MP157 | Creates record and uploads/registers `source` or `annotated` image. |
| 2 | Backend | After image registration, attempts cloud detection once if an eligible image exists. |
| 3 | Cloud detection service | Downloads image bytes, decodes with OpenCV, runs classification and segmentation models, and creates cloud result images. |
| 4 | Backend | Uploads generated cloud result images to COS, writes `DetectionRecord.cloud_detection_context` with status, timestamps, raw scores, readable summary, generated file metadata, and comparison to MP157 result. |
| 5 | Frontend detail page | Shows a "云端模型检测上下文" card, cloud-generated result images, and a "重新进行云端检测" button. |
| 6 | AI chat | Includes `cloud_detection_context` and cloud result image references in `AIRecordContext`, compact prompts, and context snapshots. |

## Cloud Detection Context Shape

```json
{
  "status": "success",
  "trigger": "auto_after_upload",
  "source_file": {
    "file_id": 12,
    "file_kind": "source",
    "object_key": "detections/REC/source/xxx.jpg"
  },
  "classification": {
    "model_name": "MobileNetV3-Small",
    "model_path": "D:\\model_picture\\checkpoints_classify\\defect_classifier_static_mixed_int8.onnx",
    "predicted_label": "washer_bad",
    "predicted_result": "bad",
    "confidence": 0.9721,
    "good_probability": 0.0213,
    "bad_probability": 0.9787,
    "probabilities": {
      "washer_bad": 0.9721
    }
  },
  "segmentation": {
    "model_name": "UNet-MobileNetV3",
    "model_path": "D:\\model_picture\\checkpoints_unet_test\\defect_unet_test_decoder_head_int8.onnx",
    "defect_pixels": 1432,
    "threshold_pixels": 80,
    "predicted_result": "bad",
    "class_pixel_counts": {
      "scratch": 1432
    }
  },
  "generated_files": [
    {
      "artifact_type": "cloud_unet_overlay",
      "display_name": "云端 UNet 缺陷叠加图",
      "file_kind": "annotated",
      "bucket_name": "demo-bucket",
      "region": "ap-shanghai",
      "object_key": "detections/REC/source/cloud_detection/20260615T100001_unet_overlay.jpg",
      "content_type": "image/jpeg",
      "size_bytes": 45812,
      "preview_url": "https://..."
    },
    {
      "artifact_type": "cloud_unet_mask",
      "display_name": "云端 UNet 缺陷 mask 图",
      "file_kind": "annotated",
      "bucket_name": "demo-bucket",
      "region": "ap-shanghai",
      "object_key": "detections/REC/source/cloud_detection/20260615T100001_unet_mask.png",
      "content_type": "image/png",
      "size_bytes": 9021,
      "preview_url": "https://..."
    }
  ],
  "comparison": {
    "mp157_result": "good",
    "cloud_result": "bad",
    "is_conflict": true,
    "suggested_action": "建议人工复核，并考虑修正板端结果。"
  },
  "summary_text": "云端分类模型倾向 washer_bad，坏件概率 97.87%；UNet 检出疑似缺陷像素 1432，高于阈值 80。云端结论 bad 与 MP157 初检 good 不一致，建议人工复核并修正板端结果。",
  "started_at": "2026-06-15T10:00:00Z",
  "finished_at": "2026-06-15T10:00:01Z",
  "duration_ms": 850,
  "error_message": null
}
```

Failure shape:

```json
{
  "status": "failed",
  "trigger": "manual_rerun",
  "source_file": null,
  "summary_text": "云端检测失败：当前记录没有可用于检测的 source 或 annotated 图片。",
  "started_at": "2026-06-15T10:00:00Z",
  "finished_at": "2026-06-15T10:00:00Z",
  "duration_ms": 12,
  "error_message": "当前记录没有可用于检测的 source 或 annotated 图片。"
}
```

## Task 1: Backend Schema And DTO Contract

**Files:**

| Action | Path |
|---|---|
| Modify | `backend/src/db/models/detection_record.py` |
| Modify | `backend/src/schemas/detection_record.py` |
| Create | `backend/alembic/versions/20260615_0012_cloud_detection_context.py` |
| Test | `backend/tests/test_detection_record_model.py` |

**Step 1: Write the failing model/schema test**

Add a test asserting `cloud_detection_context` survives ORM creation and appears in `DetectionRecordDetailResponse`.

```python
def test_detection_record_cloud_detection_context_round_trip():
    context = {
        "status": "success",
        "summary_text": "云端模型检测完成。",
        "classification": {"predicted_label": "washer_bad"},
    }
    record = DetectionRecord(
        company_id=1,
        record_no="REC-CLOUD-CTX-001",
        part_id=1,
        device_id=1,
        result=DetectionResult.BAD,
        review_status=ReviewStatus.PENDING,
        cloud_detection_context=context,
        captured_at=datetime.now(timezone.utc),
    )

    assert record.cloud_detection_context == context
```

If existing tests already create persisted records with fixtures, use those fixtures and assert `DetectionRecordDetailResponse.model_validate(record).cloud_detection_context == context`.

**Step 2: Run the failing backend test**

```powershell
cd D:\yunfuwu\backend
python -m pytest tests/test_detection_record_model.py -q
```

Expected: fail because `DetectionRecord` and schemas do not have `cloud_detection_context`.

**Step 3: Implement minimal schema changes**

Add this field to `DetectionRecord`:

```python
# 云端模型检测结果独立于板端上报上下文，便于复核页直接对比两套模型结论。
cloud_detection_context: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
```

Add this field to `DetectionRecordCreateRequest`, `DetectionRecordListItem`, and inherited detail response:

```python
cloud_detection_context: dict[str, Any] | None = None
```

Create Alembic migration:

```python
"""add cloud detection context

Revision ID: 20260615_0012
Revises: 20260519_0011
Create Date: 2026-06-15
"""

from alembic import op
import sqlalchemy as sa

revision = "20260615_0012"
down_revision = "20260519_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("detection_records", sa.Column("cloud_detection_context", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("detection_records", "cloud_detection_context")
```

**Step 4: Run the test again**

```powershell
cd D:\yunfuwu\backend
python -m pytest tests/test_detection_record_model.py -q
```

Expected: pass.

**Step 5: Commit**

```powershell
git add backend/src/db/models/detection_record.py backend/src/schemas/detection_record.py backend/alembic/versions/20260615_0012_cloud_detection_context.py backend/tests/test_detection_record_model.py
git commit -m "feat: add cloud detection context field"
```

## Task 2: Local ONNX Cloud Detection Service

**Files:**

| Action | Path |
|---|---|
| Create | `backend/src/services/cloud_detection_service.py` |
| Modify | `backend/src/core/config.py` |
| Test | `backend/tests/test_cloud_detection_service.py` |

**Step 1: Write failing unit tests**

Test the service with fake model runners and a fake COS client. Do not load real ONNX in this test.

Required tests:

| Test | Assertion |
|---|---|
| source selection | prefers `source` over `annotated` |
| summary generation | produces readable Chinese `summary_text` |
| conflict detection | marks conflict when MP157 result differs from cloud result |
| generated image upload | uploads cloud-generated result images to COS and records them in `generated_files` |
| no image failure | writes `status="failed"` and a readable reason |

Example:

```python
def test_run_cloud_detection_prefers_source_file_and_builds_summary(fake_record):
    service = CloudDetectionService(
        cos_client=FakeCosClient(image_bytes=make_test_jpeg_bytes()),
        classifier=FakeClassifier(label="washer_bad", probabilities={"washer_bad": 0.97}),
        segmenter=FakeSegmenter(defect_pixels=1432, class_pixel_counts={"scratch": 1432}),
        settings=make_cloud_detection_settings(enabled=True),
    )

    context = service.run_for_record(record=fake_record, trigger="manual_rerun")

    assert context["status"] == "success"
    assert context["source_file"]["file_kind"] == "source"
    assert context["classification"]["predicted_result"] == "bad"
    assert context["segmentation"]["predicted_result"] == "bad"
    assert context["comparison"]["is_conflict"] is True
    assert "坏件概率" in context["summary_text"]
```

**Step 2: Run tests to verify they fail**

```powershell
cd D:\yunfuwu\backend
python -m pytest tests/test_cloud_detection_service.py -q
```

Expected: fail because service does not exist.

**Step 3: Add config**

In `Settings`, add:

```python
cloud_detection_enabled: bool = Field(default=True, alias="CLOUD_DETECTION_ENABLED")
cloud_detection_model_root: str = Field(default="D:\\model_picture", alias="CLOUD_DETECTION_MODEL_ROOT")
cloud_detection_classifier_model_path: str = Field(
    default="D:\\model_picture\\checkpoints_classify\\defect_classifier_static_mixed_int8.onnx",
    alias="CLOUD_DETECTION_CLASSIFIER_MODEL_PATH",
)
cloud_detection_segment_model_path: str = Field(
    default="D:\\model_picture\\checkpoints_unet_test\\defect_unet_test_decoder_head_int8.onnx",
    alias="CLOUD_DETECTION_SEGMENT_MODEL_PATH",
)
cloud_detection_segment_num_classes: int = Field(default=6, alias="CLOUD_DETECTION_SEGMENT_NUM_CLASSES")
cloud_detection_defect_pixel_threshold: int = Field(default=80, alias="CLOUD_DETECTION_DEFECT_PIXEL_THRESHOLD")
cloud_detection_max_image_bytes: int = Field(default=8 * 1024 * 1024, alias="CLOUD_DETECTION_MAX_IMAGE_BYTES")
```

**Step 4: Implement service structure**

Create:

```python
class CloudDetectionService:
    """运行云端本地 ONNX 检测，并生成可写回检测记录的结构化上下文。"""

    def run_for_record(self, *, record: DetectionRecord, trigger: str) -> dict[str, Any]:
        """对单条检测记录执行云端检测。

        主要流程:
            1. 从记录文件中选择 source，缺失时退回 annotated。
            2. 通过 COS 客户端读取图片字节。
            3. 解码图片并分别执行分类、分割模型。
            4. 合并两个模型结论，生成与 MP157 初检的对比信息。
            5. 返回能直接写入 cloud_detection_context 的 JSON 字典。
        """
```

Use dependency injection for tests:

```python
def __init__(
    self,
    *,
    cos_client: CosClient | None = None,
    classifier: CloudClassifier | None = None,
    segmenter: CloudSegmenter | None = None,
    settings: Settings | None = None,
) -> None:
```

**Step 5: Implement model runner wrappers**

Use `onnxruntime`, `cv2`, and `numpy` inside runner classes. Lazy-load sessions so ordinary backend startup does not immediately load models.

Functions to implement:

| Function | Purpose |
|---|---|
| `decode_image_bytes(data: bytes) -> np.ndarray` | `cv2.imdecode` bytes into BGR image. |
| `CloudClassifier.predict(image_bgr) -> ClassificationPrediction` | Use `infer_classify.py` preprocessing rules. |
| `CloudSegmenter.predict(image_bgr) -> SegmentationPrediction` | Use `infer_camera_onnx.py` preprocessing rules. |
| `CloudDetectionService._upload_generated_images(...)` | Upload generated mask / overlay / classification images to COS and return metadata for DB registration and UI display. |
| `resolve_result_from_label(label: str) -> DetectionResult` | label token containing `bad` means bad, `good` means good, else uncertain. |
| `build_summary_text(...) -> str` | Human-readable Chinese output. |

Do not import `D:\model_picture` scripts directly. Copy only the minimal preprocessing constants and rules into backend service, with comments explaining they must match model training.

**Step 6: Run service tests**

```powershell
cd D:\yunfuwu\backend
python -m pytest tests/test_cloud_detection_service.py -q
```

Expected: pass.

**Step 7: Commit**

```powershell
git add backend/src/core/config.py backend/src/services/cloud_detection_service.py backend/tests/test_cloud_detection_service.py
git commit -m "feat: add cloud model detection service"
```

## Task 3: Backend Trigger And Manual Rerun Endpoint

**Files:**

| Action | Path |
|---|---|
| Modify | `backend/src/services/record_service.py` |
| Modify | `backend/src/api/routes/records.py` |
| Modify | `backend/src/schemas/detection_record.py` |
| Test | `backend/tests/test_record_service.py` |
| Test | `backend/tests/test_app.py` |

**Step 1: Write failing tests for automatic trigger**

Add service test:

```python
def test_create_file_object_runs_cloud_detection_after_source_upload(db_session, fake_cloud_detection_service):
    service = RecordService(
        db_session,
        cos_client=FakeCosClient(),
        cloud_detection_service=fake_cloud_detection_service,
    )

    file_object = service.create_file_object(
        company_id=1,
        record_id=record.id,
        payload=FileObjectCreateRequest(... file_kind=FileKind.SOURCE ...),
    )

    db_session.refresh(record)
    assert record.cloud_detection_context["status"] == "success"
    assert record.cloud_detection_context["trigger"] == "auto_after_upload"
```

**Step 2: Write failing tests for manual rerun**

Add service and route tests:

```python
def test_run_cloud_detection_updates_record_context(db_session, fake_cloud_detection_service):
    context = RecordService(...).run_cloud_detection(company_id=1, record_id=record.id)

    assert context.cloud_detection_context["trigger"] == "manual_rerun"
```

Route smoke:

```python
response = client.post(f"/api/v1/records/{record.id}/cloud-detection")
assert response.status_code == 200
assert response.json()["cloud_detection_context"]["status"] == "success"
```

**Step 3: Run tests to verify failure**

```powershell
cd D:\yunfuwu\backend
python -m pytest tests/test_record_service.py tests/test_app.py -q
```

Expected: fail because endpoint and service method do not exist.

**Step 4: Implement service injection and methods**

Update `RecordService.__init__`:

```python
cloud_detection_service: CloudDetectionService | None = None,
```

Add lazy property:

```python
@property
def cloud_detection_service(self) -> CloudDetectionService:
    """按需创建云端检测服务，避免普通列表接口加载 ONNX 模型。"""
```

Add:

```python
def run_cloud_detection(self, *, company_id: int, record_id: int, trigger: str = "manual_rerun") -> DetectionRecord:
    """对指定记录执行云端模型检测并保存结果。"""
```

Update `create_file_object()` after file metadata commit or before final commit:

| Rule | Behavior |
|---|---|
| file kind is `source` or `annotated` | attempt detection |
| service raises expected integration/model error | store failed context but do not fail file registration |
| file kind is `thumbnail` | skip automatic detection |
| cloud service returns `generated_files` | create `FileObject` rows as `annotated` artifacts so detail image preview and AI image selection can reuse existing record file behavior |

Use one DB commit after writing `cloud_detection_context`.

**Step 5: Add endpoint**

In `records.py`:

```python
@router.post("/{record_id}/cloud-detection", response_model=DetectionRecordDetailResponse)
def run_cloud_detection(...):
    """重新运行云端本地模型检测。"""
```

Use `get_current_company_user`. The endpoint returns full detail so frontend can refresh state from the response or reload.

**Step 6: Run tests**

```powershell
cd D:\yunfuwu\backend
python -m pytest tests/test_record_service.py tests/test_app.py -q
```

Expected: pass.

**Step 7: Commit**

```powershell
git add backend/src/services/record_service.py backend/src/api/routes/records.py backend/tests/test_record_service.py backend/tests/test_app.py
git commit -m "feat: trigger cloud detection for record images"
```

## Task 4: AI Context Integration

**Files:**

| Action | Path |
|---|---|
| Modify | `backend/src/services/record_service.py` |
| Modify | `backend/src/schemas/review.py` |
| Modify | `backend/src/integrations/ai_review_client.py` |
| Test | `backend/tests/test_ai_review_client.py` |
| Test | `backend/tests/test_record_service.py` |

**Step 1: Write failing tests**

Add tests asserting:

| Test | Assertion |
|---|---|
| `RecordService._build_ai_chat_context` | includes `cloud_detection_context` |
| compact prompt | contains `云端模型检测上下文` or the summary text |
| context snapshot | JSON contains `cloud_detection_context` |

Example:

```python
def test_ai_chat_context_includes_cloud_detection_context(record_with_cloud_context):
    context = RecordService(db)._build_ai_chat_context(record=record_with_cloud_context)

    assert context["cloud_detection_context"]["summary_text"] == "云端模型检测完成。"
```

**Step 2: Run failing tests**

```powershell
cd D:\yunfuwu\backend
python -m pytest tests/test_ai_review_client.py tests/test_record_service.py -q
```

Expected: fail because prompt/schema does not include new field.

**Step 3: Implement backend AI context mapping**

Add `cloud_detection_context` to:

| Location | Field |
|---|---|
| `_build_ai_chat_context()` | `"cloud_detection_context": record.cloud_detection_context` |
| `AIRecordContext` schema | `cloud_detection_context: dict[str, Any] | None` |
| `AIReviewClient._build_compact_nested_context_lines()` | include label `"cloud_detection_context": "云端模型检测上下文"` |
| Prompt instructions | mention comparing MP157 result with cloud model result when available |

**Step 4: Run tests**

```powershell
cd D:\yunfuwu\backend
python -m pytest tests/test_ai_review_client.py tests/test_record_service.py -q
```

Expected: pass.

**Step 5: Commit**

```powershell
git add backend/src/services/record_service.py backend/src/schemas/review.py backend/src/integrations/ai_review_client.py backend/tests/test_ai_review_client.py backend/tests/test_record_service.py
git commit -m "feat: include cloud detection in AI context"
```

## Task 5: Frontend DTO, Mapper, API Wrapper

**Files:**

| Action | Path |
|---|---|
| Modify | `frontend/src/types/api.ts` |
| Modify | `frontend/src/types/models.ts` |
| Modify | `frontend/src/services/mappers/commonMappers.ts` |
| Modify | `frontend/src/services/api/records.ts` |
| Test | `frontend/src/services/api/records.test.ts` |
| Test | existing mapper test or create `frontend/src/services/mappers/commonMappers.test.ts` if absent |

**Step 1: Write failing tests**

Add tests asserting:

| Test | Assertion |
|---|---|
| mapper | maps `cloud_detection_context` to `cloudDetectionContext` |
| AI mapper | maps `AIRecordContextDto.cloud_detection_context` |
| API wrapper | calls `/api/v1/records/{id}/cloud-detection` with POST |

Example:

```ts
expect(mapDetectionRecordDto(dto).cloudDetectionContext).toEqual({
  status: "success",
  summary_text: "云端模型检测完成。",
});
```

**Step 2: Run frontend tests to verify failure**

```powershell
cd D:\yunfuwu\frontend
npm run test -- records.test.ts
```

If mapper tests are separate:

```powershell
npm run test -- commonMappers.test.ts
```

Expected: fail because fields/wrapper do not exist.

**Step 3: Implement DTO/model fields**

Add:

```ts
cloud_detection_context: Record<string, StructuredContextValueDto> | null;
```

to `DetectionRecordDto` and `AIRecordContextDto`.

Add:

```ts
cloudDetectionContext: StructuredContextBlock | null;
```

to `DetectionRecordModel` and `AIRecordContext`.

Map both fields in `commonMappers.ts`.

**Step 4: Implement API wrapper**

```ts
export function runCloudDetection(recordId: number): Promise<DetectionRecordDetailDto> {
  return apiRequest<DetectionRecordDetailDto>(`/api/v1/records/${recordId}/cloud-detection`, {
    method: "POST",
  });
}
```

**Step 5: Run tests**

```powershell
cd D:\yunfuwu\frontend
npm run test -- records.test.ts
npm run test -- commonMappers.test.ts
```

Expected: pass.

**Step 6: Commit**

```powershell
git add frontend/src/types/api.ts frontend/src/types/models.ts frontend/src/services/mappers/commonMappers.ts frontend/src/services/api/records.ts frontend/src/services/api/records.test.ts frontend/src/services/mappers/commonMappers.test.ts
git commit -m "feat: map cloud detection context in frontend"
```

## Task 6: Detail Page UI

**Files:**

| Action | Path |
|---|---|
| Modify | `frontend/src/pages/RecordDetailPage.vue` |
| Test | `frontend/src/pages/managementPages.test.ts` or create dedicated `frontend/src/pages/recordDetailPage.test.ts` if pattern exists |

**Step 1: Write failing source/UI contract tests**

Assert the detail page contains:

| Selector/Text | Purpose |
|---|---|
| `云端模型检测上下文` | fifth context panel title |
| `重新进行云端检测` | manual rerun button |
| `runCloudDetection` | uses API wrapper |
| `cloudDetectionContext` | uses mapped model field |

**Step 2: Run failing frontend test**

```powershell
cd D:\yunfuwu\frontend
npm run test -- managementPages.test.ts
```

Expected: fail because UI does not exist.

**Step 3: Implement UI behavior**

Modify imports:

```ts
import { fetchRecordDetail, runCloudDetection } from "@/services/api/records";
```

Add state:

```ts
const cloudDetectionSubmitting = ref(false);
```

Add context panel:

```ts
{
  key: "cloud",
  title: "云端模型检测上下文",
  description: "展示云端重新对板端上传图片运行 UNet 和 MobileNetV3-Small 后得到的检测结果，用于和板端初检信息对比。",
  entries: flattenStructuredContext(record.value?.cloudDetectionContext),
}
```

Add handler:

```ts
async function handleRunCloudDetection(): Promise<void> {
  if (!record.value) {
    return;
  }

  cloudDetectionSubmitting.value = true;
  try {
    const response = await runCloudDetection(record.value.id);
    record.value = mapDetectionRecordDetailDto(response);
    const status = record.value.cloudDetectionContext?.status;
    if (status === "failed") {
      ElMessage.warning("云端检测已完成，但模型运行失败，请查看云端模型检测上下文。");
      return;
    }
    ElMessage.success("云端模型检测已完成");
  } catch (caughtError) {
    ElMessage.error(caughtError instanceof Error ? caughtError.message : "云端检测失败");
  } finally {
    cloudDetectionSubmitting.value = false;
  }
}
```

Add button near AI/review actions:

```vue
<ElButton
  type="success"
  plain
  :loading="cloudDetectionSubmitting"
  @click="handleRunCloudDetection"
>
  重新进行云端检测
</ElButton>
```

**Step 4: Run frontend tests**

```powershell
cd D:\yunfuwu\frontend
npm run test -- managementPages.test.ts
```

Expected: pass.

**Step 5: Commit**

```powershell
git add frontend/src/pages/RecordDetailPage.vue frontend/src/pages/managementPages.test.ts
git commit -m "feat: show and rerun cloud detection on record detail"
```

## Task 7: Integration Verification And Dependency Update

**Files:**

| Action | Path |
|---|---|
| Modify | `backend/pyproject.toml` |
| Modify | deployment docs if needed |
| Test | backend full test subset |
| Test | frontend full test/build |

**Step 1: Add dependencies**

Add backend dependencies if missing:

```toml
"onnxruntime>=1.18.0",
"opencv-python-headless>=4.10.0",
"numpy>=1.26.0",
```

If production server already has these installed through `D:\model_picture\defect-unet`, do not rely on that environment for the FastAPI process. The backend runtime must declare what it imports.

**Step 2: Run backend tests**

```powershell
cd D:\yunfuwu\backend
python -m pytest -q
```

Expected: all backend tests pass.

**Step 3: Run frontend tests and build**

```powershell
cd D:\yunfuwu\frontend
npm run test
npm run build
```

Expected: tests pass and Vite build succeeds.

**Step 4: Manual smoke test**

Use existing local or production-like data:

| Check | Expected |
|---|---|
| Open record detail with source image | cloud context card visible |
| Click `重新进行云端检测` | button shows loading, then detail reloads |
| Successful model run | `summary_text` appears in cloud context card |
| Successful model run with generated artifacts | cloud mask / overlay / classification images are uploaded to COS and visible in the detail image area |
| AI dialog meta/context | `cloud_detection_context` appears in the SSE `meta.context` payload |
| Missing image record | cloud context shows failed status and readable reason |

**Step 5: Deployment notes**

Document required env overrides:

```text
CLOUD_DETECTION_ENABLED=true
CLOUD_DETECTION_MODEL_ROOT=D:\model_picture
CLOUD_DETECTION_CLASSIFIER_MODEL_PATH=D:\model_picture\checkpoints_classify\defect_classifier_static_mixed_int8.onnx
CLOUD_DETECTION_SEGMENT_MODEL_PATH=D:\model_picture\checkpoints_unet_test\defect_unet_test_decoder_head_int8.onnx
CLOUD_DETECTION_SEGMENT_NUM_CLASSES=6
CLOUD_DETECTION_DEFECT_PIXEL_THRESHOLD=80
```

Production must ensure:

| Requirement | Reason |
|---|---|
| model files exist on the cloud server | FastAPI process loads local ONNX paths |
| backend Python environment has ONNX/OpenCV/NumPy | service imports these packages |
| COS read permissions work from backend server | cloud detection downloads the uploaded image |
| COS write permissions work from backend server | cloud detection uploads generated mask / overlay / classification result images |
| detection is synchronous MVP | upload response may be slower; if it becomes too slow, move to background task later |

**Step 6: Commit**

```powershell
git add backend/pyproject.toml docs/plans/2026-06-15-cloud-detection-context.md
git commit -m "docs: plan cloud detection deployment requirements"
```

## Task 8: Optional Post-MVP Background Queue

Do not implement this in the first pass unless synchronous upload becomes too slow.

| Future Change | Why Later |
|---|---|
| Background task queue | Requires job status, retries, and possibly worker deployment. |
| Saving cloud overlay/mask output images to COS | Useful, but not required for readable comparison and AI context. |
| Per-company model configuration | Current requirement points to one fixed `D:\model_picture` model set. |
| Automatic board correction from cloud result | Human review should stay in control for now. |

## Done Criteria

| Area | Required Evidence |
|---|---|
| Backend schema | Alembic migration exists and tests pass. |
| Detection service | Unit tests cover success, conflict, missing image, and readable summary. |
| Auto trigger | Registering source/annotated image writes cloud detection context without breaking upload. |
| Manual rerun | `POST /api/v1/records/{id}/cloud-detection` updates and returns detail. |
| AI readable | AI context schema and prompt snapshot include `cloud_detection_context`. |
| Frontend | Detail page shows fifth context panel, cloud-generated result images, and rerun button. |
| Verification | `python -m pytest -q`, `npm run test`, and `npm run build` pass. |
