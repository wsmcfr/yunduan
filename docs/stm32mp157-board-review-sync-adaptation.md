# STM32MP157 云端复核结果同步板端适配文档

## 1. 文档目标

本文档说明云端项目 `D:\yunfuwu` 为适配 STM32MP157 板端“云端复核结果回写”需要新增和修改的结构。目标是：

| 目标 | 说明 |
|---|---|
| 云端保存最终复核 | 云端仍然以自己的人工复核记录作为最终判定来源，不能只把结果发给板端。 |
| 云端一键修正板端 | 云端检测详情页只提供一个“修正板端结果”按钮，点击后弹出原因输入框。 |
| 原因随请求下发 | 弹窗填写的修改原因必须作为 `cloud_reason` 发送给板端，并保存在云端复核记录中。 |
| 只在必要时同步 | 当云端最终判定与板端初检结果不一致时，才需要提示或允许同步板端。 |
| 零件类型不按好坏拆分 | `gasket_good` 和 `gasket_bad` 只能对应同一个零件类型 `gasket`；只有不同零件才创建新的零件类型。 |
| 后端代理调用板端 | 浏览器前端不直接请求开发板，由云端后端调用板端 HTTP 接口，避免 CORS、内网不可达和 token 泄露。 |

## 2. 当前云端已有结构

| 层级 | 已有文件 | 现状 |
|---|---|---|
| 路由 | `backend/src/api/routes/reviews.py` | 已有 `POST /api/v1/records/{record_id}/manual-review`，可创建人工复核记录。 |
| 服务 | `backend/src/services/review_service.py` | `create_manual_review()` 会写入 `ReviewRecord`，并把 `record.review_status` 改为 `reviewed`。 |
| ORM | `backend/src/db/models/detection_record.py` | `effective_result` 已经优先取最新复核记录。 |
| 枚举 | `backend/src/db/models/enums.py` | 检测结果是 `good/bad/uncertain`；板端回写接口使用 `good/bad/review`，需要做枚举映射。 |
| 设备 | `backend/src/db/models/device.py` | 当前没有板端回写 URL 和 token 字段。 |
| 前端详情页 | `frontend/src/pages/RecordDetailPage.vue` | 已有人工复核表单和 `handleManualReviewSubmit()`。 |
| 前端 API | `frontend/src/services/api/reviews.ts` | 已封装 `createManualReview()`。 |

## 3. 新增数据流

```text
云端详情页用户点击“修正板端结果”
  -> 弹出原因输入框
  -> 前端提交 cloud_result + cloud_reason
  -> 云端后端校验权限、记录存在、原因非空
  -> 云端后端创建或复用人工复核记录
  -> 云端后端读取该记录关联设备的 board_review_url / board_review_token
  -> 云端后端 POST 到板端 /api/v1/review-result
  -> 云端记录同步状态 success / failed
  -> 前端刷新详情页并展示同步状态
```

## 4. 板端接口契约

板端已经提供以下接口，云端后端需要按这个格式调用。

| 项目 | 内容 |
|---|---|
| 方法 | `POST` |
| 板端路径 | `/api/v1/review-result` |
| 示例地址 | `http://192.168.1.250:18080/api/v1/review-result` |
| 鉴权请求头 | `X-Board-Token: <设备回写密钥>` |
| 内容类型 | `Content-Type: application/json` |
| 超时建议 | 3 到 5 秒，不要无限等待。 |

请求体：

```json
{
  "record_id": "123",
  "record_no": "MP157-VIS-01-20260519-143012-0001",
  "cloud_result": "bad",
  "cloud_reason": "云端复核发现边缘划痕，板端原判良品需要修正。",
  "operator": "admin",
  "review_time": "2026-05-19 14:03:10",
  "source": "cloud"
}
```

| 字段 | 云端来源 | 必填 | 说明 |
|---|---|---:|---|
| `record_id` | `DetectionRecord.id` | 条件必填 | 板端优先用它匹配本地历史。 |
| `record_no` | `DetectionRecord.record_no` | 条件必填 | `record_id` 匹配失败或为空时兜底。 |
| `cloud_result` | 云端最终复核结果 | 是 | 板端只接受 `good/bad/review`。云端的 `uncertain` 发送前要转成 `review`。 |
| `cloud_reason` | 弹窗填写原因 | 是 | 不能为空；用于板端历史详情展示“云端修正原因”。 |
| `operator` | 当前登录用户 | 否 | 建议用 `display_name`，为空时用 `username`。 |
| `review_time` | 云端复核时间 | 否 | 建议发送本地格式 `YYYY-MM-DD HH:mm:ss` 或 ISO 字符串。 |
| `source` | 固定值 | 否 | 固定传 `cloud`。 |

