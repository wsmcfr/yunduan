<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import type { FormInstance, FormRules } from "element-plus";

import AppDialog from "@/components/common/AppDialog.vue";
import {
  aiModelTemplates,
  authModeLabels,
  modelVendorLabels,
  protocolLabels,
} from "@/features/settings/aiSettingsCatalog";
import { fetchDiscoveredGatewayModels } from "@/services/api/settings";
import { mapAIDiscoveredModelCandidateDto } from "@/services/mappers/commonMappers";
import type {
  AIModelProfileCreateRequestDto,
  AIModelProfileUpdateRequestDto,
} from "@/types/api";
import type { AIDiscoveredModelCandidate, AIModelProfile } from "@/types/models";
import { normalizeOptionalText } from "@/utils/form";

interface ModelFormValue {
  displayName: string;
  upstreamVendor: AIModelProfileCreateRequestDto["upstream_vendor"];
  protocolType: AIModelProfileCreateRequestDto["protocol_type"];
  authMode: AIModelProfileCreateRequestDto["auth_mode"];
  baseUrlOverride: string;
  userAgent: string;
  modelIdentifier: string;
  supportsVision: boolean;
  supportsStream: boolean;
  isEnabled: boolean;
  note: string;
}

const AUTO_DISCOVERY_NOTE_PREFIX = "自动探测来源：";

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    submitting?: boolean;
    initialValue?: AIModelProfile | null;
    templateId?: string | null;
    gatewayId?: number | null;
  }>(),
  {
    submitting: false,
    initialValue: null,
    templateId: null,
    gatewayId: null,
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  submit: [payload: AIModelProfileCreateRequestDto | AIModelProfileUpdateRequestDto];
}>();

/**
 * Element Plus 表单实例。
 */
const formRef = ref<FormInstance>();

/**
 * 当前弹窗模式。
 */
const mode = computed(() => (props.initialValue ? "edit" : "create"));

/**
 * 当前应用的模型模板。
 */
const activeTemplate = computed(
  () => aiModelTemplates.find((item) => item.id === props.templateId) ?? null,
);

/**
 * 自动探测的模型候选列表。
 */
const discoveredModels = ref<AIDiscoveredModelCandidate[]>([]);

/**
 * 自动探测状态与错误信息。
 */
const discoveringModels = ref(false);
const discoveryError = ref("");
const selectedDiscoveredModelId = ref("");

/**
 * 表单状态。
 */
const formState = reactive<ModelFormValue>(createEmptyForm());

/**
 * 表单校验规则。
 */
const formRules: FormRules<ModelFormValue> = {
  displayName: [{ required: true, message: "请输入模型显示名", trigger: "blur" }],
  modelIdentifier: [{ required: true, message: "请输入真实模型标识", trigger: "blur" }],
};

/**
 * 默认空表单。
 */
function createEmptyForm(): ModelFormValue {
  return {
    displayName: "",
    upstreamVendor: "custom",
    protocolType: "openai_compatible",
    authMode: "authorization_bearer",
    baseUrlOverride: "",
    userAgent: "",
    modelIdentifier: "",
    // 新建模型时默认按“文本模型”处理，避免用户尚未核对官方文档时误把纯文本模型勾成视觉模型。
    supportsVision: false,
    supportsStream: true,
    isEnabled: true,
    note: "",
  };
}

/**
 * 根据模型配置回填表单。
 */
function createFormFromModel(model: AIModelProfile): ModelFormValue {
  return {
    displayName: model.displayName,
    upstreamVendor: model.upstreamVendor,
    protocolType: model.protocolType,
    authMode: model.authMode,
    baseUrlOverride: model.baseUrlOverride ?? "",
    userAgent: model.userAgent ?? "",
    modelIdentifier: model.modelIdentifier,
    supportsVision: model.supportsVision,
    supportsStream: model.supportsStream,
    isEnabled: model.isEnabled,
    note: model.note ?? "",
  };
}

/**
 * 根据模板创建新增表单。
 */
