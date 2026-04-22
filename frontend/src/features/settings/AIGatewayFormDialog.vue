<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import type { FormInstance, FormRules } from "element-plus";

import AppDialog from "@/components/common/AppDialog.vue";
import { aiGatewayPresets, gatewayVendorLabels } from "@/features/settings/aiSettingsCatalog";
import { previewGatewayModels } from "@/services/api/settings";
import { mapAIDiscoveredModelCandidateDto } from "@/services/mappers/commonMappers";
import type {
  AIGatewayCreateRequestDto,
  AIGatewayDiscoveryPreviewRequestDto,
  AIGatewayUpdateRequestDto,
} from "@/types/api";
import type { AIDiscoveredModelCandidate, AIGatewayModel } from "@/types/models";
import { normalizeOptionalText } from "@/utils/form";

interface GatewayFormValue {
  name: string;
  vendor: AIGatewayCreateRequestDto["vendor"];
  officialUrl: string;
  baseUrl: string;
  apiKey: string;
  note: string;
  isEnabled: boolean;
  isCustom: boolean;
}

interface GatewaySourceTemplateOption {
  sourceLabel: string;
  title: string;
  summary: string;
}

/**
 * OpenClaudeCode 这类中转商需要先区分外接框架模板，再从探测结果里选择真实模型。
 * 这里定义建网关阶段可勾选的模板选项，探测成功后会按这些来源分组展示真实模型。
 */
const OPENCLAUDECODE_SOURCE_TEMPLATE_OPTIONS: readonly GatewaySourceTemplateOption[] = [
  {
    sourceLabel: "OpenClaudeCode Claude 外接",
    title: "Claude 模板",
    summary: "自动套用 Anthropic Messages 协议与 Claude CLI User-Agent；部分第三方模型也可能落到这一组。",
  },
  {
    sourceLabel: "OpenClaudeCode Grok 外接",
    title: "Grok 模板",
    summary: "自动套用 Anthropic Messages 协议与 Claude CLI User-Agent；适合 OpenClaudeCode 下返回 Grok 模型列表的场景。",
  },
  {
    sourceLabel: "OpenClaudeCode Codex 外接",
    title: "Codex 模板",
    summary: "自动套用 OpenAI Responses 协议与 Codex CLI User-Agent；只适合真正兼容 Responses 的模型。",
  },
  {
    sourceLabel: "OpenClaudeCode 国产模型外接",
    title: "国产模型模板",
    summary: "自动套用通用兼容协议与浏览器型 User-Agent；适合没有独立 Grok / Claude / Codex 模板的兼容模型。",
  },
];

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    submitting?: boolean;
    initialValue?: AIGatewayModel | null;
    presetId?: string | null;
    submitError?: string;
    submitErrorCode?: string;
  }>(),
  {
    submitting: false,
    initialValue: null,
    presetId: null,
    submitError: "",
    submitErrorCode: "",
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  submit: [
    payload: AIGatewayCreateRequestDto | AIGatewayUpdateRequestDto,
    selectedCandidates: AIDiscoveredModelCandidate[],
  ];
  "clear-submit-error": [];
}>();

/**
 * 表单引用用于触发 Element Plus 校验。
 */
const formRef = ref<FormInstance>();

/**
 * 当前弹窗模式。
 */
const mode = computed(() => (props.initialValue ? "edit" : "create"));

/**
 * 供新增模式快速回填的预设。
 */
const activePreset = computed(
  () => aiGatewayPresets.find((item) => item.id === props.presetId) ?? null,
);

/**
 * 弹窗标题随模式变化。
 */
const dialogTitle = computed(() =>
  mode.value === "create" ? "新增 AI 网关" : "编辑 AI 网关",
);

/**
 * 为网关保存失败提示生成短标题，避免把很长的后端说明直接挤进标题行。
 */
const submitErrorTitle = computed(() => {
  if (props.submitErrorCode === "ai_gateway_name_exists") {
    return "当前公司内已存在同名网关";
  }
  if (props.submitErrorCode === "ai_gateway_global_name_conflict") {
    return "数据库仍残留旧的全局唯一索引";
  }
  return "网关保存失败";
});

/**
 * 表单状态统一托管，便于重置与编辑回填。
 */