板端成功响应示例：

```json
{
  "ok": true,
  "message": "updated",
  "updated": true,
  "record_id": "123",
  "record_no": "MP157-VIS-01-20260519-143012-0001",
  "board_result_text": "良品",
  "effective_result_text": "坏品",
  "cloud_review_result": "bad"
}
```

## 5. 数据库适配

### 5.1 设备表新增回写配置

建议在 `devices` 表新增字段：

| 字段 | 类型建议 | 是否返回前端 | 说明 |
|---|---|---:|---|
| `board_review_url` | `String(255)` nullable | 管理页可返回 | 板端回写完整地址，例如 `http://192.168.1.250:18080/api/v1/review-result`。 |
| `board_review_token` | `String(255)` nullable | 不给普通列表/详情返回 | 板端接口密钥，只允许后端调用时读取。 |

如果后续要做更严格的安全设计，可以把 `board_review_token` 放到单独密钥表或加密字段；当前 MVP 可先放在 `devices` 表，但前端普通接口不能明文展示。

需要修改：

| 文件 | 修改点 |
|---|---|
| `backend/src/db/models/device.py` | `Device` ORM 增加 `board_review_url`、`board_review_token`。 |
| `backend/src/schemas/device.py` | `DeviceCreateRequest`、`DeviceUpdateRequest` 增加这两个字段；`DeviceResponse` 建议只返回 `board_review_url` 和 `has_board_review_token`，不要返回 token 明文。 |
| `backend/src/services/device_service.py` | 创建设备和更新设备时保存新增字段。 |
| `backend/alembic/versions/<新版本>_board_review_sync.py` | 增加数据库迁移。 |

迁移示例：

```python
"""add board review sync fields

Revision ID: 20260519_0011_board_review_sync
Revises: <当前 head>
Create Date: 2026-05-19
"""

from alembic import op
import sqlalchemy as sa


revision = "20260519_0011_board_review_sync"
down_revision = "<当前 head>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("board_review_url", sa.String(length=255), nullable=True))
    op.add_column("devices", sa.Column("board_review_token", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("devices", "board_review_token")
    op.drop_column("devices", "board_review_url")
```

### 5.2 检测记录表新增同步状态

建议在 `detection_records` 表新增字段，用来追踪“云端复核是否已经成功同步到板端”。

| 字段 | 类型建议 | 说明 |
|---|---|---|
| `board_sync_status` | `String(32)` nullable | `not_required/pending/success/failed`，也可以用枚举。 |
| `board_sync_time` | `DateTime(timezone=True)` nullable | 最近一次同步成功时间。 |
| `board_sync_error` | `Text` nullable | 最近一次失败原因，方便前端展示和排障。 |
| `board_last_synced_review_id` | `Integer` nullable | 可选；记录最后一次同步到板端的 `review_records.id`，避免重复同步旧复核。 |

需要修改：

| 文件 | 修改点 |
|---|---|
| `backend/src/db/models/detection_record.py` | `DetectionRecord` 增加同步状态字段。 |
| `backend/src/schemas/detection_record.py` | `DetectionRecordListItem` 和 `DetectionRecordDetailResponse` 增加同步状态响应字段。 |
| `frontend/src/types/api.ts` | `DetectionRecordDto` / `DetectionRecordDetailDto` 增加 snake_case 字段。 |
| `frontend/src/types/models.ts` | `DetectionRecordModel` 增加 camelCase 字段。 |
| `frontend/src/services/mappers/commonMappers.ts` | 把后端字段映射到前端模型。 |
| `backend/alembic/versions/<新版本>_board_review_sync.py` | 同一迁移中增加这些字段。 |

迁移示例：

```python
def upgrade() -> None:
    op.add_column("devices", sa.Column("board_review_url", sa.String(length=255), nullable=True))
    op.add_column("devices", sa.Column("board_review_token", sa.String(length=255), nullable=True))
    op.add_column(
        "detection_records",
        sa.Column("board_sync_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "detection_records",
        sa.Column("board_sync_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("detection_records", sa.Column("board_sync_error", sa.Text(), nullable=True))
    op.add_column(
        "detection_records",
        sa.Column("board_last_synced_review_id", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("detection_records", "board_last_synced_review_id")
    op.drop_column("detection_records", "board_sync_error")
    op.drop_column("detection_records", "board_sync_time")
    op.drop_column("detection_records", "board_sync_status")
    op.drop_column("devices", "board_review_token")
    op.drop_column("devices", "board_review_url")
```

## 6. 后端接口设计

推荐新增一个独立接口，不直接改旧的人工复核接口。