function createFormFromTemplate(templateId: string | null): ModelFormValue {
  const template = aiModelTemplates.find((item) => item.id === templateId);
  if (!template) {
    return createEmptyForm();
  }

  return {
    displayName: template.payload.display_name,
    upstreamVendor: template.payload.upstream_vendor,
    protocolType: template.payload.protocol_type,
    authMode: template.payload.auth_mode,
    baseUrlOverride: template.payload.base_url_override ?? "",
    userAgent: template.payload.user_agent ?? "",
    modelIdentifier: template.payload.model_identifier,
    supportsVision: template.payload.supports_vision,
    supportsStream: template.payload.supports_stream,
    isEnabled: template.payload.is_enabled,
    note: template.payload.note ?? "",
  };
}

/**
 * 判断当前探测到的模型是否和所选模板兼容。
 */
function isCandidateCompatibleWithTemplate(candidate: AIDiscoveredModelCandidate): boolean {
  if (!activeTemplate.value) {
    return true;
  }

  const templatePayload = activeTemplate.value.payload;
  if (candidate.protocolType !== templatePayload.protocol_type) {
    return false;
  }
  if (candidate.authMode !== templatePayload.auth_mode) {
    return false;
  }
  if (
    templatePayload.upstream_vendor !== "custom" &&
    candidate.upstreamVendor !== templatePayload.upstream_vendor
  ) {
    return false;
  }

  return true;
}

/**
 * 为自动探测候选模型生成稳定主键。
 * 这里不能只用模型名，因为同一个中转商下可能会在不同协议来源里返回同名模型。
 */
function createDiscoveredModelKey(candidate: AIDiscoveredModelCandidate): string {
  return [
    candidate.sourceLabel,
    candidate.upstreamVendor,
    candidate.protocolType,
    candidate.authMode,
    candidate.modelIdentifier,
  ].join("::");
}

/**
 * 从备注里提取自动探测来源。
 * 这样编辑已有模型时，重新探测后可以尽量匹配回原来的来源分组，而不是误切到别的协议来源。
 */
function extractAutoDiscoverySourceLabel(note: string): string | null {
  const normalizedNote = note.trim();
  if (!normalizedNote.startsWith(AUTO_DISCOVERY_NOTE_PREFIX)) {
    return null;
  }
  return normalizedNote.slice(AUTO_DISCOVERY_NOTE_PREFIX.length).trim() || null;
}

/**
 * 判断当前备注是否是系统自动写入的探测来源。
 * 如果是，就允许在重新探测后同步更新；如果是人工备注，则保持不动。
 */
function isAutoDiscoveryNote(note: string): boolean {
  return note.trim().startsWith(AUTO_DISCOVERY_NOTE_PREFIX);
}

/**
 * 根据稳定主键从候选列表中找到对应项。
 */
function findCandidateByKey(
  candidates: AIDiscoveredModelCandidate[],
  candidateKey: string,
): AIDiscoveredModelCandidate | null {
  return candidates.find((item) => createDiscoveredModelKey(item) === candidateKey) ?? null;
}

/**
 * 根据当前表单内容回找最匹配的探测模型。
 * 优先保留用户上一次选中的候选项，其次再按协议、品牌、模型标识和自动探测来源做精确匹配。
 */
function findBestMatchingCandidate(
  candidates: AIDiscoveredModelCandidate[],
  preferredCandidateKey: string,
): AIDiscoveredModelCandidate | null {
  if (preferredCandidateKey) {
    const preferredCandidate = findCandidateByKey(candidates, preferredCandidateKey);
    if (preferredCandidate) {
      return preferredCandidate;
    }
  }

  const normalizedModelIdentifier = formState.modelIdentifier.trim();
  if (!normalizedModelIdentifier) {
    return null;
  }

  const preferredSourceLabel = extractAutoDiscoverySourceLabel(formState.note);
  const normalizedUserAgent = formState.userAgent.trim();

  const exactMatch = candidates.find((candidate) => {
    if (candidate.modelIdentifier !== normalizedModelIdentifier) {
      return false;
    }
    if (candidate.upstreamVendor !== formState.upstreamVendor) {
      return false;
    }
    if (candidate.protocolType !== formState.protocolType) {
      return false;
    }
    if (candidate.authMode !== formState.authMode) {
      return false;
    }
    if (preferredSourceLabel && candidate.sourceLabel !== preferredSourceLabel) {
      return false;
    }
    if (
      normalizedUserAgent &&
      (candidate.userAgent ?? "").trim() !== normalizedUserAgent
    ) {
      return false;
    }
    return true;
  });
  if (exactMatch) {
    return exactMatch;
  }

  const sourceAwareMatch = candidates.find((candidate) => {
    if (candidate.modelIdentifier !== normalizedModelIdentifier) {
      return false;
    }
    if (preferredSourceLabel && candidate.sourceLabel !== preferredSourceLabel) {
      return false;
    }
    return true;
  });
  if (sourceAwareMatch) {
    return sourceAwareMatch;
  }

  return null;
}