const formState = reactive<GatewayFormValue>(createEmptyForm());
const discoveringModels = ref(false);
const discoveryError = ref("");
const discoveredModels = ref<AIDiscoveredModelCandidate[]>([]);
const selectedCandidateKeys = ref<string[]>([]);
const selectedSourceTemplateLabels = ref<string[]>([]);

/**
 * 只有 OpenClaudeCode 这类多协议中转商，才需要在建网关时显式选择外接框架模板。
 */
const isOpenClaudeCodeVendor = computed(() => formState.vendor === "openclaudecode");

/**
 * 网关表单校验规则。
 */
const formRules: FormRules<GatewayFormValue> = {
  name: [
    { required: true, message: "请输入网关名称", trigger: "blur" },
    { min: 1, max: 128, message: "网关名称长度需在 1 到 128 个字符之间", trigger: "blur" },
  ],
  baseUrl: [{ required: true, message: "请输入网关基础 URL", trigger: "blur" }],
};

/**
 * 创建默认空表单。
 */
function createEmptyForm(): GatewayFormValue {
  return {
    name: "",
    vendor: "custom",
    officialUrl: "",
    baseUrl: "",
    apiKey: "",
    note: "",
    isEnabled: true,
    isCustom: true,
  };
}

/**
 * 为当前供应商返回默认勾选的外接模板来源。
 * 官方直连厂商不展示这组三选项，因此返回空数组。
 */
function createDefaultSourceTemplateLabels(
  vendor: GatewayFormValue["vendor"],
): string[] {
  if (vendor !== "openclaudecode") {
    return [];
  }
  return OPENCLAUDECODE_SOURCE_TEMPLATE_OPTIONS.map((item) => item.sourceLabel);
}

/**
 * 根据网关模型回填表单。
 */
function createFormFromGateway(gateway: AIGatewayModel): GatewayFormValue {
  return {
    name: gateway.name,
    vendor: gateway.vendor,
    officialUrl: gateway.officialUrl ?? "",
    baseUrl: gateway.baseUrl,
    apiKey: "",
    note: gateway.note ?? "",
    isEnabled: gateway.isEnabled,
    isCustom: gateway.isCustom,
  };
}

/**
 * 根据预设创建表单初始值。
 */
function createFormFromPreset(presetId: string | null): GatewayFormValue {
  const preset = aiGatewayPresets.find((item) => item.id === presetId);
  if (!preset) {
    return createEmptyForm();
  }

  return {
    name: preset.payload.name,
    vendor: preset.payload.vendor,
    officialUrl: preset.payload.official_url ?? "",
    baseUrl: preset.payload.base_url,
    apiKey: "",
    note: preset.payload.note ?? "",
    isEnabled: preset.payload.is_enabled,
    isCustom: preset.payload.is_custom,
  };
}

/**
 * 按当前模式同步表单内容。
 */
function syncFormState(): void {
  const nextValue = props.initialValue
    ? createFormFromGateway(props.initialValue)
    : createFormFromPreset(props.presetId);
  Object.assign(formState, nextValue);
  emit("clear-submit-error");
  discoveryError.value = "";
  discoveredModels.value = [];
  selectedCandidateKeys.value = [];
  selectedSourceTemplateLabels.value = createDefaultSourceTemplateLabels(nextValue.vendor);
}

/**
 * 关闭弹窗。
 */
function closeDialog(): void {
  emit("clear-submit-error");
  emit("update:modelValue", false);
}

/**
 * 为候选模型生成稳定选择键。
 */
function createCandidateKey(candidate: AIDiscoveredModelCandidate): string {
  return [
    candidate.sourceLabel,
    candidate.protocolType,
    candidate.authMode,
    candidate.modelIdentifier,
  ].join("::");
}

/**
 * 返回用户勾选的模型候选项。
 */
const selectedCandidates = computed(() => {
  const selectedKeySet = new Set(selectedCandidateKeys.value);
  return discoveredModels.value.filter((candidate) => selectedKeySet.has(createCandidateKey(candidate)));
});

/**
 * 当前探测结果里的来源分组。
 * 对 OpenClaudeCode 这类多外接类型网关，会拆成 Claude / Grok / Codex / 国产模型四组，便于在建网关阶段直接批量勾选。
 */
const discoveredSourceLabels = computed(() => {
  return Array.from(new Set(discoveredModels.value.map((candidate) => candidate.sourceLabel)));
});

