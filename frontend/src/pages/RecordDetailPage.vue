<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";

import PageHeader from "@/components/common/PageHeader.vue";
import StatusTag from "@/components/common/StatusTag.vue";
import AiReviewChatDialog from "@/features/review/AiReviewChatDialog.vue";
import ManualReviewFormCard from "@/features/review/ManualReviewFormCard.vue";
import { flattenStructuredContext } from "@/features/review/recordContext";
import { fetchRecordDetail, runCloudDetection } from "@/services/api/records";
import { createManualReview, syncBoardReview } from "@/services/api/reviews";
import { mapDetectionRecordDetailDto } from "@/services/mappers/commonMappers";
import { useAuthStore } from "@/stores/auth";
import type { BoardSyncStatus, DetectionResult, ManualReviewCreateRequestDto } from "@/types/api";
import type { DetectionRecordModel, StructuredContextBlock } from "@/types/models";
import { buildAiPreviewUrl, getAiFileKindLabel, sortAiDisplayFiles } from "@/utils/aiReview";
import { formatConfidence, formatDateTime } from "@/utils/format";

interface RecordPreviewFile {
  id: number;
  fileKind: "source" | "annotated" | "thumbnail";
  label: string;
  objectKey: string;
  uploadedAt: string | null;
  previewUrl: string | null;
}

interface CloudGeneratedFile {
  artifactType: string;
  displayName: string;
  objectKey: string;
  uploadedAt: string | null;
  previewUrl: string | null;
}

interface RecordContextPanel {
  key: string;
  title: string;
  description: string;
  entries: ReturnType<typeof flattenStructuredContext>;
}

const route = useRoute();
const authStore = useAuthStore();
const loading = ref(false);
const reviewSubmitting = ref(false);
const cloudDetectionSubmitting = ref(false);
const boardSyncSubmitting = ref(false);
const boardSyncDialogVisible = ref(false);
const boardSyncDecision = ref<DetectionResult>("bad");
const boardSyncReason = ref("");
const error = ref("");
const record = ref<DetectionRecordModel | null>(null);
const aiDialogVisible = ref(false);

/**
 * 从路由里读取检测记录编号。
 */
const recordId = computed(() => Number(route.params.id));

/**
 * 当前记录是否属于建议优先复核的样本。
 */
const shouldReview = computed(
  () => record.value?.reviewStatus === "pending" || record.value?.result === "uncertain",
);

/**
 * 当前登录账号是否允许发起 AI 分析。
 */
const canUseAiAnalysis = computed(() => authStore.currentUser?.canUseAiAnalysis ?? false);

/**
 * 板端同步状态展示配置。
 */
const boardSyncDisplay = computed(() => {
  const status = record.value?.boardSyncStatus;
  const displayMap: Record<BoardSyncStatus, { label: string; type: "success" | "warning" | "danger" | "info" }> = {
    not_required: { label: "无需同步", type: "info" },
    pending: { label: "待同步", type: "warning" },
    success: { label: "同步成功", type: "success" },
    failed: { label: "同步失败", type: "danger" },
  };
  return status ? displayMap[status] : { label: "未同步", type: "info" as const };
});

/**
 * 只有云端最终结果与 MP 初检结果不一致时，才突出提示需要修正板端。
 */
const shouldShowBoardCorrectionHint = computed(() => {
  if (!record.value) {
    return false;
  }
  return record.value.effectiveResult !== record.value.result;
});

/**
 * 当前记录中可直接预览的图片对象。
 * 这里复用 AI 对话的排序规则，保持“标注图 -> 源图 -> 缩略图”的一致体验。
 */
const previewFiles = computed<RecordPreviewFile[]>(() => {
  if (!record.value?.files) {
    return [];
  }

  return sortAiDisplayFiles(record.value.files)
    .filter((file) => ["annotated", "source", "thumbnail"].includes(file.fileKind))
    .map((file) => ({
      id: file.id,
      fileKind: file.fileKind,
      label: getAiFileKindLabel(file.fileKind),
      objectKey: file.objectKey,
      uploadedAt: file.uploadedAt,
      previewUrl: buildAiPreviewUrl(file),
    }));
});

