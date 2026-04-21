<script setup lang="ts">
import { reactive, ref, watch } from "vue";
import type { FormInstance, FormRules } from "element-plus";

import AppDialog from "@/components/common/AppDialog.vue";
import { detectionResultOptions } from "@/constants/options";
import type { DetectionRecordCreateRequestDto, DetectionResult } from "@/types/api";
import type { DeviceModel, PartModel } from "@/types/models";
import {
  createCurrentDateTimeInputValue,
  normalizeOptionalDateTime,
  normalizeOptionalText,
} from "@/utils/form";

type OptionalResultField = DetectionResult | "" | undefined;

interface RecordCreateFormValue {
  recordNo: string;
  partId: number | undefined;
  deviceId: number | undefined;
  result: DetectionResult;
  surfaceResult: OptionalResultField;
  backlightResult: OptionalResultField;
  eddyResult: OptionalResultField;
  defectType: string;
  defectDesc: string;
  confidenceScore: number | undefined;
  capturedAt: string;
  detectedAt: string;
  uploadedAt: string;
}

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    submitting?: boolean;
    parts: PartModel[];
    devices: DeviceModel[];
  }>(),
  {
    submitting: false,
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  submit: [payload: DetectionRecordCreateRequestDto];
}>();

/**
 * 表单实例。
 */
const formRef = ref<FormInstance>();

/**
 * 检测记录创建表单。
 * 它代表的是 MP 侧初检结果，不在这里做人工或大模型复核。
 */
const formState = reactive<RecordCreateFormValue>(createEmptyForm());

/**
 * 校验规则。
 */
const formRules: FormRules<RecordCreateFormValue> = {
  partId: [{ required: true, message: "请选择零件", trigger: "change" }],
  deviceId: [{ required: true, message: "请选择设备", trigger: "change" }],
  result: [{ required: true, message: "请选择初检结果", trigger: "change" }],
  capturedAt: [{ required: true, message: "请选择拍摄时间", trigger: "change" }],
};

/**
 * 新建空表单。
 */
function createEmptyForm(): RecordCreateFormValue {
  const currentTime = createCurrentDateTimeInputValue();
  return {
    recordNo: "",
    partId: undefined,
    deviceId: undefined,
    result: "good",
    surfaceResult: "",
    backlightResult: "",
    eddyResult: "",
    defectType: "",
    defectDesc: "",
    confidenceScore: undefined,
    capturedAt: currentTime,
    detectedAt: currentTime,
    uploadedAt: "",
  };
}

/**
 * 把可空结果字段转成后端需要的 null。
 */
function normalizeOptionalResult(value: OptionalResultField): DetectionResult | null {
  return value || null;
}

/**
 * 关闭弹窗。
 */
function closeDialog(): void {
  emit("update:modelValue", false);
}

/**
 * 提交记录创建表单。
 */
async function submitForm(): Promise<void> {
  const isValid = await formRef.value?.validate().catch(() => false);
  if (!isValid) {
    return;
  }

  const payload: DetectionRecordCreateRequestDto = {
    record_no: normalizeOptionalText(formState.recordNo),
    part_id: Number(formState.partId),
    device_id: Number(formState.deviceId),
    result: formState.result,
    review_status: "pending",
    surface_result: normalizeOptionalResult(formState.surfaceResult),
    backlight_result: normalizeOptionalResult(formState.backlightResult),
    eddy_result: normalizeOptionalResult(formState.eddyResult),
    defect_type: normalizeOptionalText(formState.defectType),
    defect_desc: normalizeOptionalText(formState.defectDesc),
    confidence_score: formState.confidenceScore ?? null,
    captured_at: formState.capturedAt,
    detected_at: normalizeOptionalDateTime(formState.detectedAt),
    uploaded_at: normalizeOptionalDateTime(formState.uploadedAt),
    storage_last_modified: null,
  };

  emit("submit", payload);
}

/**
 * 每次打开弹窗时重置表单，保证新纪录使用当前时间。
 */
watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      Object.assign(formState, createEmptyForm());
      return;
    }
    formRef.value?.clearValidate();
  },
  { immediate: true },
);
</script>