/**
 * 将探测到的真实模型按来源模板分组展示。
 * 这样用户能看清楚自己勾选的是哪一类模板下的哪些实际模型。
 */
const discoveredModelGroups = computed(() => {
  return discoveredSourceLabels.value.map((sourceLabel) => ({
    sourceLabel,
    items: discoveredModels.value.filter((candidate) => candidate.sourceLabel === sourceLabel),
  }));
});

/**
 * 只有 OpenClaudeCode 这种同站多协议中转，才展示按来源分组的快捷选择按钮。
 * 官方直连厂商在创建网关时不需要出现 Claude / Grok / Codex / 国产模型这类框架分组入口。
 */
const shortcutSourceLabels = computed(() => {
  if (!isOpenClaudeCodeVendor.value) {
    return [];
  }
  return discoveredSourceLabels.value;
});

/**
 * 当前供应商可使用的外接模板来源。
 * 只有 OpenClaudeCode 会在建网关阶段出现 Claude / Grok / Codex / 国产模型四类模板。
 */
const availableSourceTemplateOptions = computed(() => {
  if (!isOpenClaudeCodeVendor.value) {
    return [];
  }
  return OPENCLAUDECODE_SOURCE_TEMPLATE_OPTIONS;
});

/**
 * 按当前勾选的模板来源，同步真实模型的默认选中状态。
 * 这样“模板选择”和“实际模型选择”会联动，用户不需要再手工逐个推断协议配置。
 */
function syncSelectedCandidatesFromTemplates(): void {
  if (!isOpenClaudeCodeVendor.value) {
    selectedCandidateKeys.value = discoveredModels.value.map(createCandidateKey);
    return;
  }

  const selectedTemplateSet = new Set(selectedSourceTemplateLabels.value);
  selectedCandidateKeys.value = discoveredModels.value
    .filter((candidate) => selectedTemplateSet.has(candidate.sourceLabel))
    .map(createCandidateKey);
}

/**
 * 一键选中当前探测到的全部候选模型。
 */
function selectAllCandidates(): void {
  if (isOpenClaudeCodeVendor.value) {
    selectedSourceTemplateLabels.value = createDefaultSourceTemplateLabels(formState.vendor);
  }
  selectedCandidateKeys.value = discoveredModels.value.map(createCandidateKey);
}

/**
 * 只选中某一个探测来源分组下的模型。
 * 这样用户在创建网关时就能直接选“Claude 外接 / Grok 外接 / Codex 外接 / 国产模型外接”整组，而不是逐条手点。
 */
function selectCandidatesBySourceLabel(sourceLabel: string): void {
  if (isOpenClaudeCodeVendor.value) {
    selectedSourceTemplateLabels.value = [sourceLabel];
  }
  selectedCandidateKeys.value = discoveredModels.value
    .filter((candidate) => candidate.sourceLabel === sourceLabel)
    .map(createCandidateKey);
}

/**
 * 清空当前所有候选模型勾选。
 */
function clearSelectedCandidates(): void {
  if (isOpenClaudeCodeVendor.value) {
    selectedSourceTemplateLabels.value = [];
  }
  selectedCandidateKeys.value = [];
}

/**
 * 用当前弹窗里填写的 URL、厂商和密钥即时探测模型。
 * 这里不要求先保存网关，所以你在这个弹窗里就能直接看到可选模型。
 */
async function handlePreviewModels(): Promise<void> {
  emit("clear-submit-error");
  const normalizedBaseUrl = formState.baseUrl.trim();
  const normalizedApiKey = formState.apiKey.trim();

  if (!normalizedBaseUrl) {
    ElMessage.warning("请先填写基础 URL 再探测模型。");
    return;
  }
  if (!normalizedApiKey) {
    ElMessage.warning(
      mode.value === "edit"
        ? "编辑模式下如果要重新探测模型，请重新输入 API Key。"
        : "请先填写 API Key 再探测模型。",
    );
    return;
  }

  discoveringModels.value = true;
  discoveryError.value = "";

  try {
    const response = await previewGatewayModels({
      vendor: formState.vendor,
      base_url: normalizedBaseUrl,
      api_key: normalizedApiKey,
    } satisfies AIGatewayDiscoveryPreviewRequestDto);
    discoveredModels.value = response.items.map(mapAIDiscoveredModelCandidateDto);
    syncSelectedCandidatesFromTemplates();
    if (discoveredModels.value.length === 0) {
      ElMessage.warning("当前网关没有探测到可用模型。");
      return;
    }
    ElMessage.success(`已探测到 ${discoveredModels.value.length} 个可选模型，可直接勾选后一起创建。`);
  } catch (caughtError) {
    discoveredModels.value = [];
    selectedCandidateKeys.value = [];
    discoveryError.value =
      caughtError instanceof Error ? caughtError.message : "模型探测失败";
    ElMessage.error(discoveryError.value);
  } finally {
    discoveringModels.value = false;
  }
}