/**
 * 解析云端检测上下文里的生成图列表。
 *
 * 返回:
 *   只返回具备 COS 路径或预览地址的云端产物图，用于在详情页单独展示，方便和板端上传图片对比。
 */
const cloudGeneratedFiles = computed<CloudGeneratedFile[]>(() => {
  const generatedFiles = record.value?.cloudDetectionContext?.generated_files;
  if (!generatedFiles) {
    return [];
  }

  return generatedFiles
    .map((item) => {
      const artifactType = typeof item.artifact_type === "string" ? item.artifact_type : "";
      const displayName = typeof item.display_name === "string" ? item.display_name : artifactType;
      const objectKey = typeof item.object_key === "string" ? item.object_key : "";
      const uploadedAt = typeof item.uploaded_at === "string" ? item.uploaded_at : null;
      const previewUrl = buildAiPreviewUrl({
        previewUrl: typeof item.preview_url === "string" ? item.preview_url : null,
        objectKey,
        bucketName: typeof item.bucket_name === "string" ? item.bucket_name : "",
        region: typeof item.region === "string" ? item.region : "",
      });

      return {
        artifactType,
        displayName: displayName || "云端检测生成图",
        objectKey,
        uploadedAt,
        previewUrl,
      };
    })
    .filter((item) => item.objectKey || item.previewUrl);
});

/**
 * 将四类结构化上下文整理成统一的页面板块配置。
 * 这样模板层只负责渲染，不再散落大量字段判断。
 */
const contextPanels = computed<RecordContextPanel[]>(() => [
  {
    key: "vision",
    title: "视觉检测上下文",
    description: "展示边缘侧视觉模型、通道结果、局部判定和图像侧依据。",
    entries: flattenStructuredContext(record.value?.visionContext),
  },
  {
    key: "sensor",
    title: "传感器上下文",
    description: "展示 F4 或其他传感器上传的原始值、阈值、计算结果和越界信息。",
    entries: flattenStructuredContext(record.value?.sensorContext),
  },
  {
    key: "decision",
    title: "判定依据上下文",
    description: "展示最终为什么会判成良品、不良或待确认，而不是只给一个结果。",
    entries: flattenStructuredContext(record.value?.decisionContext),
  },
  {
    key: "device",
    title: "设备上传上下文",
    description: "展示设备任务号、批次号、固件版本、采集参数等运行信息。",
    entries: flattenStructuredContext(record.value?.deviceContext),
  },
  {
    key: "cloud-detection",
    title: "云端模型检测上下文",
    description: "展示云端 ONNX 复检摘要、分类/分割结果、与板端初检的对比以及生成图路径。",
    entries: flattenStructuredContext(record.value?.cloudDetectionContext as StructuredContextBlock | null),
  },
]);

/**
 * 拉取详情页数据。
 */
async function loadRecordDetail(): Promise<void> {
  if (!Number.isFinite(recordId.value)) {
    error.value = "路由中的记录编号无效";
    return;
  }

  loading.value = true;
  error.value = "";

  try {
    const response = await fetchRecordDetail(recordId.value);
    record.value = mapDetectionRecordDetailDto(response);
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : "记录详情加载失败";
  } finally {
    loading.value = false;
  }
}

/**
 * 提交人工复核。
 */
async function handleManualReviewSubmit(payload: ManualReviewCreateRequestDto): Promise<void> {
  if (!record.value) {
    return;
  }

  reviewSubmitting.value = true;

  try {
    await createManualReview(record.value.id, payload);
    ElMessage.success("人工复核已提交");
    await loadRecordDetail();
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "人工复核提交失败";
    ElMessage.error(message);
  } finally {
    reviewSubmitting.value = false;
  }
}