| 项目 | 内容 |
|---|---|
| 方法 | `POST` |
| 路径 | `/api/v1/records/{record_id}/sync-board-review` |
| 路由文件 | `backend/src/api/routes/reviews.py` |
| 服务文件 | `backend/src/services/review_service.py` |
| 请求体 | 复核结果、修改原因、缺陷类型、复核时间。 |
| 响应体 | 本次复核记录 + 板端同步状态。 |

这样做的好处是：旧的 `manual-review` 仍只负责云端复核；新接口明确表达“提交云端复核并同步板端”。前端详情页可以继续保留原人工复核表单，同时新增一个按钮专门做板端修正。

### 6.1 新增 Schema

建议在 `backend/src/schemas/review.py` 增加：

```python
class BoardReviewSyncRequest(BaseModel):
    """云端复核结果同步板端请求体。"""

    decision: DetectionResult
    cloud_reason: str = Field(min_length=1, max_length=2000)
    defect_type: str | None = Field(default=None, max_length=128)
    reviewed_at: datetime | None = None


class BoardReviewSyncResponse(BaseModel):
    """云端复核结果同步板端响应体。"""

    review: ReviewRecordResponse
    board_sync_status: str
    board_sync_time: datetime | None
    board_sync_error: str | None
```

### 6.2 新增路由

建议在 `backend/src/api/routes/reviews.py` 增加：

```python
@router.post("/records/{record_id}/sync-board-review", response_model=BoardReviewSyncResponse)
def sync_board_review(
    record_id: int,
    payload: BoardReviewSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_user),
) -> BoardReviewSyncResponse:
    """提交云端复核结论，并把结论同步到板端本地历史。"""

    return ReviewService(db).sync_board_review(
        company_id=current_user.company_id or 0,
        record_id=record_id,
        reviewer_id=current_user.id,
        reviewer_name=current_user.display_name or current_user.username,
        payload=payload,
    )
```

## 7. 后端服务逻辑

### 7.1 必须增加 HTTP 客户端依赖

当前 `backend/pyproject.toml` 没有 `httpx` 或 `requests`。推荐新增：

```toml
"httpx>=0.28.1"
```

原因：云端后端需要主动调用板端 HTTP 接口。FastAPI 项目中用 `httpx` 比较合适，后续改异步也方便。

### 7.2 结果枚举映射

云端和板端枚举不完全一样：

| 云端 `DetectionResult` | 发送给板端 `cloud_result` | 说明 |
|---|---|---|
| `good` | `good` | 良品。 |
| `bad` | `bad` | 坏品。 |
| `uncertain` | `review` | 云端待确认或无法明确时，板端显示为待复核。 |

必须集中写一个 helper，不要在多个文件里重复硬编码：

```python
def map_cloud_result_to_board(decision: DetectionResult) -> str:
    """把云端检测结果枚举转换成板端回写接口接受的枚举。"""

    if decision == DetectionResult.UNCERTAIN:
        return "review"
    return decision.value
```

### 7.3 推荐服务流程

`ReviewService.sync_board_review()` 建议按以下顺序实现：

| 步骤 | 动作 | 失败处理 |
|---:|---|---|
| 1 | 查询 `DetectionRecord`，必须带 `device` 关系。 | 不存在返回 `record_not_found`。 |
| 2 | 校验 `cloud_reason.strip()` 非空。 | 返回 422 或业务错误。 |
| 3 | 创建一条 `ReviewRecord`，`comment` 写入修改原因。 | 数据库异常回滚。 |
| 4 | 把 `record.review_status` 改为 `reviewed`。 | 与复核记录同事务提交。 |
| 5 | 检查 `record.device.board_review_url` 是否配置。 | 写 `board_sync_status=failed` 和错误原因，返回给前端。 |
| 6 | 检查 `board_review_token` 是否配置。 | 同上。 |
| 7 | POST 板端接口，超时 3 到 5 秒。 | 网络失败、超时、非 2xx 都写 failed。 |
| 8 | 板端返回 `ok=true` 时写 `board_sync_status=success`、`board_sync_time=now`、清空错误。 | 同步成功。 |
| 9 | 板端返回错误时写 `board_sync_status=failed`、`board_sync_error=<错误摘要>`。 | 云端复核仍保留，前端允许重试。 |

注意：不要因为板端同步失败而撤销云端复核。云端是最终判定来源，板端同步是下游动作，可以失败后重试。

### 7.4 HTTP 调用伪代码