/**
 * 提交网关表单。
 * 编辑模式下如果 API Key 留空，表示保留后端现有密钥。
 */
async function submitForm(): Promise<void> {
  emit("clear-submit-error");
  const isValid = await formRef.value?.validate().catch(() => false);
  if (!isValid) {
    return;
  }

  if (mode.value === "create") {
    const createPayload: AIGatewayCreateRequestDto = {
      name: formState.name.trim(),
      vendor: formState.vendor,
      official_url: normalizeOptionalText(formState.officialUrl),
      base_url: formState.baseUrl.trim(),
      api_key: formState.apiKey.trim(),
      note: normalizeOptionalText(formState.note),
      is_enabled: formState.isEnabled,
      is_custom: formState.isCustom,
    };
    emit("submit", createPayload, selectedCandidates.value);
    return;
  }

  const normalizedApiKey = formState.apiKey.trim();
  const updatePayload: AIGatewayUpdateRequestDto = {
    name: formState.name.trim(),
    vendor: formState.vendor,
    official_url: normalizeOptionalText(formState.officialUrl),
    base_url: formState.baseUrl.trim(),
    api_key: normalizedApiKey ? normalizedApiKey : null,
    note: normalizeOptionalText(formState.note),
    is_enabled: formState.isEnabled,
    is_custom: formState.isCustom,
  };
  emit("submit", updatePayload, selectedCandidates.value);
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      syncFormState();
      return;
    }
    formRef.value?.clearValidate();
    emit("clear-submit-error");
  },
  { immediate: true },
);

watch(
  () => [props.initialValue, props.presetId],
  () => {
    if (props.modelValue) {
      syncFormState();
    }
  },
);

watch(
  () => formState.vendor,
  (nextVendor) => {
    emit("clear-submit-error");
    selectedSourceTemplateLabels.value = createDefaultSourceTemplateLabels(nextVendor);
    discoveryError.value = "";
    discoveredModels.value = [];
    selectedCandidateKeys.value = [];
  },
);

watch(
  selectedSourceTemplateLabels,
  () => {
    if (discoveredModels.value.length > 0) {
      syncSelectedCandidatesFromTemplates();
    }
  },
);

watch(
  () => [
    formState.name,
    formState.baseUrl,
    formState.apiKey,
    formState.officialUrl,
    formState.note,
    formState.isEnabled,
    formState.isCustom,
  ],
  () => {
    if (props.modelValue && props.submitError) {
      emit("clear-submit-error");
    }
  },
);
</script>

