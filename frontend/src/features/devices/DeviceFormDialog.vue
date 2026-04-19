<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import type { FormInstance, FormRules } from "element-plus";

import { deviceStatusOptions, deviceTypeOptions } from "@/constants/options";
import type { DeviceCreateRequestDto, DeviceUpdateRequestDto } from "@/types/api";
import type { DeviceModel } from "@/types/models";
import { formatDateTimeInputValue, normalizeOptionalDateTime, normalizeOptionalText } from "@/utils/form";

interface DeviceFormValue {
  deviceCode: string;
  name: string;
  deviceType: DeviceCreateRequestDto["device_type"];
  status: DeviceCreateRequestDto["status"];
  firmwareVersion: string;
  ipAddress: string;
  lastSeenAt: string;
}

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    submitting?: boolean;
    initialValue?: DeviceModel | null;
  }>(),
  {
    submitting: false,
    initialValue: null,
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  submit: [payload: DeviceCreateRequestDto | DeviceUpdateRequestDto];
}>();

/**
 * 表单实例。
 */
const formRef = ref<FormInstance>();

/**
 * 当前编辑模式。
 */
const mode = computed(() => (props.initialValue ? "edit" : "create"));

/**
 * 弹窗标题。
 */
const dialogTitle = computed(() => (mode.value === "create" ? "新增设备" : "编辑设备"));

/**
 * 设备表单状态。
 */
const formState = reactive<DeviceFormValue>(createEmptyForm());

/**
 * 设备表单校验规则。
 */
const formRules: FormRules<DeviceFormValue> = {
  deviceCode: [
    { required: true, message: "请输入设备编码", trigger: "blur" },
    { min: 2, max: 64, message: "设备编码长度需在 2 到 64 个字符之间", trigger: "blur" },
  ],
  name: [
    { required: true, message: "请输入设备名称", trigger: "blur" },
    { min: 1, max: 128, message: "设备名称长度需在 1 到 128 个字符之间", trigger: "blur" },
  ],
  deviceType: [{ required: true, message: "请选择设备类型", trigger: "change" }],
  status: [{ required: true, message: "请选择设备状态", trigger: "change" }],
};

/**
 * 新建设备时的默认表单。
 */
function createEmptyForm(): DeviceFormValue {
  return {
    deviceCode: "",
    name: "",
    deviceType: "mp157",
    status: "online",
    firmwareVersion: "",
    ipAddress: "",
    lastSeenAt: "",
  };
}

/**
 * 把设备模型映射为可编辑表单。
 */
function createFormFromModel(model: DeviceModel): DeviceFormValue {
  return {
    deviceCode: model.deviceCode,
    name: model.name,
    deviceType: model.deviceType,
    status: model.status,
    firmwareVersion: model.firmwareVersion ?? "",
    ipAddress: model.ipAddress ?? "",
    lastSeenAt: formatDateTimeInputValue(model.lastSeenAt),
  };
}

/**
 * 同步当前表单值。
 */
function syncFormState(): void {
  const nextValue = props.initialValue
    ? createFormFromModel(props.initialValue)
    : createEmptyForm();
  Object.assign(formState, nextValue);
}

/**
 * 关闭弹窗。
 */
function closeDialog(): void {
  emit("update:modelValue", false);
}

/**
 * 提交设备表单。
 */
async function submitForm(): Promise<void> {
  const isValid = await formRef.value?.validate().catch(() => false);
  if (!isValid) {
    return;
  }

  const payloadBase = {
    device_code: formState.deviceCode.trim(),
    name: formState.name.trim(),
    device_type: formState.deviceType,
    status: formState.status,
    firmware_version: normalizeOptionalText(formState.firmwareVersion),
    ip_address: normalizeOptionalText(formState.ipAddress),
    last_seen_at: normalizeOptionalDateTime(formState.lastSeenAt),
  };

  if (mode.value === "create") {
    const createPayload: DeviceCreateRequestDto = payloadBase;
    emit("submit", createPayload);
    return;
  }

  const updatePayload: DeviceUpdateRequestDto = payloadBase;
  emit("submit", updatePayload);
}

/**
 * 弹窗开合时同步表单与校验状态。
 */
watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      syncFormState();
      return;
    }
    formRef.value?.clearValidate();
  },
  { immediate: true },
);

/**
 * 编辑目标变更时及时回填。
 */
watch(
  () => props.initialValue,
  () => {
    if (props.modelValue) {
      syncFormState();
    }
  },
);
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    :title="dialogTitle"
    width="720px"
    destroy-on-close
    @close="closeDialog"
  >
    <ElForm ref="formRef" :model="formState" :rules="formRules" label-position="top">
      <ElRow :gutter="16">
        <ElCol :span="12">
          <ElFormItem label="设备编码" prop="deviceCode">
            <ElInput v-model="formState.deviceCode" placeholder="例如 MP157-A-01" />
          </ElFormItem>
        </ElCol>
        <ElCol :span="12">
          <ElFormItem label="设备名称" prop="name">
            <ElInput v-model="formState.name" placeholder="例如 主视觉节点" />
          </ElFormItem>
        </ElCol>
      </ElRow>

      <ElRow :gutter="16">
        <ElCol :span="12">
          <ElFormItem label="设备类型" prop="deviceType">
            <ElSelect v-model="formState.deviceType" placeholder="请选择设备类型">
              <ElOption
                v-for="option in deviceTypeOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </ElSelect>
          </ElFormItem>
        </ElCol>
        <ElCol :span="12">
          <ElFormItem label="设备状态" prop="status">
            <ElSelect v-model="formState.status" placeholder="请选择设备状态">
              <ElOption
                v-for="option in deviceStatusOptions"
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
          <ElFormItem label="固件版本">
            <ElInput v-model="formState.firmwareVersion" placeholder="例如 2026.04.20" />
          </ElFormItem>
        </ElCol>
        <ElCol :span="12">
          <ElFormItem label="IP 地址">
            <ElInput v-model="formState.ipAddress" placeholder="例如 192.168.1.20" />
          </ElFormItem>
        </ElCol>
      </ElRow>

      <ElFormItem label="最近心跳时间">
        <ElDatePicker
          v-model="formState.lastSeenAt"
          type="datetime"
          value-format="YYYY-MM-DDTHH:mm:ss"
          format="YYYY-MM-DD HH:mm:ss"
          placeholder="可选，留空表示暂未记录"
          style="width: 100%"
        />
      </ElFormItem>
    </ElForm>

    <template #footer>
      <div class="dialog-footer">
        <ElButton @click="closeDialog">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="submitForm">
          {{ mode === "create" ? "创建设备" : "保存修改" }}
        </ElButton>
      </div>
    </template>
  </ElDialog>
</template>

<style scoped>
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