```python
from datetime import datetime, timezone

import httpx


def post_review_to_board(record, review, operator: str, token: str) -> tuple[bool, str | None]:
    """调用板端回写接口，并返回是否成功和错误摘要。"""

    payload = {
        "record_id": str(record.id),
        "record_no": record.record_no,
        "cloud_result": map_cloud_result_to_board(review.decision),
        "cloud_reason": review.comment or "",
        "operator": operator,
        "review_time": review.reviewed_at.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "cloud",
    }

    try:
        response = httpx.post(
            record.device.board_review_url,
            json=payload,
            headers={"X-Board-Token": token},
            timeout=5.0,
        )
    except httpx.TimeoutException:
        return False, "连接板端超时，请检查开发板网络和回写地址。"
    except httpx.RequestError as exc:
        return False, f"连接板端失败：{exc}"

    if response.status_code >= 400:
        return False, f"板端返回 HTTP {response.status_code}：{response.text[:300]}"

    body = response.json()
    if body.get("ok") is not True:
        return False, body.get("error") or body.get("message") or "板端返回失败。"

    return True, None
```

## 8. 前端适配

### 8.1 UI 要求

用户已经明确：这里不是五个按钮，只要一个按钮。

| UI 元素 | 要求 |
|---|---|
| 按钮名称 | 建议叫“修正板端结果”或“同步板端结果”。 |
| 展示位置 | `RecordDetailPage.vue` 的“AI 对话与人工复核”区域，靠近人工复核表单。 |
| 点击行为 | 弹出一个对话框，填写修改原因。 |
| 原因校验 | 原因不能为空，建议最多 2000 字。 |
| 复核结论 | 默认使用当前人工复核表单的结论，或弹窗内提供一个单选组。 |
| 提交后 | 调用后端新接口，成功提示并刷新详情页；失败展示 `board_sync_error`。 |
| 按钮状态 | 同步中禁用；同步成功显示成功状态；失败允许重试。 |

### 8.2 前端类型

在 `frontend/src/types/api.ts` 增加：

```ts
export interface BoardReviewSyncRequestDto {
  decision: DetectionResult;
  cloud_reason: string;
  defect_type?: string | null;
  reviewed_at?: string | null;
}

export interface BoardReviewSyncResponseDto {
  review: ReviewRecordDto;
  board_sync_status: string;
  board_sync_time: string | null;
  board_sync_error: string | null;
}
```

同时给 `DetectionRecordDto` / `DetectionRecordDetailDto` 增加：

```ts
board_sync_status: string | null;
board_sync_time: string | null;
board_sync_error: string | null;
board_last_synced_review_id: number | null;
```

在 `frontend/src/types/models.ts` 增加 camelCase：

```ts
boardSyncStatus: string | null;
boardSyncTime: string | null;
boardSyncError: string | null;
boardLastSyncedReviewId: number | null;
```

在 `frontend/src/services/mappers/commonMappers.ts` 的记录映射函数里补：

```ts
boardSyncStatus: dto.board_sync_status,
boardSyncTime: dto.board_sync_time,
boardSyncError: dto.board_sync_error,
boardLastSyncedReviewId: dto.board_last_synced_review_id,
```

### 8.3 前端 API 封装

在 `frontend/src/services/api/reviews.ts` 增加：

```ts
export function syncBoardReview(
  recordId: number,
  payload: BoardReviewSyncRequestDto,
): Promise<BoardReviewSyncResponseDto> {
  return apiRequest<BoardReviewSyncResponseDto>(
    `/api/v1/records/${recordId}/sync-board-review`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}
```

### 8.4 详情页交互建议

在 `frontend/src/pages/RecordDetailPage.vue` 增加这些状态：

```ts
const boardSyncSubmitting = ref(false);
const boardSyncDialogVisible = ref(false);
const boardSyncReason = ref("");
const boardSyncDecision = ref<DetectionResult>("bad");
```

打开弹窗：

```ts
function openBoardSyncDialog(): void {
  if (!record.value) {
    return;
  }

  boardSyncDecision.value = record.value.effectiveResult;
  boardSyncReason.value = "";
  boardSyncDialogVisible.value = true;
}
```

提交：

```ts
async function submitBoardSync(): Promise<void> {
  if (!record.value) {
    return;
  }

  const reason = boardSyncReason.value.trim();
  if (!reason) {
    ElMessage.error("请填写修正原因");
    return;
  }

  boardSyncSubmitting.value = true;

  try {
    await syncBoardReview(record.value.id, {
      decision: boardSyncDecision.value,
      cloud_reason: reason,
      defect_type: record.value.defectType,
      reviewed_at: new Date().toISOString(),
    });
    ElMessage.success("已同步板端结果");
    boardSyncDialogVisible.value = false;
    await loadRecordDetail();
  } catch (caughtError) {
    ElMessage.error(caughtError instanceof Error ? caughtError.message : "同步板端失败");
  } finally {
    boardSyncSubmitting.value = false;
  }
}
```