/**
 * 当前模板过滤后的自动探测模型列表。
 */
const filteredDiscoveredModels = computed(() =>
  discoveredModels.value.filter((candidate) => isCandidateCompatibleWithTemplate(candidate)),
);

/**
 * 把自动探测结果回填到表单。
 */
function applyDiscoveredModel(candidate: AIDiscoveredModelCandidate): void {
  formState.displayName = candidate.displayName;
  formState.upstreamVendor = candidate.upstreamVendor;
  formState.protocolType = candidate.protocolType;
  formState.authMode = candidate.authMode;
  formState.baseUrlOverride = candidate.baseUrl;
  formState.userAgent = candidate.userAgent ?? "";
  formState.modelIdentifier = candidate.modelIdentifier;
  formState.supportsVision = candidate.supportsVision;
  formState.supportsStream = candidate.supportsStream;
  if (!formState.note.trim() || isAutoDiscoveryNote(formState.note)) {
    formState.note = `${AUTO_DISCOVERY_NOTE_PREFIX}${candidate.sourceLabel}`;
  }
}

/**
 * 根据当前选中的自动探测模型键回填表单。
 */
function handleDiscoveredModelChange(nextValue: string | undefined): void {
  /**
   * 这里必须先同步下拉框受控值。
   * 否则用户手动改完别的表单项时，Select 会因为没有真正更新 value 而回到“未选中”状态。
   */
  selectedDiscoveredModelId.value = nextValue ?? "";
  if (!nextValue) {
    return;
  }
  const candidate = findCandidateByKey(filteredDiscoveredModels.value, nextValue);
  if (!candidate) {
    return;
  }
  applyDiscoveredModel(candidate);
}

/**
 * 从当前网关自动拉取可用模型列表。
 * 这里依赖后端用已保存的密钥和 URL 做探测，前端不会拿到真实密钥。
 */
async function discoverGatewayModels(): Promise<void> {
  if (props.gatewayId === null) {
    discoveredModels.value = [];
    selectedDiscoveredModelId.value = "";
    return;
  }

  discoveringModels.value = true;
  discoveryError.value = "";
  const previousSelectedCandidateKey = selectedDiscoveredModelId.value;

  try {
    const response = await fetchDiscoveredGatewayModels(props.gatewayId);
    discoveredModels.value = response.items.map(mapAIDiscoveredModelCandidateDto);

    const preferredCandidates = discoveredModels.value.filter((item) =>
      isCandidateCompatibleWithTemplate(item),
    );
    const matchedCandidate =
      findBestMatchingCandidate(preferredCandidates, previousSelectedCandidateKey) ??
      findBestMatchingCandidate(discoveredModels.value, previousSelectedCandidateKey);
    const firstCandidate = matchedCandidate ?? preferredCandidates[0] ?? discoveredModels.value[0] ?? null;
    if (firstCandidate) {
      selectedDiscoveredModelId.value = createDiscoveredModelKey(firstCandidate);
      applyDiscoveredModel(firstCandidate);
    } else {
      selectedDiscoveredModelId.value = "";
    }
  } catch (caughtError) {
    discoveredModels.value = [];
    selectedDiscoveredModelId.value = "";
    discoveryError.value =
      caughtError instanceof Error ? caughtError.message : "自动探测模型失败";
    ElMessage.warning(discoveryError.value);
  } finally {
    discoveringModels.value = false;
  }
}