/**
 * 手动重新运行云端 ONNX 模型检测。
 *
 * 主要流程:
 * 1. 防止无记录或重复点击；
 * 2. 调用后端重新下载当前记录图片、运行分类与分割模型；
 * 3. 用后端返回的完整详情刷新页面上的检测信息和生成图；
 * 4. 根据后端上下文状态提示用户本次检测是否成功。
 *
 * 返回:
 *   无返回值；成功时会更新 `record`。
 */
async function handleRunCloudDetection(): Promise<void> {
  if (!record.value || cloudDetectionSubmitting.value) {
    return;
  }

  cloudDetectionSubmitting.value = true;

  try {
    const response = await runCloudDetection(record.value.id);
    record.value = mapDetectionRecordDetailDto(response);
    const cloudContext = record.value.cloudDetectionContext;
    if (cloudContext?.status === "success") {
      ElMessage.success("云端模型检测已完成");
    } else if (cloudContext?.status === "skipped") {
      ElMessage.warning(cloudContext.summary_text ?? "云端模型检测已跳过");
    } else {
      ElMessage.warning(cloudContext?.summary_text ?? "云端模型检测未成功完成，请查看上下文详情");
    }
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "云端模型检测失败";
    ElMessage.error(message);
  } finally {
    cloudDetectionSubmitting.value = false;
  }
}

/**
 * 打开板端修正弹窗。
 */
function openBoardSyncDialog(): void {
  if (!record.value) {
    return;
  }

  boardSyncDecision.value = record.value.effectiveResult;
  boardSyncReason.value = "";
  boardSyncDialogVisible.value = true;
}

/**
 * 提交云端复核并同步板端结果。
 */
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
    const response = await syncBoardReview(record.value.id, {
      decision: boardSyncDecision.value,
      cloud_reason: reason,
      defect_type: record.value.defectType,
      reviewed_at: new Date().toISOString(),
    });
    if (response.board_sync_status === "success") {
      ElMessage.success("已同步板端结果");
    } else {
      ElMessage.warning(response.board_sync_error ?? "云端复核已保存，但板端同步失败");
    }
    boardSyncDialogVisible.value = false;
    await loadRecordDetail();
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "同步板端失败";
    ElMessage.error(message);
  } finally {
    boardSyncSubmitting.value = false;
  }
}

/**
 * 打开 AI 对话弹窗。
 */
function openAiDialog(): void {
  if (!record.value || !canUseAiAnalysis.value) {
    return;
  }
  aiDialogVisible.value = true;
}

watch(
  () => recordId.value,
  () => {
    void loadRecordDetail();
  },
  { immediate: true },
);
</script>