模板里只加一个按钮和一个弹窗：

```vue
<ElButton
  type="warning"
  :loading="boardSyncSubmitting"
  @click="openBoardSyncDialog"
>
  修正板端结果
</ElButton>

<ElDialog v-model="boardSyncDialogVisible" title="填写修正原因" width="520px">
  <ElForm label-position="top">
    <ElFormItem label="云端最终结论">
      <ElRadioGroup v-model="boardSyncDecision">
        <ElRadioButton value="good">良品</ElRadioButton>
        <ElRadioButton value="bad">坏品</ElRadioButton>
        <ElRadioButton value="uncertain">待复核</ElRadioButton>
      </ElRadioGroup>
    </ElFormItem>

    <ElFormItem label="修正原因" required>
      <ElInput
        v-model="boardSyncReason"
        type="textarea"
        :rows="5"
        maxlength="2000"
        show-word-limit
        placeholder="例如：云端复核发现边缘划痕，板端原判良品需要修正。"
      />
    </ElFormItem>
  </ElForm>

  <template #footer>
    <ElButton @click="boardSyncDialogVisible = false">取消</ElButton>
    <ElButton type="primary" :loading="boardSyncSubmitting" @click="submitBoardSync">
      确认同步
    </ElButton>
  </template>
</ElDialog>
```

## 9. 零件类型适配规则

板端上传检测记录时会先按云端现有契约调用 `GET /api/v1/parts?limit=100`，能匹配到真实零件类型时把 `part_id` 放进 `POST /api/v1/records`。如果匹配不到，但板端已经能从模型类别归一出真实 `part_code`，则由 `POST /api/v1/records` 携带 `part_code/part_name/part_category/auto_create_part=true`，云端自动创建或复用零件后再创建检测记录。

云端需要坚持以下规则：

| 场景 | 正确做法 | 错误做法 |
|---|---|---|
| 模型输出 `gasket_good` | `part_code=gasket`，`result=good` | 新建零件类型 `gasket_good` |
| 模型输出 `gasket_bad` | `part_code=gasket`，`result=bad` | 新建零件类型 `gasket_bad` |
| 模型输出 `washer_good` | `part_code=washer`，`result=good` | 把它也归到 `gasket` |
| 新增另一种真实零件 | 在 `POST /api/v1/records` 中发送 `part_code/part_name/part_category/auto_create_part=true`，或在云端零件管理手工新增该真实零件，例如 `washer`、`splitwasher`、`wave_washer` | 因为好坏结果不同而新增零件 |

云端排障时看两个位置：

| 字段 | 含义 |
|---|---|
| `records.part_id` | 统计和详情页使用的真实零件类型。 |
| `records.device_context.part_code` | 板端归一后的零件编码，例如 `gasket`。 |
| `records.device_context.class_label` | 模型原始标签，例如 `gasket_bad`。 |

如果上传失败并提示找不到零件类型，先看请求体是否缺少 `part_code` 或 `auto_create_part=true`。板端能确定真实零件编码时，不需要先手工创建零件；云端 `backend/src/services/record_service.py::RecordService._resolve_record_part()` 会在当前公司内按 `part_code` 查询，查不到且 `auto_create_part=true` 时自动创建零件。只有板端完全没有传 `part_code`，或现场明确禁止自动创建时，才需要人工在云端零件管理里创建真实零件类型。

`wave_washer` 的中文名必须使用板端传入或云端归一后的 `part_name=波形垫圈`，分类使用 `part_category=垫圈类`；云端不要自行把它翻译成“电平”。历史训练编码 `gasket` 也代表波形垫圈，业务显示不能按英文词面翻译成“垫片”。

## 10. 设备配置方式

设备管理页需要允许管理员配置板端回写地址和密钥。

| 配置项 | 示例 | 注意事项 |
|---|---|---|
| 板端回写地址 | `http://192.168.1.250:18080/api/v1/review-result` | 地址必须是云端服务器后端能访问到的地址，不是浏览器能访问即可。 |
| 板端回写密钥 | `please-change-this-token` | 与板端 `/root/qt_camera_display/cos-upload.env` 中 `BOARD_REVIEW_TOKEN` 一致。 |

前端设备表单建议：

| 页面/组件 | 修改点 |
|---|---|
| `frontend/src/features/devices/DeviceFormDialog.vue` | 增加“板端回写地址”和“板端回写密钥”输入项。 |
| `frontend/src/pages/DevicesPage.vue` | 设备列表可显示“已配置/未配置回写地址”，不要显示 token 明文。 |
| `frontend/src/services/api/devices.ts` | 创建/更新设备请求体带上新增字段。 |
| `frontend/src/types/api.ts` / `models.ts` | 设备 DTO 和模型增加 `board_review_url`、`has_board_review_token`。 |

