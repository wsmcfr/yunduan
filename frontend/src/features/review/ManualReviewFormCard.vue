<script setup lang="ts">
import { reactive, ref, watch } from "vue";
import type { FormInstance, FormRules } from "element-plus";

import { detectionResultOptions } from "@/constants/options";
import type { DetectionResult, ManualReviewCreateRequestDto } from "@/types/api";
import { createCurrentDateTimeInputValue, normalizeOptionalDateTime, normalizeOptionalText } from "@/utils/form";

interface ManualReviewFormValue {
  decision: DetectionResult;
  defectType: string;
  comment: string;
  reviewedAt: string;
}

const props = withDefaults(
  defineProps<{
    submitting?: boolean;
    defaultDecision?: DetectionResult;
  }>(),
  {
    submitting: false,
    defaultDecision: "uncertain",
  },
);

const emit = defineEmits<{
  submit: [payload: ManualReviewCreateRequestDto];
}>();

/**
 * 表单引用。
 */
const formRef = ref<FormInstance>();

/**
 * 人工复核表单状态。
 */
const formState = reactive<ManualReviewFormValue>(createEmptyForm(props.defaultDecision));

/**
 * 校验规则。
 */
const formRules: FormRules<ManualReviewFormValue> = {
  decision: [{ required: true, message: "请选择复核结论", trigger: "change" }],
};

/**
 * 创建默认表单。
 */
function createEmptyForm(defaultDecision: DetectionResult): ManualReviewFormValue {
  return {
    decision: defaultDecision,
    defectType: "",
    comment: "",
    reviewedAt: createCurrentDateTimeInputValue(),
  };
}

/**
 * 将表单恢复为初始状态。
 */
function resetForm(): void {
  Object.assign(formState, createEmptyForm(props.defaultDecision));
  formRef.value?.clearValidate();
}

/**
 * 一键回填当前时间。
 */
function fillCurrentTime(): void {
  formState.reviewedAt = createCurrentDateTimeInputValue();
}

/**
 * 提交人工复核。
 */
async function submitForm(): Promise<void> {
  const isValid = await formRef.value?.validate().catch(() => false);
  if (!isValid) {
    return;
  }

  const payload: ManualReviewCreateRequestDto = {
    decision: formState.decision,
    defect_type: normalizeOptionalText(formState.defectType),
    comment: normalizeOptionalText(formState.comment),
    reviewed_at: normalizeOptionalDateTime(formState.reviewedAt),
  };
  emit("submit", payload);
}

/**
 * 外部默认结论改变时同步表单。
 */
watch(
  () => props.defaultDecision,
  (nextDecision) => {
    resetForm();
    formState.decision = nextDecision;
  },
);
</script>

<template>
  <section class="review-card">
    <div class="review-card__header">
      <div>
        <strong>人工复核</strong>
        <p>当 MP 初检结果不够确定时，在这里给出最终二次结论。</p>
      </div>
      <ElButton text @click="resetForm">重置表单</ElButton>
    </div>

    <ElForm ref="formRef" :model="formState" :rules="formRules" label-position="top">
      <ElFormItem label="复核结论" prop="decision">
        <ElRadioGroup v-model="formState.decision">
          <ElRadioButton
            v-for="option in detectionResultOptions"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </ElRadioButton>
        </ElRadioGroup>
      </ElFormItem>

      <ElRow :gutter="16">
        <ElCol :span="12">
          <ElFormItem label="缺陷类型">
            <ElInput v-model="formState.defectType" placeholder="例如 毛刺 / 划伤 / 内部裂纹" />
          </ElFormItem>
        </ElCol>
        <ElCol :span="12">
          <ElFormItem label="复核时间">
            <div class="review-card__time-row">
              <ElDatePicker
                v-model="formState.reviewedAt"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ss"
                format="YYYY-MM-DD HH:mm:ss"
                style="width: 100%"
              />
              <ElButton plain @click="fillCurrentTime">当前时间</ElButton>
            </div>
          </ElFormItem>
        </ElCol>
      </ElRow>

      <ElFormItem label="复核说明">
        <ElInput
          v-model="formState.comment"
          type="textarea"
          :rows="4"
          placeholder="填写人工判断依据，例如异常位置、是否为误检、复核结论原因"
        />
      </ElFormItem>
    </ElForm>

    <div class="review-card__actions">
      <ElButton type="primary" :loading="submitting" @click="submitForm">提交人工复核</ElButton>
    </div>
  </section>
</template>

<style scoped>
.review-card {
  display: grid;
  gap: 18px;
}

.review-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.review-card__header p {
  margin: 8px 0 0;
  color: var(--app-text-secondary);
  line-height: 1.6;
}

.review-card__time-row {
  display: flex;
  gap: 12px;
}

.review-card__actions {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 900px) {
  .review-card__header,
  .review-card__time-row {
    flex-direction: column;
  }
}
</style>