<template>
  <div class="page-grid">
    <PageHeader
      eyebrow="Detail"
      title="检测详情"
      description="这里是单条样本的完整复检工作区：不仅展示结果，还展示图片证据、视觉/传感器/判定/设备四类上下文，再决定是否人工复核或继续追问 AI。"
    />

    <ElAlert
      v-if="error"
      type="error"
      show-icon
      :closable="false"
      :title="error"
    />

    <div v-if="record" class="detail-page">
      <section class="app-panel detail-section">
        <div class="detail-section__header">
          <div>
            <strong>{{ record.recordNo }}</strong>
            <p class="muted-text">
              当前样本对应 {{ record.part.name }} / {{ record.part.partCode }}。详情页会把初检结果、最终结果、结构化上下文和人工复核一起放在同一个工作区里。
            </p>
          </div>
          <div class="detail-section__header-tags">
            <StatusTag :value="record.result" />
            <StatusTag :value="record.effectiveResult" />
            <StatusTag :value="record.reviewStatus" />
          </div>
        </div>

        <ElDescriptions :column="2" border>
          <ElDescriptionsItem label="零件类型">
            {{ record.part.name }} / {{ record.part.partCode }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="设备">
            {{ record.device.name }} / {{ record.device.deviceCode }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="MP 初检结果">
            <StatusTag :value="record.result" />
          </ElDescriptionsItem>
          <ElDescriptionsItem label="当前最终结果">
            <StatusTag :value="record.effectiveResult" />
          </ElDescriptionsItem>
          <ElDescriptionsItem label="复核状态">
            <StatusTag :value="record.reviewStatus" />
          </ElDescriptionsItem>
          <ElDescriptionsItem label="置信度">
            {{ formatConfidence(record.confidenceScore) }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="表面结果">
            {{ record.surfaceResult ?? "未记录" }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="背光通道结果">
            {{ record.backlightResult ?? "未记录" }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="涡流结果">
            {{ record.eddyResult ?? "未记录" }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="缺陷类型">
            {{ record.defectType ?? "未记录" }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="拍摄时间">
            {{ formatDateTime(record.capturedAt) }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="检测完成">
            {{ formatDateTime(record.detectedAt) }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="上传完成">
            {{ formatDateTime(record.uploadedAt) }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="对象最后修改">
            {{ formatDateTime(record.storageLastModified) }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="板端同步状态">
            <div class="board-sync-status">
              <ElTag :type="boardSyncDisplay.type" effect="dark" round>
                {{ boardSyncDisplay.label }}
              </ElTag>
              <span v-if="record.boardSyncTime" class="muted-text">
                {{ formatDateTime(record.boardSyncTime) }}
              </span>
            </div>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="板端同步错误">
            {{ record.boardSyncError ?? "无" }}
          </ElDescriptionsItem>
        </ElDescriptions>

        <ElInput
          v-if="record.defectDesc"
          :model-value="record.defectDesc"
          type="textarea"
          :rows="4"
          readonly
        />
      </section>

      <section class="app-panel detail-section">
        <div class="detail-section__header">
          <div>
            <strong>图片证据</strong>
            <p class="muted-text">
              如果这条记录登记了多张图片，这里可以直接左右切换查看。人工复核和 AI 对话都围绕这些图片证据展开。
            </p>
          </div>
          <ElTag effect="dark" round type="info">
            共 {{ previewFiles.length }} 张
          </ElTag>
        </div>

        <ElEmpty
          v-if="previewFiles.length === 0"
          description="当前记录还没有可预览的图片对象。"
        />

        <div v-else class="detail-preview">
          <ElCarousel
            class="detail-preview__carousel"
            arrow="always"
            indicator-position="outside"
            height="360px"
          >
            <ElCarouselItem
              v-for="file in previewFiles"
              :key="file.id"
            >
              <div class="detail-preview__slide">
                <ElImage
                  v-if="file.previewUrl"
                  :src="file.previewUrl"
                  fit="contain"
                  class="detail-preview__image"
                >
                  <template #error>
                    <div class="detail-preview__fallback">
                      <strong>{{ file.label }}</strong>
                      <p>当前对象已登记，但浏览器无法直接预览该文件。</p>
                      <code>{{ file.objectKey }}</code>
                    </div>
                  </template>
                </ElImage>

                <div v-else class="detail-preview__fallback">
                  <strong>{{ file.label }}</strong>
                  <p>当前对象没有可直接访问的预览地址。</p>
                  <code>{{ file.objectKey }}</code>
                </div>
              </div>
            </ElCarouselItem>
          </ElCarousel>

          <div class="detail-preview__mobile-list">
            <article
              v-for="file in previewFiles"
              :key="`mobile-${file.id}`"
              class="detail-preview__mobile-card"
            >
              <div class="detail-preview__meta-head">
                <strong>{{ file.label }}</strong>
                <ElTag effect="dark" round>{{ formatDateTime(file.uploadedAt) }}</ElTag>
              </div>

              <ElImage
                v-if="file.previewUrl"
                :src="file.previewUrl"
                :alt="file.label"
                fit="contain"
                class="detail-preview__mobile-image"
              >
                <template #error>
                  <div class="detail-preview__fallback">
                    <strong>{{ file.label }}</strong>
                    <p>当前对象已登记，但浏览器无法直接预览该文件。</p>
                    <code>{{ file.objectKey }}</code>
                  </div>
                </template>
              </ElImage>

              <div v-else class="detail-preview__fallback">
                <strong>{{ file.label }}</strong>
                <p>当前对象没有可直接访问的预览地址。</p>
              </div>

              <code>{{ file.objectKey }}</code>
            </article>
          </div>

          <div class="detail-preview__meta-list">
            <article
              v-for="file in previewFiles"
              :key="`meta-${file.id}`"
              class="detail-preview__meta-card"
            >
              <div class="detail-preview__meta-head">
                <strong>{{ file.label }}</strong>
                <ElTag effect="dark" round>{{ formatDateTime(file.uploadedAt) }}</ElTag>
              </div>
              <code>{{ file.objectKey }}</code>
            </article>
          </div>

          <div class="detail-preview__print-list">
            <article
              v-for="file in previewFiles"
              :key="`print-${file.id}`"
              class="detail-preview__print-card"
            >
              <div class="detail-preview__meta-head">
                <strong>{{ file.label }}</strong>
                <ElTag effect="dark" round>{{ formatDateTime(file.uploadedAt) }}</ElTag>
              </div>

              <img
                v-if="file.previewUrl"
                :src="file.previewUrl"
                :alt="file.label"
                class="detail-preview__print-image"
              >

              <div v-else class="detail-preview__fallback">
                <strong>{{ file.label }}</strong>
                <p>当前对象没有可直接访问的预览地址。</p>
              </div>

              <code>{{ file.objectKey }}</code>
            </article>
          </div>
        </div>
      </section>

      <section class="app-panel detail-section">
        <div class="detail-section__header">
          <div>
            <strong>云端检测生成图</strong>
            <p class="muted-text">
              云端重新检测会把 UNet 叠加图、mask 图和 MobileNetV3-Small 分类结果图上传到 COS。手动重新跑模型后，同一记录的这些图片会被当前结果覆盖。
            </p>
          </div>
          <ElTag effect="dark" round type="success">
            {{ cloudGeneratedFiles.length > 0 ? `${cloudGeneratedFiles.length} 张` : "暂无生成图" }}
          </ElTag>
        </div>

        <ElEmpty
          v-if="cloudGeneratedFiles.length === 0"
          description="当前记录还没有云端检测生成图。上传板端图片后会自动触发一次，也可以点击重新进行云端检测。"
        />

        <div v-else class="cloud-generated-grid">
          <article
            v-for="file in cloudGeneratedFiles"
            :key="file.objectKey || file.artifactType"
            class="cloud-generated-card"
          >
            <div class="detail-preview__meta-head">
              <strong>{{ file.displayName }}</strong>
              <ElTag effect="dark" round>{{ formatDateTime(file.uploadedAt) }}</ElTag>
            </div>

            <ElImage
              v-if="file.previewUrl"
              :src="file.previewUrl"
              :alt="file.displayName"
              fit="contain"
              class="cloud-generated-card__image"
            >
              <template #error>
                <div class="detail-preview__fallback">
                  <strong>{{ file.displayName }}</strong>
                  <p>云端生成图已登记到 COS，但当前浏览器无法直接预览。</p>
                  <code>{{ file.objectKey }}</code>
                </div>
              </template>
            </ElImage>

            <div v-else class="detail-preview__fallback">
              <strong>{{ file.displayName }}</strong>
              <p>云端生成图缺少可直接访问的预览地址。</p>
            </div>

            <code>{{ file.objectKey }}</code>
          </article>
        </div>
      </section>

      <section
        v-for="panel in contextPanels"
        :key="panel.key"
        class="app-panel detail-section"
      >
        <div class="detail-section__header">
          <div>
            <strong>{{ panel.title }}</strong>
            <p class="muted-text">{{ panel.description }}</p>
          </div>
          <ElTag effect="dark" round>
            {{ panel.entries.length > 0 ? `${panel.entries.length} 项` : "未上报" }}
          </ElTag>
        </div>

        <ElEmpty
          v-if="panel.entries.length === 0"
          description="当前设备还没有上报这部分结构化上下文。"
        />

        <div v-else class="detail-context">
          <article
            v-for="entry in panel.entries"
            :key="entry.keyPath"
            class="detail-context__item"
          >
            <span class="detail-context__label">{{ entry.label }}</span>
            <strong class="detail-context__value">{{ entry.valueText }}</strong>
          </article>
        </div>
      </section>

      <section class="app-panel detail-section detail-section--wide">
        <div class="detail-section__header">
          <div>
            <strong>AI 对话与人工复核</strong>
            <p class="muted-text">
              先让 AI 结合图片和上下文分析，再决定人工是否改判。当前页面会把所有证据留在同一工作区，不需要来回切页对照。
            </p>
          </div>
          <ElTag :type="shouldReview ? 'warning' : 'success'" effect="dark" round>
            {{ shouldReview ? "建议优先复核" : "当前可直接归档" }}
          </ElTag>
        </div>

        <div class="detail-review-workspace">
          <div class="detail-review-workspace__assistant">
            <p class="muted-text">
              AI 对话会自动读取当前零件、图片对象、初检结果、最终结果、结构化上下文和复核历史。你可以直接追问“为什么判成这样”“传感器值是否支持这个结论”“人工应该重点看哪张图”。
            </p>

            <ElAlert
              v-if="!canUseAiAnalysis"
              type="warning"
              show-icon
              :closable="false"
              title="当前账号未开通 AI 复核分析"
              description="你仍然可以查看图片与上下文并直接做人审，但无法发起 AI 对话。请联系管理员在系统设置中开启该权限。"
            />

            <div class="detail-review-workspace__assistant-tags">
              <ElTag type="info" effect="dark" round>自动带入当前记录上下文</ElTag>
              <ElTag type="warning" effect="dark" round>支持围绕当前图片和判定依据追问</ElTag>
              <ElTag type="success" effect="dark" round>适合先分析再人工复核</ElTag>
            </div>

            <div class="detail-review-workspace__assistant-actions">
              <ElButton
                type="primary"
                plain
                :disabled="!canUseAiAnalysis"
                @click="openAiDialog"
              >
                打开 AI 对话分析
              </ElButton>
              <ElButton
                type="warning"
                plain
                :loading="cloudDetectionSubmitting"
                @click="handleRunCloudDetection"
              >
                重新进行云端检测
              </ElButton>
              <ElButton
                type="warning"
                plain
                :loading="boardSyncSubmitting"
                @click="openBoardSyncDialog"
              >
                修正板端结果
              </ElButton>
              <ElButton @click="loadRecordDetail" :loading="loading">刷新详情</ElButton>
            </div>

            <ElAlert
              v-if="shouldShowBoardCorrectionHint"
              type="warning"
              show-icon
              :closable="false"
              title="云端最终结论与 MP 初检结果不一致"
              description="如需让开发板历史记录显示云端最终结论，请使用“修正板端结果”并填写原因。"
            />

            <ElAlert
              v-if="record.boardSyncStatus === 'failed' && record.boardSyncError"
              type="error"
              show-icon
              :closable="false"
              title="最近一次板端同步失败"
              :description="record.boardSyncError"
            />
          </div>

          <ManualReviewFormCard
            :submitting="reviewSubmitting"
            :default-decision="record.effectiveResult"
            @submit="handleManualReviewSubmit"
          />
        </div>
      </section>

      <section class="app-panel detail-section detail-section--wide">
        <div class="detail-section__header">
          <strong>复核记录</strong>
          <span class="muted-text">按时间倒序展示人工复核历史，便于追溯最终结论的变化过程。</span>
        </div>

        <ElTable :data="record.reviews ?? []" empty-text="暂无复核记录">
          <ElTableColumn prop="reviewerDisplayName" label="复核人" min-width="120" />
          <ElTableColumn label="结论" min-width="120">
            <template #default="{ row }">
              <StatusTag :value="row.decision" />
            </template>
          </ElTableColumn>
          <ElTableColumn prop="defectType" label="缺陷类型" min-width="160" />
          <ElTableColumn prop="comment" label="说明" min-width="260" />
          <ElTableColumn label="复核时间" min-width="180">
            <template #default="{ row }">
              {{ formatDateTime(row.reviewedAt) }}
            </template>
          </ElTableColumn>
        </ElTable>
      </section>

      <section class="app-panel detail-section detail-section--wide">
        <div class="detail-section__header">
          <strong>文件对象清单</strong>
          <span class="muted-text">保留原始对象元数据，便于排查 COS 路径、上传时间和文件类型是否一致。</span>
        </div>

        <ElTable :data="record.files ?? []" empty-text="暂无文件对象记录">
          <ElTableColumn prop="fileKind" label="类型" min-width="110" />
          <ElTableColumn prop="objectKey" label="COS 路径" min-width="300" />
          <ElTableColumn label="上传时间" min-width="180">
            <template #default="{ row }">
              {{ formatDateTime(row.uploadedAt) }}
            </template>
          </ElTableColumn>
          <ElTableColumn label="最后修改" min-width="180">
            <template #default="{ row }">
              {{ formatDateTime(row.storageLastModified) }}
            </template>
          </ElTableColumn>
        </ElTable>
      </section>
    </div>

    <section v-else-if="loading" class="app-panel detail-section">
      <ElSkeleton animated :rows="10" />
    </section>

    <AiReviewChatDialog
      v-model="aiDialogVisible"
      :record="record"
    />

    <ElDialog
      v-model="boardSyncDialogVisible"
      title="修正板端结果"
      width="520px"
      destroy-on-close
    >
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
        <div class="detail-dialog-footer">
          <ElButton @click="boardSyncDialogVisible = false">取消</ElButton>
          <ElButton type="primary" :loading="boardSyncSubmitting" @click="submitBoardSync">
            确认同步
          </ElButton>
        </div>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.detail-page {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.detail-section {
  display: grid;
  gap: 18px;
  padding: 22px;
}

.detail-section--wide {
  grid-column: 1 / -1;
}

.detail-section__header,
.detail-section__header-tags,
.detail-preview__meta-head,
.detail-review-workspace__assistant-actions,
.board-sync-status,
.detail-dialog-footer {
  display: flex;
  gap: 14px;
}

.detail-section__header,
.detail-preview__meta-head {
  align-items: flex-start;
  justify-content: space-between;
}

.detail-section__header-tags,
.detail-review-workspace__assistant-tags,
.board-sync-status {
  flex-wrap: wrap;
}

.detail-section__header p {
  margin: 8px 0 0;
  line-height: 1.7;
}

.detail-preview,
.detail-preview__meta-list,
.detail-preview__mobile-list,
.detail-preview__print-list,
.cloud-generated-grid,
.detail-context,
.detail-review-workspace,
.detail-review-workspace__assistant,
.detail-review-workspace__assistant-tags {
  display: grid;
  gap: 16px;
}

.detail-preview__slide {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  border-radius: 18px;
  overflow: hidden;
  background:
    radial-gradient(circle at top left, rgba(255, 138, 31, 0.16), transparent 42%),
    rgba(255, 255, 255, 0.03);
}

.detail-preview__image {
  width: 100%;
  height: 100%;
}

.detail-preview__fallback {
  min-height: 280px;
  width: 100%;
  display: grid;
  place-content: center;
  gap: 10px;
  padding: 24px;
  text-align: center;
  color: var(--app-text-secondary);
}

.detail-preview__fallback code,
.detail-preview__meta-card code {
  max-width: 100%;
  white-space: normal;
  word-break: break-all;
  color: var(--app-text);
}

.detail-preview__meta-list {
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.cloud-generated-grid {
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.detail-preview__meta-card,
.detail-preview__print-card,
.cloud-generated-card,
.detail-context__item {
  display: grid;
  gap: 10px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  background: rgba(255, 255, 255, 0.02);
}

.cloud-generated-card {
  min-width: 0;
}

.cloud-generated-card code {
  max-width: 100%;
  white-space: normal;
  word-break: break-all;
  color: var(--app-text);
}

.cloud-generated-card__image {
  width: 100%;
  aspect-ratio: 4 / 3;
  min-height: 220px;
  max-height: 320px;
  overflow: hidden;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.03);
}

.detail-context {
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}

.detail-context__label {
  color: var(--app-text-secondary);
  line-height: 1.6;
}

.detail-context__value {
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-review-workspace {
  grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
  align-items: start;
}

.detail-review-workspace__assistant {
  padding: 18px;
  border-radius: 18px;
  border: 1px solid rgba(255, 138, 31, 0.14);
  background:
    radial-gradient(circle at top right, rgba(255, 138, 31, 0.1), transparent 36%),
    rgba(255, 255, 255, 0.02);
}

.detail-review-workspace__assistant p {
  margin: 0;
  line-height: 1.8;
}

.board-sync-status {
  align-items: center;
}

.detail-dialog-footer {
  justify-content: flex-end;
}

.detail-preview__print-list {
  display: none;
}

.detail-preview__mobile-list {
  display: none;
}

.detail-preview__print-image {
  width: 100%;
  max-height: none;
  object-fit: contain;
  border-radius: 14px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  background: rgba(255, 255, 255, 0.02);
}

@media (max-width: 1280px) {
  .detail-page,
  .detail-review-workspace {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .detail-section__header,
  .detail-preview__meta-head,
  .detail-review-workspace__assistant-actions,
  .detail-dialog-footer {
    flex-direction: column;
    align-items: stretch;
  }

  .detail-context,
  .detail-preview__meta-list,
  .cloud-generated-grid {
    grid-template-columns: 1fr;
  }

  /**
   * 移动端不用 Element Plus 轮播承载证据图。
   * 轮播会把非激活项定位到视口外，视觉上被裁掉但仍容易形成右溢检测和触控误判。
   */
  .detail-preview__carousel,
  .detail-preview__meta-list {
    display: none;
  }

  .detail-preview__mobile-list {
    display: grid;
    grid-template-columns: 1fr;
  }

  .detail-preview__mobile-card {
    display: grid;
    gap: 12px;
    min-width: 0;
    padding: 14px;
    border: 1px solid rgba(149, 184, 223, 0.12);
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.02);
  }

  .detail-preview__mobile-card code {
    max-width: 100%;
    white-space: normal;
    word-break: break-all;
    color: var(--app-text);
  }

  .detail-preview__mobile-image {
    width: 100%;
    aspect-ratio: 4 / 3;
    min-height: 180px;
    max-height: min(46dvh, 320px);
    overflow: hidden;
    border-radius: 14px;
    background: rgba(255, 255, 255, 0.03);
  }
}

@media print {
  .detail-page,
  .detail-review-workspace,
  .detail-context,
  .detail-preview__meta-list,
  .detail-preview__print-list {
    grid-template-columns: 1fr !important;
  }

  .detail-review-workspace__assistant-actions,
  .detail-section :deep(.el-carousel),
  .detail-preview__meta-list {
    display: none !important;
  }

  .detail-preview__print-list {
    display: grid !important;
  }

  .detail-section__header,
  .detail-preview__meta-head {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