/**
 * 打开弹窗时同步表单内容。
 */
function syncFormState(): void {
  const nextValue = props.initialValue
    ? createFormFromModel(props.initialValue)
    : createFormFromTemplate(props.templateId);
  Object.assign(formState, nextValue);
  selectedDiscoveredModelId.value = "";
  discoveryError.value = "";
}

/**
 * 关闭弹窗。
 */
function closeDialog(): void {
  emit("update:modelValue", false);
}

/**
 * 提交模型配置表单。
 */
async function submitForm(): Promise<void> {
  const isValid = await formRef.value?.validate().catch(() => false);
  if (!isValid) {
    return;
  }

  const normalizedPayload = {
    display_name: formState.displayName.trim(),
    upstream_vendor: formState.upstreamVendor,
    protocol_type: formState.protocolType,
    auth_mode: formState.authMode,
    base_url_override: normalizeOptionalText(formState.baseUrlOverride),
    user_agent: normalizeOptionalText(formState.userAgent),
    model_identifier: formState.modelIdentifier.trim(),
    supports_vision: formState.supportsVision,
    supports_stream: formState.supportsStream,
    is_enabled: formState.isEnabled,
    note: normalizeOptionalText(formState.note),
  } satisfies AIModelProfileCreateRequestDto;

  emit("submit", normalizedPayload);
}

watch(
  () => props.modelValue,
  async (visible) => {
    if (visible) {
      syncFormState();
      await discoverGatewayModels();
      return;
    }
    formRef.value?.clearValidate();
    discoveryError.value = "";
  },
  { immediate: true },
);

watch(
  () => [props.initialValue, props.templateId, props.gatewayId],
  () => {
    if (props.modelValue) {
      syncFormState();
      void discoverGatewayModels();
    }
  },
);
</script>