## 11. 错误处理和重试

| 失败类型 | 云端保存方式 | 前端提示 |
|---|---|---|
| 原因为空 | 不创建复核，不调用板端。 | “请填写修正原因”。 |
| 记录不存在 | 不创建复核。 | “检测记录不存在”。 |
| 设备未配置回写地址 | 云端复核可保存，`board_sync_status=failed`。 | “当前设备未配置板端回写地址”。 |
| 设备未配置 token | 云端复核可保存，`board_sync_status=failed`。 | “当前设备未配置板端回写密钥”。 |
| 板端 401 | 保存失败状态。 | “板端密钥错误”。 |
| 板端 404 | 保存失败状态。 | “板端找不到对应检测记录，检查 record_id/record_no”。 |
| 板端超时 | 保存失败状态。 | “连接板端超时，可稍后重试”。 |
| 板端 500 | 保存失败状态。 | 展示板端返回摘要，允许重试。 |

重试建议：

| 方案 | 说明 |
|---|---|
| MVP | 仍使用同一个“修正板端结果”按钮，重新填写或沿用原因后再次提交。 |
| 更完整 | 增加“重试同步板端”按钮，使用最新复核记录和原原因，不再创建新复核记录。 |

## 12. 权限和安全

| 项目 | 要求 |
|---|---|
| 调用权限 | 复用 `get_current_company_user` 即可；如果需要更严格，可限制 `reviewer/admin`。 |
| 租户隔离 | 查询记录时必须带 `company_id`，不能跨公司同步。 |
| token 保密 | `board_review_token` 不能出现在普通设备列表、检测详情、浏览器日志中。 |
| 出站 URL 校验 | 最低要求限制为 `http://` 或 `https://`；生产环境建议限制内网网段或设备白名单，避免 SSRF 风险。 |
| 日志 | 可以记录 record_id、device_id、HTTP 状态码；不要记录 token。 |

## 13. 测试与验收

### 13.1 后端单元测试建议

| 测试目标 | 位置 | 断言 |
|---|---|---|
| 创建复核并同步成功 | `backend/tests/test_review_service.py` | 新增 `ReviewRecord`，`record.review_status=reviewed`，`board_sync_status=success`。 |
| 原因为空 | 同上 | 抛出校验错误，不调用板端。 |
| 未配置回写地址 | 同上 | 云端复核保存，`board_sync_status=failed`，错误原因可读。 |
| 板端 401/404/500 | 同上 | 失败状态和错误摘要写入记录。 |
| `uncertain` 映射 | 同上 | 发送给板端的是 `review`，不是 `uncertain`。 |

如果使用 `httpx`，测试里可以 mock `httpx.post()`，不要真的请求开发板。

### 13.2 后端本地验证命令

在 `D:\yunfuwu\backend` 执行：

```powershell
alembic upgrade head
python -m pytest tests
```

启动后端后，先配置设备：

```bash
curl -b cloud_cookie.txt \
  -H "Content-Type: application/json" \
  -X PUT "http://119.91.65.122/api/v1/devices/1" \
  -d '{
    "board_review_url": "http://192.168.1.250:18080/api/v1/review-result",
    "board_review_token": "please-change-this-token"
  }'
```

提交同步请求：

```bash
curl -b cloud_cookie.txt \
  -H "Content-Type: application/json" \
  -X POST "http://119.91.65.122/api/v1/records/123/sync-board-review" \
  -d '{
    "decision": "bad",
    "cloud_reason": "云端复核发现边缘划痕，板端原判良品需要修正。",
    "defect_type": "scratch"
  }'
```

预期：

| 检查项 | 预期 |
|---|---|
| 响应 | `board_sync_status` 为 `success` 或可读的 `failed`。 |
| 云端记录详情 | `effective_result` 变成最新复核结论。 |
| 板端历史 JSON | 对应记录出现 `cloud_review_result`、`cloud_review_reason` 等云端修正字段。 |

### 13.3 前端验收

