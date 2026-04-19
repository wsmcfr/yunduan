<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";

import PageHeader from "@/components/common/PageHeader.vue";
import StatusTag from "@/components/common/StatusTag.vue";
import ManualReviewFormCard from "@/features/review/ManualReviewFormCard.vue";
import { requestAiReview, fetchRecordDetail } from "@/services/api/records";
import { createManualReview } from "@/services/api/reviews";
import { mapDetectionRecordDetailDto } from "@/services/mappers/commonMappers";
import type { ManualReviewCreateRequestDto } from "@/types/api";
import type { DetectionRecordModel } from "@/types/models";
import { formatConfidence, formatDateTime } from "@/utils/format";

const route = useRoute();
const loading = ref(false);
const reviewSubmitting = ref(false);
const aiSubmitting = ref(false);
const error = ref("");
const record = ref<DetectionRecordModel | null>(null);
const aiReviewMessage = ref("");

/**
 * 从路由里读取检测记录编号。
 */
const recordId = computed(() => Number(route.params.id));

/**
 * 当前记录是否属于建议复核的疑似样本。
 */
const shouldReview = computed(
  () => record.value?.reviewStatus === "pending" || record.value?.result === "uncertain",
);

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
  aiReviewMessage.value = "";

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
 * 发起云端 AI 复核预留接口。
 * 这里先只打占位接口，后端后续再接真实大模型服务。
 */
async function handleAiReview(): Promise<void> {
  if (!record.value) {
    return;
  }

  aiSubmitting.value = true;

  try {
    const response = await requestAiReview(record.value.id, {
      provider_hint: "cloud-llm",
      note: "由详情页发起疑似样本复核",
    });
    aiReviewMessage.value = response.message;
    ElMessage.success(response.message);
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "AI 复核接口调用失败";
    ElMessage.error(message);
  } finally {
    aiSubmitting.value = false;
  }
}

/**
 * 监听路由参数变化。
 * 当用户在不同记录详情之间切换时，当前页面组件会复用，因此需要主动重新拉取数据。
 */
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
      description="详情页只处理单条样本的证据和复核流程。零件管理页不承担人工审核与大模型审核入口，避免主数据页和检测流程混在一起。"
    />

    <ElAlert
      v-if="error"
      type="error"
      show-icon
      :closable="false"
      :title="error"
    />

    <div v-if="record" class="page-grid two-col">
      <section class="app-panel detail-section">
        <div class="detail-section__header">
          <div>
            <strong>{{ record.recordNo }}</strong>
            <p class="muted-text">当前最终结果默认采用 MP 初检结果；当人工复核存在时，以最新复核结果覆盖展示。</p>
          </div>
          <StatusTag :value="record.effectiveResult" />
        </div>

        <ElDescriptions :column="2" border>
          <ElDescriptionsItem label="零件">
            {{ record.part.name }} / {{ record.part.partCode }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="设备">
            {{ record.device.name }} / {{ record.device.deviceCode }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="MP 初检结果">
            <StatusTag :value="record.result" />
          </ElDescriptionsItem>
          <ElDescriptionsItem label="复核状态">
            <StatusTag :value="record.reviewStatus" />
          </ElDescriptionsItem>
          <ElDescriptionsItem label="最终结果">
            <StatusTag :value="record.effectiveResult" />
          </ElDescriptionsItem>
          <ElDescriptionsItem label="置信度">
            {{ formatConfidence(record.confidenceScore) }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="表面结果">
            {{ record.surfaceResult ?? "未记录" }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="背光结果">
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
            <strong>二次复核</strong>
            <p class="muted-text">建议仅对疑似样本、误检样本或高价值零件启用复核。</p>
          </div>
          <ElTag :type="shouldReview ? 'warning' : 'success'" effect="dark" round>
            {{ shouldReview ? "建议复核" : "当前可直接归档" }}
          </ElTag>
        </div>

        <ElAlert
          type="info"
          show-icon
          :closable="false"
          title="MP157 初检始终是第一道判断。人工复核与云端大模型复核是可选的二次确认流程。"
        />

        <div class="detail-section__actions">
          <ElButton type="primary" plain :loading="aiSubmitting" @click="handleAiReview">
            触发云端 AI 复核
          </ElButton>
          <ElButton @click="loadRecordDetail" :loading="loading">刷新详情</ElButton>
        </div>

        <ElAlert
          v-if="aiReviewMessage"
          type="success"
          show-icon
          :closable="false"
          :title="aiReviewMessage"
        />

        <ManualReviewFormCard
          :submitting="reviewSubmitting"
          :default-decision="record.effectiveResult"
          @submit="handleManualReviewSubmit"
        />
      </section>

      <section class="app-panel detail-section">
        <div class="detail-section__header">
          <strong>文件对象</strong>
          <span class="muted-text">记录源图、标注图与缩略图在 COS 上的对象键</span>
        </div>

        <ElTable :data="record.files ?? []" empty-text="暂无文件对象记录">
          <ElTableColumn prop="fileKind" label="类型" min-width="110" />
          <ElTableColumn prop="objectKey" label="COS 路径" min-width="280" />
          <ElTableColumn label="上传时间" min-width="180">
            <template #default="{ row }">
              {{ formatDateTime(row.uploadedAt) }}
            </template>
          </ElTableColumn>
        </ElTable>
      </section>

      <section class="app-panel detail-section">
        <div class="detail-section__header">
          <strong>复核记录</strong>
          <span class="muted-text">按时间倒序展示人工复核历史</span>
        </div>

        <ElTable :data="record.reviews ?? []" empty-text="暂无复核记录">
          <ElTableColumn prop="reviewerDisplayName" label="复核人" min-width="120" />
          <ElTableColumn label="结论" min-width="120">
            <template #default="{ row }">
              <StatusTag :value="row.decision" />
            </template>
          </ElTableColumn>
          <ElTableColumn prop="defectType" label="缺陷类型" min-width="160" />
          <ElTableColumn prop="comment" label="说明" min-width="220" />
          <ElTableColumn label="复核时间" min-width="180">
            <template #default="{ row }">
              {{ formatDateTime(row.reviewedAt) }}
            </template>
          </ElTableColumn>
        </ElTable>
      </section>
    </div>

    <section v-else-if="loading" class="app-panel detail-section">
      <ElSkeleton animated :rows="8" />
    </section>
  </div>
</template>

<style scoped>
.detail-section {
  display: grid;
  gap: 18px;
  padding: 22px;
}

.detail-section__header,
.detail-section__actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

@media (max-width: 900px) {
  .detail-section__header,
  .detail-section__actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