<template>
  <AppDialog
    :model-value="modelValue"
    title="新增检测记录"
    width="860px"
    destroy-on-close
    @close="closeDialog"
  >
    <div class="dialog-body">
      <ElAlert
        type="info"
        show-icon
        :closable="false"
        title="这里录入的是 MP157 初检结果。疑似样本请在详情页再发起人工复核或云端大模型复核。"
      />

      <ElForm ref="formRef" :model="formState" :rules="formRules" label-position="top">
        <ElRow :gutter="16">
          <ElCol :span="12">
            <ElFormItem label="记录编号">
              <ElInput
                v-model="formState.recordNo"
                placeholder="可留空，后端将自动生成"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem label="MP 初检结果" prop="result">
              <ElSelect v-model="formState.result" placeholder="请选择初检结果">
                <ElOption
                  v-for="option in detectionResultOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </ElSelect>
            </ElFormItem>
          </ElCol>
        </ElRow>

        <ElRow :gutter="16">
          <ElCol :span="12">
            <ElFormItem label="零件" prop="partId">
              <ElSelect v-model="formState.partId" filterable placeholder="请选择零件">
                <ElOption
                  v-for="part in parts"
                  :key="part.id"
                  :label="`${part.name} / ${part.partCode}`"
                  :value="part.id"
                />
              </ElSelect>
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem label="设备" prop="deviceId">
              <ElSelect v-model="formState.deviceId" filterable placeholder="请选择设备">
                <ElOption
                  v-for="device in devices"
                  :key="device.id"
                  :label="`${device.name} / ${device.deviceCode}`"
                  :value="device.id"
                />
              </ElSelect>
            </ElFormItem>
          </ElCol>
        </ElRow>

        <ElRow :gutter="16">
          <ElCol :span="8">
            <ElFormItem label="表面结果">
              <ElSelect v-model="formState.surfaceResult" clearable placeholder="可选">
                <ElOption
                  v-for="option in detectionResultOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </ElSelect>
            </ElFormItem>
          </ElCol>
          <ElCol :span="8">
            <ElFormItem label="背光通道结果">
              <ElSelect v-model="formState.backlightResult" clearable placeholder="可选">
                <ElOption
                  v-for="option in detectionResultOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </ElSelect>
            </ElFormItem>
          </ElCol>
          <ElCol :span="8">
            <ElFormItem label="涡流结果">
              <ElSelect v-model="formState.eddyResult" clearable placeholder="可选">
                <ElOption
                  v-for="option in detectionResultOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </ElSelect>
            </ElFormItem>
          </ElCol>
        </ElRow>

        <ElRow :gutter="16">
          <ElCol :span="12">
            <ElFormItem label="缺陷类型">
              <ElInput v-model="formState.defectType" placeholder="例如 划痕 / 缺口 / 内部黑斑" />
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem label="置信度">
              <ElInputNumber
                v-model="formState.confidenceScore"
                :min="0"
                :max="1"
                :step="0.01"
                :precision="2"
                style="width: 100%"
              />
            </ElFormItem>
          </ElCol>
        </ElRow>

        <ElFormItem label="缺陷说明">
          <ElInput
            v-model="formState.defectDesc"
            type="textarea"
            :rows="4"
            placeholder="补充描述模型观察到的异常位置、特征或人工备注"
          />
        </ElFormItem>

        <ElRow :gutter="16">
          <ElCol :span="8">
            <ElFormItem label="拍摄时间" prop="capturedAt">
              <ElDatePicker
                v-model="formState.capturedAt"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ss"
                format="YYYY-MM-DD HH:mm:ss"
                style="width: 100%"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="8">
            <ElFormItem label="检测完成时间">
              <ElDatePicker
                v-model="formState.detectedAt"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ss"
                format="YYYY-MM-DD HH:mm:ss"
                style="width: 100%"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="8">
            <ElFormItem label="上传完成时间">
              <ElDatePicker
                v-model="formState.uploadedAt"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ss"
                format="YYYY-MM-DD HH:mm:ss"
                placeholder="可选"
                style="width: 100%"
              />
            </ElFormItem>
          </ElCol>
        </ElRow>
      </ElForm>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <ElButton @click="closeDialog">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="submitForm">
          创建记录
        </ElButton>
      </div>
    </template>
  </AppDialog>
</template>

<style scoped>
.dialog-body {
  display: grid;
  gap: 16px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