| 测试目标 | 执行位置 | 操作 | 预期输出/现象 | 失败时排查 |
|---|---|---|---|---|
| 按钮数量 | 云端检测详情页 | 打开任意检测记录 | 只有一个“修正板端结果/同步板端结果”按钮，不出现五个按钮。 | 查 `RecordDetailPage.vue` 是否误把原因选项做成多个按钮。 |
| 原因弹窗 | 云端检测详情页 | 点击按钮 | 弹出原因输入框和最终结论选择。 | 查 `boardSyncDialogVisible` 状态和 Element Plus 弹窗。 |
| 空原因拦截 | 云端检测详情页 | 不填原因直接确认 | 前端提示“请填写修正原因”，不调用后端。 | 查 `submitBoardSync()` 的 trim 校验。 |
| 同步成功 | 云端检测详情页 | 填写原因并确认 | 提示成功，详情页刷新，同步状态为成功。 | 查后端响应、设备回写地址、板端 token。 |
| 同步失败可见 | 断开板端或填错 token 后提交 | 页面显示失败原因，允许再次提交。 | 查 `board_sync_error` 是否返回和映射。 |

### 13.4 板端联调检查

在开发板执行：

```sh
pidof qt_camera_display
grep -n '"record_id"\|"record_no"\|"cloud_review_result"\|"cloud_review_reason"' \
  /mnt/sdcard/images/upload_history.json
```

如果云端同步后板端没有变化，按顺序排查：

| 排查项 | 命令/位置 |
|---|---|
| Qt 程序是否运行 | `pidof qt_camera_display` |
| 板端监听端口 | `netstat -lntp | grep 18080` 或 `ss -lntp | grep 18080` |
| token 是否一致 | 板端 `/root/qt_camera_display/cos-upload.env` 的 `BOARD_REVIEW_TOKEN` 与云端设备配置一致 |
| 记录 ID 是否一致 | 云端 `DetectionRecord.id` 是否等于板端历史里的 `record_id` |
| 记录编号兜底 | 云端 `record_no` 是否等于板端历史里的 `record_no` |

## 14. 推荐实施顺序

| 顺序 | 工作项 | 主要文件 |
|---:|---|---|
| 1 | 加数据库字段和迁移 | `device.py`、`detection_record.py`、`alembic/versions/...` |
| 2 | 加后端 Schema | `schemas/review.py`、`schemas/device.py`、`schemas/detection_record.py` |
| 3 | 加后端同步服务 | `services/review_service.py` |
| 4 | 加后端路由 | `api/routes/reviews.py` |
| 5 | 加后端测试 | `backend/tests/test_review_service.py` |
| 6 | 加前端类型和 API | `types/api.ts`、`types/models.ts`、`services/api/reviews.ts` |
| 7 | 改详情页按钮和弹窗 | `pages/RecordDetailPage.vue` |
| 8 | 改设备配置入口 | `features/devices/DeviceFormDialog.vue`、`pages/DevicesPage.vue` |
| 9 | 联调板端真实接口 | 云端后端、开发板 Qt 程序、`upload_history.json` |

## 15. 最小验收标准

| 编号 | 标准 |
|---:|---|
| 1 | 云端详情页只有一个“修正板端结果”按钮。 |
| 2 | 点击按钮必须弹出原因输入框，原因不能为空。 |
| 3 | 云端保存人工复核记录后，`effective_result` 使用云端最终结论。 |
| 4 | 云端后端能把 `record_id`、`record_no`、`cloud_result`、`cloud_reason`、`operator` 发给板端。 |
| 5 | 云端 `uncertain` 同步给板端时转换为 `review`。 |
| 6 | 同步成功/失败状态能在云端记录详情中看到。 |
| 7 | 板端本地 `/mnt/sdcard/images/upload_history.json` 对应记录出现云端修正结果和原因。 |
| 8 | `gasket_good/gasket_bad` 不会在云端创建两个零件类型，二者都属于同一个 `gasket` 零件。 |

## 16. 2026-05-20 实际落地总结

### 16.1 本次做了什么

| 方向 | 已完成内容 | 关键文件/服务 |
|---|---|---|
| 板端回写服务 | 板端 Qt 程序保留 `POST /api/v1/review-result`，云端修正后可以写回本地 `upload_history.json`。 | `/root/qt_camera_display/qt_camera_display`、`/mnt/sdcard/images/upload_history.json` |
| 板端独立隧道 | 板端开机后主动建立 `ssh -R 127.0.0.1:18081:127.0.0.1:18080`，断线后由板端 monitor 自动重连。 | `/root/qt_camera_display/board-review-tunnel.sh`、`/etc/init.d/S91board-review-tunnel` |
| 云端周期检查 | 云端不负责重连 NAT 后的板端，只每 60 秒检查本机 `127.0.0.1:18081` 是否可达并写日志。 | `/opt/yunduan/scripts/check_board_review_tunnel.sh`、`yunduan-board-review-tunnel-check.timer` |
| 云端后端零件归一 | `gasket` 历史编码显示为“波形垫圈”；`washer` 显示为“平垫圈”；`垫圈类` 只是分类。 | `backend/src/services/part_identity.py`、`part_service.py`、`record_service.py` |
| 云端前端零件分类 | 零件页先显示分类入口，再保留具体零件类型；不会把好坏结果或分类当成具体零件。 | `frontend/src/features/parts/partCategories.ts`、`frontend/src/pages/PartsPage.vue` |
| 长文本显示经验 | 板端小屏和云端页面都不能只截断长复核说明；卡片显示摘要，完整内容放到可滚动详情页/弹层。 | 板端 `historyAnalysisDetailOverlay`；云端详情页/弹窗契约 |