<template>
  <AppDialog
    class="gateway-dialog"
    :model-value="modelValue"
    :title="dialogTitle"
    width="min(920px, calc(100vw - 32px))"
    top="3vh"
    append-to-body
    destroy-on-close
    @close="closeDialog"
  >
    <div class="gateway-dialog__scroll">
      <ElAlert
        v-if="activePreset"
        type="info"
        show-icon
        :closable="false"
        :title="`已应用预设：${activePreset.title}`"
        :description="activePreset.summary"
      />

      <ElAlert
        v-if="initialValue?.hasApiKey"
        type="warning"
        show-icon
        :closable="false"
        :title="`当前已保存密钥：${initialValue.apiKeyMask ?? '已配置'}`"
        description="编辑时 API Key 留空表示继续保留现有密钥，前端不会拿到旧密钥原文。"
        class="gateway-dialog__alert"
      />

      <ElAlert
        v-if="submitError"
        type="error"
        show-icon
        :closable="false"
        :title="submitErrorTitle"
        :description="submitError"
        class="gateway-dialog__alert"
      />

      <ElAlert
        v-if="discoveryError"
        type="warning"
        show-icon
        :closable="false"
        title="模型实时探测失败"
        :description="discoveryError"
        class="gateway-dialog__alert"
      />

      <ElForm ref="formRef" :model="formState" :rules="formRules" label-position="top">
        <ElRow :gutter="16">
          <ElCol :xs="24" :sm="12">
            <ElFormItem label="网关名称" prop="name">
              <ElInput v-model="formState.name" placeholder="例如 OpenClaudeCode / Claude 官方" />
            </ElFormItem>
          </ElCol>
          <ElCol :xs="24" :sm="12">
            <ElFormItem label="网关品牌">
              <ElSelect v-model="formState.vendor">
                <ElOption
                  v-for="(label, value) in gatewayVendorLabels"
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
            <ElFormItem label="官方文档 / 官网">
              <ElInput v-model="formState.officialUrl" placeholder="可选，例如 https://docs.openclaudecode.cn/#/" />
            </ElFormItem>
          </ElCol>
          <ElCol :xs="24" :sm="12">
            <ElFormItem label="基础 URL" prop="baseUrl">
              <ElInput v-model="formState.baseUrl" placeholder="例如 https://www.openclaudecode.cn" />
            </ElFormItem>
          </ElCol>
        </ElRow>

        <ElRow :gutter="16">
          <ElCol :xs="24" :sm="12">
            <ElFormItem :label="mode === 'create' ? 'API Key' : 'API Key（留空表示保留）'">
              <ElInput
                v-model="formState.apiKey"
                type="password"
                show-password
                :placeholder="mode === 'create' ? '请输入网关 API Key' : '如需替换密钥再填写'"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :xs="24" :sm="12">
            <ElFormItem label="自定义网关">
              <ElSwitch
                v-model="formState.isCustom"
                inline-prompt
                active-text="自定义"
                inactive-text="预设"
              />
            </ElFormItem>
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

        <ElFormItem label="管理员备注（可选）">
          <ElInput
            v-model="formState.note"
            type="textarea"
            :rows="4"
            placeholder="仅供管理员记录，例如协议说明、限流规则、供应商注意事项；这里不会用于模型选择。"
          />
        </ElFormItem>

        <ElFormItem label="实时探测模型">
          <div v-if="availableSourceTemplateOptions.length > 0" class="gateway-dialog__framework-panel">
            <div class="gateway-dialog__framework-header">
              <strong>先选要创建的外接框架模板</strong>
              <p class="muted-text">
                这里选的是模板规则，不是最终模型名。探测完成后，下方会按模板来源分组展示真实模型，并自动带出对应协议、鉴权、User-Agent 和 Base URL 规则。
              </p>
              <p class="muted-text">
                现在已经提供单独的 Grok 模板入口；如果同名模型在某个分组里调用仍报“无法解析响应”，通常就是这组协议不匹配，或者上游返回的是流式事件而不是普通 JSON。
              </p>
            </div>

            <ElCheckboxGroup
              v-model="selectedSourceTemplateLabels"
              class="gateway-dialog__framework-group"
            >
              <ElCheckbox
                v-for="option in availableSourceTemplateOptions"
                :key="option.sourceLabel"
                :value="option.sourceLabel"
                class="gateway-dialog__framework-item"
              >
                <div class="gateway-dialog__framework-item-copy">
                  <strong>{{ option.title }}</strong>
                  <p class="muted-text">{{ option.summary }}</p>
                </div>
              </ElCheckbox>
            </ElCheckboxGroup>
          </div>

          <div class="gateway-dialog__discovery-panel">
            <div class="gateway-dialog__discovery-toolbar">
              <div class="gateway-dialog__discovery-copy">
                <strong>在这个弹窗里直接探测</strong>
                <p class="muted-text">
                  填完 URL 和 API Key 后点“探测模型”，下方会列出可用模型。勾选后，保存网关时会把这些模型一起创建到当前网关下。
                </p>
                <p v-if="shortcutSourceLabels.length > 0" class="muted-text">
                  当前供应商支持按来源分组快捷勾选，可直接只选 Claude / Grok / Codex / 国产模型这一类；如果同一个模型名同时出现在多个分组里，优先保留实际能稳定返回的那一组。
                </p>
              </div>
              <ElButton :loading="discoveringModels" @click="handlePreviewModels">
                探测模型
              </ElButton>
            </div>
          </div>

          <div v-if="discoveredModels.length > 0" class="gateway-dialog__candidate-list">
            <div class="gateway-dialog__candidate-summary">
              <strong>可选模型</strong>
              <span class="muted-text">已勾选 {{ selectedCandidates.length }} / {{ discoveredModels.length }}</span>
            </div>

            <div class="gateway-dialog__candidate-actions">
              <ElButton size="small" @click="selectAllCandidates">全选</ElButton>
              <ElButton size="small" @click="clearSelectedCandidates">清空</ElButton>
              <ElButton
                v-for="sourceLabel in shortcutSourceLabels"
                :key="sourceLabel"
                size="small"
                type="primary"
                plain
                @click="selectCandidatesBySourceLabel(sourceLabel)"
              >
                仅选 {{ sourceLabel }}
              </ElButton>
            </div>

            <template v-if="isOpenClaudeCodeVendor">
              <section
                v-for="group in discoveredModelGroups"
                :key="group.sourceLabel"
                class="gateway-dialog__candidate-section"
              >
                <div class="gateway-dialog__candidate-section-header">
                  <div class="gateway-dialog__candidate-section-copy">
                    <strong>{{ group.sourceLabel }}</strong>
                    <p class="muted-text">
                      这里勾选的是实际模型名称；对应协议、鉴权、User-Agent 与 Base URL 规则会按当前模板自动填写。
                    </p>
                  </div>
                  <ElTag
                    :type="selectedSourceTemplateLabels.includes(group.sourceLabel) ? 'success' : 'info'"
                    effect="dark"
                    round
                  >
                    {{ selectedSourceTemplateLabels.includes(group.sourceLabel) ? "模板已启用" : "模板未启用" }}
                  </ElTag>
                </div>

                <ElCheckboxGroup
                  v-model="selectedCandidateKeys"
                  class="gateway-dialog__candidate-group"
                >
                  <ElCheckbox
                    v-for="candidate in group.items"
                    :key="createCandidateKey(candidate)"
                    :value="createCandidateKey(candidate)"
                    class="gateway-dialog__candidate-item"
                  >
                    <div class="gateway-dialog__candidate-main">
                      <strong>{{ candidate.displayName }}</strong>
                      <span class="muted-text">{{ candidate.modelIdentifier }}</span>
                    </div>
                    <div class="gateway-dialog__candidate-tags">
                      <ElTag size="small" effect="dark" round>{{ candidate.sourceLabel }}</ElTag>
                      <ElTag size="small" type="info" effect="plain" round>{{ candidate.protocolType }}</ElTag>
                      <ElTag size="small" type="warning" effect="plain" round>{{ candidate.authMode }}</ElTag>
                    </div>
                  </ElCheckbox>
                </ElCheckboxGroup>
              </section>
            </template>

            <ElCheckboxGroup
              v-else
              v-model="selectedCandidateKeys"
              class="gateway-dialog__candidate-group"
            >
              <ElCheckbox
                v-for="candidate in discoveredModels"
                :key="createCandidateKey(candidate)"
                :value="createCandidateKey(candidate)"
                class="gateway-dialog__candidate-item"
              >
                <div class="gateway-dialog__candidate-main">
                  <strong>{{ candidate.displayName }}</strong>
                  <span class="muted-text">{{ candidate.modelIdentifier }}</span>
                </div>
                <div class="gateway-dialog__candidate-tags">
                  <ElTag size="small" effect="dark" round>{{ candidate.sourceLabel }}</ElTag>
                  <ElTag size="small" type="info" effect="plain" round>{{ candidate.protocolType }}</ElTag>
                  <ElTag size="small" type="warning" effect="plain" round>{{ candidate.authMode }}</ElTag>
                </div>
              </ElCheckbox>
            </ElCheckboxGroup>
          </div>

          <div v-else class="gateway-dialog__candidate-empty">
            <strong>模型选择区</strong>
            <p class="muted-text">
              <template v-if="isOpenClaudeCodeVendor">
                这里选的不是模板名，而是探测出来的实际模型。先勾选上面的 Claude / Grok / Codex / 国产模型模板，再填写基础 URL 和 API Key，点击“探测模型”后，这里会按模板分组列出真实模型，并沿用对应的协议与 User-Agent 规则。
              </template>
              <template v-else>
                这里就是模型选择的地方。现在还没有候选项，是因为还没完成探测。先填写基础 URL 和 API Key，再点击“探测模型”，探测成功后这里会出现可勾选模型列表。
              </template>
            </p>
          </div>
        </ElFormItem>
      </ElForm>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <ElButton @click="closeDialog">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="submitForm">
          {{
            selectedCandidates.length > 0
              ? mode === "create"
                ? `创建网关并新增 ${selectedCandidates.length} 个模型`
                : `保存网关并新增 ${selectedCandidates.length} 个模型`
              : mode === "create"
                ? "创建网关"
                : "保存修改"
          }}
        </ElButton>
      </div>
    </template>
  </AppDialog>
