# MP157 Context Explanations Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 MP157 上传的视觉、传感器、判定、设备上下文字段统一转成中文解释，并让详情页、AI 对话上下文、统计报表 PDF 共用同一套解释。

**Architecture:** 后端新增统一上下文解释服务，保留原始 JSON 不改、不丢，只在响应和内部消费链路中附加 `context_explanations`。详情接口、AI 上下文、统计导出都调用同一个服务，前端只负责渲染后端已经解释好的中文结构，避免多处翻译逻辑漂移。

**Tech Stack:** FastAPI/Pydantic、SQLAlchemy ORM、ReportLab/WeasyPrint PDF、Vue 3 + Vite + TypeScript + Element Plus、pytest、Vitest。

---

### Task 1: 后端解释服务

**Files:**
- Create: `backend/src/services/context_explanation_service.py`
- Test: `backend/tests/test_context_explanation_service.py`

**Step 1: Write the failing test**

```python
from src.services.context_explanation_service import build_context_explanations


def test_explains_mp157_weighing_ldc_f4_and_vision_contexts() -> None:
    result = build_context_explanations(
        vision_context={
            "unet": {"defect_pixels": 0},
            "mobilenetv3_small": {"class_label": "gasket_bad", "confidence": 0.91},
        },
        sensor_context={
            "weighing": {
                "stable": True,
                "decision": "pass",
                "raw_adc": 237171,
                "net_weight_g": 12.35,
            },
            "ldc1614_eddy_current": {
                "overall_decision": "fail",
                "channels": [
                    {"channel": 0, "enabled": False},
                    {"channel": 1, "enabled": True, "raw_code": 9988, "decision": "fail"},
                ],
            },
            "f4_flow": {
                "model_ready_ack": True,
                "active_frame_timeout_ms": 600,
                "next_step": "upload_then_final_sort",
            },
        },
        decision_context={"result": "bad", "need_ai_review": True},
        device_context={"device_code": "MP157-VIS-01"},
    )

    flat_text = "\n".join(
        item.explanation
        for group in result.groups
        for item in group.items
    )
    assert "HX711 原始 ADC 读数：237171" in flat_text
    assert "称重结论：通过" in flat_text
    assert "LDC1614 通道 0：未启用" in flat_text
    assert "下一步：先上传云端，上传完成后再通知 F4 做最终分拣" in flat_text
    assert "UNet 检出缺陷像素数：0" in flat_text
    assert result.summary
```

**Step 2: Run test to verify it fails**

Run: `cd backend; python -m pytest tests/test_context_explanation_service.py -q`

Expected: FAIL with `ModuleNotFoundError` because the service does not exist yet.

**Step 3: Write minimal implementation**

Create Pydantic models:

```python
class ContextExplanationItem(BaseModel):
    source_path: str
    label: str
    value_text: str
    explanation: str

class ContextExplanationGroup(BaseModel):
    key: str
    title: str
    summary: str
    items: list[ContextExplanationItem]

class ContextExplanationResponse(BaseModel):
    summary: str
    groups: list[ContextExplanationGroup]
```

Implement `build_context_explanations(...)` using explicit MP157 rule functions for:

- `vision_context.unet.*`
- `vision_context.mobilenetv3_small.*`
- `sensor_context.weighing.*`
- `sensor_context.ldc1614_eddy_current.*` and `channels[]`
- `sensor_context.f4_flow.*`
- `decision_context.*`
- `device_context.*`

Keep unknown fields as readable fallback items, but mark them as original debug data in Chinese.

**Step 4: Run test to verify it passes**

Run: `cd backend; python -m pytest tests/test_context_explanation_service.py -q`

Expected: PASS.

---

### Task 2: 详情响应带中文解释

**Files:**
- Modify: `backend/src/schemas/detection_record.py`
- Modify: `backend/src/services/record_service.py`
- Test: `backend/tests/test_record_service.py`

**Step 1: Write the failing test**

Add a service/schema test that creates or loads a record with MP157 contexts, calls `RecordService.get_record_detail(...)`, then asserts:

```python
assert record.context_explanations.summary
assert any(
    item.source_path == "sensor_context.weighing.raw_adc"
    and "HX711 原始 ADC 读数" in item.explanation
    for group in record.context_explanations.groups
    for item in group.items
)
```

**Step 2: Run test to verify it fails**

Run: `cd backend; python -m pytest tests/test_record_service.py -q`

Expected: FAIL because `context_explanations` is not attached yet.

**Step 3: Implement minimal code**

- Import `ContextExplanationResponse` into `detection_record.py`.
- Add `context_explanations: ContextExplanationResponse | None = None` to `DetectionRecordDetailResponse`.
- In `RecordService.get_record_detail(...)`, after preview URL enrichment, attach:

```python
record.context_explanations = build_context_explanations(
    vision_context=record.vision_context,
    sensor_context=record.sensor_context,
    decision_context=record.decision_context,
    device_context=record.device_context,
)
```

**Step 4: Run test to verify it passes**

Run: `cd backend; python -m pytest tests/test_record_service.py -q`

Expected: PASS.

---

### Task 3: AI 对话上下文复用中文解释

**Files:**
- Modify: `backend/src/services/record_service.py`
- Modify: `backend/src/integrations/ai_review_client.py`
- Test: `backend/tests/test_record_service.py`
- Test: `backend/tests/test_ai_review_client.py`

**Step 1: Write the failing tests**

Add assertions that `_build_ai_chat_context(...)` includes:

```python
assert context["context_explanations"]["summary"]
assert "称重结论" in str(context["context_explanations"])
```

Add AI prompt/client test asserting the compact context text includes `中文上下文解释` and one concrete explanation sentence.