<template>
  <AppDialog
    class="model-dialog"
    :model-value="modelValue"
    :title="mode === 'create' ? '新增模型配置' : '编辑模型配置'"
    width="min(920px, calc(100vw - 32px))"
    top="3vh"
    append-to-body
    destroy-on-close
    @close="closeDialog"
  >
    <div class="model-dialog__scroll">
      <ElAlert
        v-if="activeTemplate"
        type="info"
        show-icon
        :closable="false"
        :title="`已应用模板：${activeTemplate.title}`"
        :description="activeTemplate.summary"
      />

      <ElAlert
        v-if="discoveryError"
        type="warning"
        show-icon
        :closable="false"
        title="自动探测模型失败"
        :description="discoveryError"
        class="model-dialog__alert"
      />

      <ElForm ref="formRef" :model="formState" :rules="formRules" label-position="top">
        <ElRow :gutter="16">
          <ElCol :xs="24" :sm="12">
            <ElFormItem label="模型显示名" prop="displayName">
              <ElInput v-model="formState.displayName" placeholder="例如 OpenClaudeCode Codex" />
            </ElFormItem>
          </ElCol>
          <ElCol :xs="24" :sm="12">
            <ElFormItem label="真实模型标识" prop="modelIdentifier">
              <ElInput
                v-model="formState.modelIdentifier"
                placeholder="优先从下方自动探测结果选择；这里只作为手动兜底"
              />
            </ElFormItem>
          </ElCol>
        </ElRow>

        <ElFormItem label="自动探测模型">
          <div class="model-dialog__discovery-row">
            <ElSelect
              v-model="selectedDiscoveredModelId"
              filterable
              clearable
              :loading="discoveringModels"
              placeholder="根据当前网关 URL 和密钥自动探测可用模型"
              @change="handleDiscoveredModelChange"
            >
              <ElOption
                v-for="candidate in filteredDiscoveredModels"
                :key="createDiscoveredModelKey(candidate)"
                :label="`${candidate.displayName} / ${candidate.modelIdentifier} / ${candidate.sourceLabel}`"
                :value="createDiscoveredModelKey(candidate)"
              />
            </ElSelect>
            <ElButton :loading="discoveringModels" @click="discoverGatewayModels">
              重新探测
            </ElButton>
          </div>
          <p class="muted-text model-dialog__hint">
            模型列表由后端使用已保存的 URL 与密钥探测得到。选择后会自动填充协议、鉴权、User-Agent 和模型标识。
          </p>
        </ElFormItem>

        <ElRow :gutter="16">
          <ElCol :xs="24" :sm="12">
            <ElFormItem label="上游模型品牌">
              <ElSelect v-model="formState.upstreamVendor">
                <ElOption
                  v-for="(label, value) in modelVendorLabels"
                  :key="value"
                  :label="label"
                  :value="value"
                />
              </ElSelect>
            </ElFormItem>
          </ElCol>
          <ElCol :xs="24" :sm="12">
            <ElFormItem label="协议类型">
              <ElSelect v-model="formState.protocolType">
                <ElOption
                  v-for="(label, value) in protocolLabels"
                  :key="value"
                  :label="label"
                  :value="value"
                />
              </ElSelect>
            </ElFormItem>
          </ElCol>
        </ElRow>

        <ElRow :gutter="16">
          <ElCol :xs="24" :sm="12">
            <ElFormItem label="鉴权方式">
              <ElSelect v-model="formState.authMode">
                <ElOption
                  v-for="(label, value) in authModeLabels"
                  :key="value"
                  :label="label"
                  :value="value"
                />
              </ElSelect>
            </ElFormItem>
          </ElCol>
          <ElCol :xs="24" :sm="12">
            <ElFormItem label="Base URL 覆盖">
              <ElInput
                v-model="formState.baseUrlOverride"
                placeholder="留空时继承网关基础 URL，例如 Codex 可单独写成 .../v1"
              />
            </ElFormItem>
          </ElCol>
        </ElRow>

        <ElFormItem label="User-Agent">
          <ElInput
            v-model="formState.userAgent"
            placeholder="例如 openclaudecode 文档要求的 Claude CLI / Codex CLI UA"
          />
        </ElFormItem>

        <ElRow :gutter="16">
          <ElCol :xs="24" :sm="8">
            <ElFormItem label="支持视觉">
              <div class="model-dialog__capability-field">
                <ElSwitch
                  v-model="formState.supportsVision"
                  inline-prompt
                  active-text="支持"
                  inactive-text="否"
                />
                <span class="muted-text model-dialog__capability-hint">
                  只有官方文档或实测确认支持图片输入时再打开。
                </span>
              </div>
            </ElFormItem>
          </ElCol>
          <ElCol :xs="24" :sm="8">
            <ElFormItem label="支持流式">
              <ElSwitch
                v-model="formState.supportsStream"
                inline-prompt
                active-text="支持"
                inactive-text="否"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :xs="24" :sm="8">
            <ElFormItem label="启用状态">
              <ElSwitch
                v-model="formState.isEnabled"
                inline-prompt
                active-text="启用"
                inactive-text="停用"
              />
            </ElFormItem>
          </ElCol>
        </ElRow>

        <ElFormItem label="备注">
          <ElInput
            v-model="formState.note"
            type="textarea"
            :rows="4"
            placeholder="填写这个模型模板对应的官方文档要求、配额分组、已知兼容性差异等"
          />
        </ElFormItem>
      </ElForm>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <ElButton @click="closeDialog">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="submitForm">
          {{ mode === "create" ? "创建模型" : "保存修改" }}
        </ElButton>
      </div>
    </template>
  </AppDialog>
</template>

<style scoped>
.model-dialog__scroll {
  max-height: calc(100vh - 220px);
  overflow-y: auto;
  padding-right: 6px;
}

.model-dialog__alert {
  margin-bottom: 14px;
}

.model-dialog__discovery-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
}

.model-dialog__hint {
  margin: 8px 0 0;
}

.model-dialog__capability-field {
  display: grid;
  gap: 8px;
}

.model-dialog__capability-hint {
  line-height: 1.5;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 768px) {
  .model-dialog__scroll {
    max-height: calc(100vh - 190px);
  }

  .model-dialog__discovery-row {
    grid-template-columns: 1fr;
  }
}
</style>