### 16.2 最终连接边界

| 问题 | 结论 |
|---|---|
| 最终是否依赖 Windows 或虚拟机 | 不依赖。Windows/虚拟机只用于开发、部署和调试。 |
| 谁负责建立隧道 | 开发板负责。板端主动连接云服务器并建立 `ssh -R`。 |
| 谁负责断线重连 | 开发板负责。`board-review-tunnel.sh` 的 monitor 循环发现 ssh 进程不存在后重连。 |
| 云服务器负责什么 | 云端后端、nginx 和 systemd timer 常驻；timer 只检查 `127.0.0.1:18081` 是否监听和能否转发到板端。 |
| 云端设备回写地址应该填什么 | `http://127.0.0.1:18081/api/v1/review-result`。这里的 `127.0.0.1` 是云服务器本机。 |
| 为什么不能填 `192.168.1.250` | 这是板端局域网地址，云服务器公网后端访问不到。 |

### 16.3 零件命名经验

| 模型/历史编码 | 正确业务显示 | 说明 |
|---|---|---|
| `gasket`、`gasket_good`、`gasket_bad` | 波形垫圈 | 当时训练命名没起好，不能翻译成“垫片”。 |
| `washer`、`washer_good`、`washer_bad` | 平垫圈 | 平垫圈是另一个真实零件。 |
| `splitwasher` | 弹性垫圈 | 弹性垫圈是另一个真实零件。 |
| `垫圈类` | 分类 | 分类用于聚合展示，不代表一个具体零件。 |

### 16.4 已验证命令

| 测试目标 | 执行位置 | 命令 | 预期输出/现象 | 失败时排查 |
|---|---|---|---|---|
| 板端隧道状态 | 开发板 SSH | `/etc/init.d/S91board-review-tunnel status` | 输出 `monitor: running`、`ssh_tunnel: running`、`remote_forward: 127.0.0.1:18081:127.0.0.1:18080`。 | 查 `/tmp/board-review-tunnel.log`、4G 网络、私钥权限和云端端口占用。 |
| 云端隧道监听 | 云服务器 | `ss -ltnp | grep 127.0.0.1:18081` | 看到 `sshd` 监听云端本机 18081。 | 若没有监听，等待板端重连；再查板端 monitor。 |
| 云端转发探测 | 云服务器 | `curl -i --max-time 5 http://127.0.0.1:18081/api/v1/review-result` | 返回板端 HTTP 404 JSON，说明已经转发到板端服务。 | 若超时查 4G/SSH；若连接拒绝查板端 Qt 18080 服务。 |
| 云端 timer | 云服务器 | `systemctl status yunduan-board-review-tunnel-check.timer; tail -n 80 /var/log/yunduan-board-review-tunnel-check.log` | timer active，日志周期出现 `OK 反向隧道可达`。 | 查 service/timer 是否 enabled、脚本权限和日志路径。 |
| 云端后端零件测试 | 云端后端目录 | `python -m pytest tests/test_part_service.py tests/test_record_service.py tests/test_detection_record_model.py -q` | 测试通过，证明零件归一和记录创建契约稳定。 | 查 `part_identity.py` 映射和 `_resolve_record_part()`。 |
| 云端前端分类测试 | 云端前端目录 | `npm test -- partCategories managementPages` | 测试通过，证明零件分类和管理页显示稳定。 | 查 `partCategories.ts`、`PartsPage.vue` 和 mapper。 |

### 16.5 后续修改必须遵守

| 规则 | 原因 |
|---|---|
| 云端按钮同步失败时不要删除云端复核记录，只更新 `board_sync_status/board_sync_error`。 | 复核结论是云端事实，板端同步只是外部链路状态。 |
| 不要把 `_good/_bad` 当作零件类型。 | 好坏是检测结果，不是物理零件主数据。 |
| 不要把 `gasket` 显示成“垫片”。 | 本项目历史训练中 `gasket` 代表波形垫圈。 |
| 不要把完整复核说明硬塞进固定高度卡片。 | 操作员需要读完整原因；小卡片只负责摘要。 |
| 不要让云端尝试主动重连板端。 | 板端在 NAT/4G 后面，只能由板端主动向云端建立反向隧道。 |
