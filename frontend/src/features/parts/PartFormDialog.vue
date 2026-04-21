<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import type { FormInstance, FormRules } from "element-plus";

import AppDialog from "@/components/common/AppDialog.vue";
import type { PartCreateRequestDto, PartUpdateRequestDto } from "@/types/api";
import type { PartModel } from "@/types/models";
import { normalizeOptionalText } from "@/utils/form";

interface PartFormValue {
  partCode: string;
  name: string;
  category: string;
  description: string;
  isActive: boolean;
}

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    submitting?: boolean;
    initialValue?: PartModel | null;
  }>(),
  {
    submitting: false,
    initialValue: null,
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  submit: [payload: PartCreateRequestDto | PartUpdateRequestDto];
}>();

/**
 * 表单引用用于触发 Element Plus 校验。
 */
const formRef = ref<FormInstance>();

/**
 * 当前表单模式。
 * 有初始值就是编辑，没有则是新增。
 */
const mode = computed(() => (props.initialValue ? "edit" : "create"));

/**
 * 弹窗标题跟随模式切换。
 */
const dialogTitle = computed(() => (mode.value === "create" ? "新增零件类型" : "编辑零件类型"));

/**
 * 编辑已有类型时，展示最近一次实际来源设备与设备覆盖范围。
 * 这是只读信息，真正的隶属关系由设备上报记录自动沉淀，不允许在前端手工伪造。
 */
const affiliationSummary = computed(() => {
  if (!props.initialValue) {
    return {
      latestDeviceLabel: "待设备上报后自动识别",
      coverageLabel: "新建后会根据上传记录自动关联来源设备",
    };
  }

  return {
    latestDeviceLabel: props.initialValue.latestSourceDevice
      ? `${props.initialValue.latestSourceDevice.name} / ${props.initialValue.latestSourceDevice.deviceCode}`
      : "暂无来源设备记录",
    coverageLabel: props.initialValue.deviceCount > 0
      ? `已关联 ${props.initialValue.deviceCount} 台设备的上传记录`
      : "当前还没有任何设备上传到该类别",
  };
});

/**
 * 表单状态统一放在一个响应式对象里，便于重置与回填。
 */
const formState = reactive<PartFormValue>(createEmptyForm());

/**
 * 表单校验规则。
 */
const formRules: FormRules<PartFormValue> = {
  partCode: [
    { required: true, message: "请输入零件编码", trigger: "blur" },
    { min: 2, max: 64, message: "零件编码长度需在 2 到 64 个字符之间", trigger: "blur" },
  ],
  name: [
    { required: true, message: "请输入零件名称", trigger: "blur" },
    { min: 1, max: 128, message: "零件名称长度需在 1 到 128 个字符之间", trigger: "blur" },
  ],
  category: [{ max: 64, message: "分类长度不能超过 64 个字符", trigger: "blur" }],
};

/**
 * 创建新增模式下的空表单。
 */
function createEmptyForm(): PartFormValue {
  return {
    partCode: "",
    name: "",
    category: "",
    description: "",
    isActive: true,
  };
}

/**
 * 将已有零件模型映射成表单值。
 */
function createFormFromModel(model: PartModel): PartFormValue {
  return {
    partCode: model.partCode,
    name: model.name,
    category: model.category ?? "",
    description: model.description ?? "",
    isActive: model.isActive,
  };
}

/**
 * 根据当前模式同步表单内容。
 * 每次打开弹窗时都重建一次，避免残留上一次输入。
 */
function syncFormState(): void {
  const nextValue = props.initialValue ? createFormFromModel(props.initialValue) : createEmptyForm();
  Object.assign(formState, nextValue);
}

/**
 * 关闭弹窗并清除校验状态。
 */
function closeDialog(): void {
  emit("update:modelValue", false);
}

/**
 * 提交表单。
 * 新增与编辑都共用一份表单，只在最终 payload 结构上区分。
 */
async function submitForm(): Promise<void> {
  const isValid = await formRef.value?.validate().catch(() => false);
  if (!isValid) {
    return;
  }

  if (mode.value === "create") {
    const createPayload: PartCreateRequestDto = {
      part_code: formState.partCode.trim(),
      name: formState.name.trim(),
      category: normalizeOptionalText(formState.category),
      description: normalizeOptionalText(formState.description),
      is_active: formState.isActive,
    };
    emit("submit", createPayload);
    return;
  }

  const updatePayload: PartUpdateRequestDto = {
    part_code: formState.partCode.trim(),
    name: formState.name.trim(),
    category: normalizeOptionalText(formState.category),
    description: normalizeOptionalText(formState.description),
    is_active: formState.isActive,
  };
  emit("submit", updatePayload);
}

/**
 * 弹窗打开时重新同步数据，关闭时清理校验提示。
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
 * 编辑对象变化时，如果弹窗正处于打开状态，则立即回填。
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
  <AppDialog
    :model-value="modelValue"
    :title="dialogTitle"
    width="620px"
    destroy-on-close
    @close="closeDialog"
  >
    <ElForm ref="formRef" :model="formState" :rules="formRules" label-position="top">
      <ElAlert
        type="info"
        show-icon
        :closable="false"
        class="dialog-affiliation"
      >
        <template #title>
          设备隶属会根据检测记录自动识别，不在这里手工指定
        </template>
        <template #default>
          <div class="dialog-affiliation__content">
            <span>最近来源设备：{{ affiliationSummary.latestDeviceLabel }}</span>
            <span>{{ affiliationSummary.coverageLabel }}</span>
          </div>
        </template>
      </ElAlert>

      <ElRow :gutter="16">
        <ElCol :span="12">
          <ElFormItem label="类型编码" prop="partCode">
            <ElInput v-model="formState.partCode" placeholder="例如 PART-001" />
          </ElFormItem>
        </ElCol>
        <ElCol :span="12">
          <ElFormItem label="类型名称" prop="name">
            <ElInput v-model="formState.name" placeholder="例如 金属垫片" />
          </ElFormItem>
        </ElCol>
      </ElRow>

      <ElRow :gutter="16">
        <ElCol :span="12">
          <ElFormItem label="分类" prop="category">
            <ElInput v-model="formState.category" placeholder="例如 紧固件 / 端子 / 连接件" />
          </ElFormItem>
        </ElCol>
        <ElCol :span="12">
          <ElFormItem label="启用状态">
            <ElSwitch
              v-model="formState.isActive"
              inline-prompt
              active-text="启用"
              inactive-text="停用"
            />
          </ElFormItem>
        </ElCol>
      </ElRow>

      <ElFormItem label="说明">
        <ElInput
          v-model="formState.description"
          type="textarea"
          :rows="4"
          placeholder="填写适合的缺陷类型、检测重点、尺寸注意事项等"
        />
      </ElFormItem>
    </ElForm>

    <template #footer>
      <div class="dialog-footer">
        <ElButton @click="closeDialog">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="submitForm">
          {{ mode === "create" ? "创建零件类型" : "保存修改" }}
        </ElButton>
      </div>
    </template>
  </AppDialog>
</template>

<style scoped>
.dialog-affiliation {
  margin-bottom: 18px;
}

.dialog-affiliation__content {
  display: grid;
  gap: 6px;
  line-height: 1.7;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