</template>

<style scoped>
.gateway-dialog__scroll {
  max-height: calc(100vh - 220px);
  overflow-y: auto;
  padding-right: 6px;
}

.gateway-dialog__alert {
  margin-top: 14px;
}

.gateway-dialog__discovery-toolbar,
.gateway-dialog__candidate-main,
.gateway-dialog__candidate-tags {
  display: flex;
  gap: 12px;
}

.gateway-dialog__framework-panel,
.gateway-dialog__discovery-panel,
.gateway-dialog__framework-header,
.gateway-dialog__candidate-section,
.gateway-dialog__candidate-section-copy {
  display: grid;
  gap: 12px;
}

.gateway-dialog__framework-panel,
.gateway-dialog__discovery-panel,
.gateway-dialog__candidate-empty,
.gateway-dialog__candidate-section {
  min-width: 0;
  padding: 16px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.02);
}

.gateway-dialog__framework-panel,
.gateway-dialog__discovery-panel {
  margin-bottom: 16px;
}

.gateway-dialog__discovery-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: flex-start;
  gap: 16px;
}

.gateway-dialog__discovery-copy {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.gateway-dialog__discovery-copy p,
.gateway-dialog__framework-header p,
.gateway-dialog__framework-item-copy p,
.gateway-dialog__candidate-section-copy p {
  margin: 0;
}

.gateway-dialog__candidate-list,
.gateway-dialog__candidate-group,
.gateway-dialog__candidate-empty,
.gateway-dialog__framework-group {
  display: grid;
  gap: 12px;
}

.gateway-dialog__candidate-group {
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.gateway-dialog__framework-group {
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.gateway-dialog__candidate-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.gateway-dialog__candidate-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.gateway-dialog__candidate-section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.gateway-dialog__framework-item-copy {
  display: grid;
  gap: 6px;
}

:deep(.gateway-dialog__framework-item) {
  margin-right: 0;
  margin-bottom: 0;
  width: 100%;
  min-height: 108px;
  display: flex;
  align-items: flex-start;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.02);
}

:deep(.gateway-dialog__framework-item .el-checkbox__input) {
  margin-top: 2px;
}

:deep(.gateway-dialog__framework-item .el-checkbox__label) {
  display: block;
  width: 100%;
  padding-left: 12px;
  white-space: normal;
}

:deep(.gateway-dialog__candidate-item) {
  margin-right: 0;
  margin-bottom: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: flex-start;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.02);
}

:deep(.gateway-dialog__candidate-item .el-checkbox__input) {
  margin-top: 2px;
}

:deep(.gateway-dialog__candidate-item .el-checkbox__label) {
  display: block;
  width: 100%;
  padding-left: 12px;
  white-space: normal;
}

.gateway-dialog__candidate-empty {
  margin-top: 0;
  border-style: dashed;
}

.gateway-dialog__candidate-empty p {
  margin: 0;
}

.gateway-dialog__candidate-main {
  align-items: center;
  flex-wrap: wrap;
}

.gateway-dialog__candidate-tags {
  margin-top: 8px;
  flex-wrap: wrap;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 768px) {
  .gateway-dialog__scroll {
    max-height: calc(100vh - 190px);
  }

  .gateway-dialog__discovery-toolbar {
    grid-template-columns: 1fr;
  }

  .gateway-dialog__candidate-summary,
  .gateway-dialog__candidate-section-header {
    display: flex;
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