**Step 2: Run tests to verify they fail**

Run: `cd backend; python -m pytest tests/test_record_service.py tests/test_ai_review_client.py -q`

Expected: FAIL because AI context still only contains raw context JSON.

**Step 3: Implement minimal code**

- Add `context_explanations` to `_build_ai_chat_context(...)`.
- Update AI client context serialization to render a compact Chinese explanation block before or near raw context fields.
- Keep raw context fields present for diagnostics.

**Step 4: Run tests to verify they pass**

Run: `cd backend; python -m pytest tests/test_record_service.py tests/test_ai_review_client.py -q`

Expected: PASS.

---

### Task 4: 统计 PDF 样本解释

**Files:**
- Modify: `backend/src/services/statistics_export_service.py`
- Modify: `backend/src/services/statistics_lightweight_pdf_renderer.py`
- Test: `backend/tests/test_statistics_export_service.py`

**Step 1: Write the failing tests**

Add a visual export HTML test:

```python
entry = service._build_sample_image_entry(record=record)
assert "称重结论" in entry["context_summary"]
html = service._build_html(..., sample_images=[entry])
assert "MP157 中文解释" in html
assert "称重结论" in html
```

Add lightweight fake-canvas pagination/content test asserting `drawn_strings` contains `MP157 中文解释` and a concrete explanation text.

**Step 2: Run test to verify it fails**

Run: `cd backend; python -m pytest tests/test_statistics_export_service.py -q`

Expected: FAIL because sample entries do not include context summaries yet.

**Step 3: Implement minimal code**

- Use `build_context_explanations(...)` in `_build_sample_image_entry(...)`.
- Add `context_summary` or compact `context_explanations` strings to sample image dictionaries.
- Render the summary in visual PDF sample cards.
- Draw the summary in lightweight PDF sample cards, preserving existing page breaks.

**Step 4: Run test to verify it passes**

Run: `cd backend; python -m pytest tests/test_statistics_export_service.py -q`

Expected: PASS and fake-canvas pagination assertions still hold.

---

### Task 5: 前端 DTO、Model 和 Mapper

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/types/models.ts`
- Modify: `frontend/src/services/mappers/commonMappers.ts`
- Test: add or modify mapper/source contract test under `frontend/src/services/mappers` or the existing nearest test file

**Step 1: Write the failing test**

Add a mapper test that passes:

```ts
context_explanations: {
  summary: "本记录包含称重、涡流和 F4 流程解释。",
  groups: [
    {
      key: "sensor",
      title: "传感器中文解释",
      summary: "称重通过，LDC 通道 0 未启用。",
      items: [
        {
          source_path: "sensor_context.weighing.raw_adc",
          label: "HX711 原始 ADC",
          value_text: "237171",
          explanation: "HX711 原始 ADC 读数：237171，用于换算重量。",
        },
      ],
    },
  ],
}
```

Assert mapped model exposes `contextExplanations.groups[0].items[0].sourcePath`.

**Step 2: Run test to verify it fails**

Run: `cd frontend; npm run test -- commonMappers`

Expected: FAIL because types and mapper do not know the field.

**Step 3: Implement minimal code**

- Add DTO interfaces `ContextExplanationItemDto`, `ContextExplanationGroupDto`, `ContextExplanationResponseDto`.
- Add frontend model interfaces `ContextExplanationItem`, `ContextExplanationGroup`, `ContextExplanationResponse`.
- Add mapper helpers with Chinese comments.
- Map `DetectionRecordDetailDto.context_explanations -> DetectionRecordModel.contextExplanations`.

**Step 4: Run test to verify it passes**

Run: `cd frontend; npm run test -- commonMappers`

Expected: PASS.

---

### Task 6: 详情页展示中文解释并保留原始调试字段

**Files:**
- Modify: `frontend/src/pages/RecordDetailPage.vue`
- Test: `frontend/src/pages/managementPages.test.ts` or a new source contract test

**Step 1: Write the failing test**

Add a source contract test asserting:

```ts
expect(source).toContain("MP157 中文解释");
expect(source).toContain("contextExplanations");
expect(source).toContain("原始上下文");
```

**Step 2: Run test to verify it fails**

Run: `cd frontend; npm run test -- RecordDetailPage`

Expected: FAIL because the page only renders flattened raw context panels.

**Step 3: Implement minimal code**

- Add a top-level “MP157 中文解释” section before raw context panels.
- Render group title, summary, and explanation cards.
- Rename existing flattened context panels as “原始上下文 / 调试字段”，明确它们是排障用原始数据。
- Keep `.page-grid` as the scroll owner; do not add route-level `height: 100%` or browser scrolling.

**Step 4: Run test to verify it passes**

Run: `cd frontend; npm run test -- RecordDetailPage`

Expected: PASS.

---

### Task 7: 全量相关验证

**Files:**
- No production file changes.

**Step 1: Run backend targeted tests**

Run:

```bash
cd backend
python -m pytest tests/test_context_explanation_service.py tests/test_record_service.py tests/test_ai_review_client.py tests/test_statistics_export_service.py -q
```

Expected: PASS.

**Step 2: Run frontend targeted tests**

Run:

```bash
cd frontend
npm run test -- commonMappers RecordDetailPage
```

Expected: PASS.

**Step 3: Run frontend build**

Run:

```bash
cd frontend
npm run build
```

Expected: build exits 0.

**Step 4: Optional browser visual probe**

If a dev server is needed for detail-page QA, start it and check `/records/<id>` at desktop and narrow widths:

- Browser document must not vertically scroll.
- `.page-grid` must keep `overflow-y: auto`.
- “MP157 中文解释” appears before “原始上下文”.
- Long explanation text wraps inside cards and does not overlap.

