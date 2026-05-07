import type {
  AIAuthMode,
  AIGatewayCreateRequestDto,
  AIGatewayVendor,
  AIModelProfileCreateRequestDto,
  AIModelVendor,
  AIProtocolType,
} from "@/types/api";

export interface AIGatewayPreset {
  readonly id: string;
  readonly title: string;
  readonly summary: string;
  readonly payload: Omit<AIGatewayCreateRequestDto, "api_key">;
}

export interface AIModelTemplate {
  readonly id: string;
  readonly title: string;
  readonly summary: string;
  readonly supportedGatewayVendors: readonly AIGatewayVendor[];
  readonly preferredSourceLabel?: string;
  readonly payload: AIModelProfileCreateRequestDto;
}

export const gatewayVendorLabels: Record<AIGatewayVendor, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  google: "Google",
  zhipu: "智谱 GLM",
  moonshot: "Moonshot Kimi",
  minmax: "MiniMax",
  deepseek: "DeepSeek",
  openclaudecode: "OpenClaudeCode",
  relay: "通用中转",
  custom: "自定义",
};

export const modelVendorLabels: Record<AIModelVendor, string> = {
  codex: "Codex",
  claude: "Claude",
  gemini: "Gemini",
  deepseek: "DeepSeek",
  glm: "GLM",
  kimi: "Kimi",
  minmax: "MiniMax",
  custom: "自定义",
};

export const protocolLabels: Record<AIProtocolType, string> = {
  anthropic_messages: "Anthropic Messages",
  openai_compatible: "OpenAI Compatible",
  openai_responses: "OpenAI Responses",
  gemini_generate_content: "Gemini GenerateContent",
};

export const authModeLabels: Record<AIAuthMode, string> = {
  x_api_key: "X-Api-Key",
  authorization_bearer: "Authorization Bearer",
  both: "双写认证头",
  query_api_key: "Query API Key",
};

/**
 * OpenClaudeCode 文档里给出的 Codex 外接 User-Agent。
 */
export const OPENCLAUDECODE_CODEX_UA =
  "codex_cli_rs/0.77.0 (Windows 10.0.26100; x86_64) WindowsTerminal";

/**
 * OpenClaudeCode 文档里给出的 Claude 外接 User-Agent。
 */
export const OPENCLAUDECODE_CLAUDE_UA = "claude-cli/2.0.76 (external, cli)";

/**
 * OpenClaudeCode 文档里给出的国产模型外接浏览器 UA。
 */
export const OPENCLAUDECODE_BROWSER_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0";

export const aiGatewayPresets: AIGatewayPreset[] = [
  {
    id: "openai-official",
    title: "OpenAI 官方",
    summary: "适合 GPT / Codex 官方直连，根地址使用官方 API 域名。",
    payload: {
      name: "OpenAI 官方",
      vendor: "openai",
      official_url: "https://platform.openai.com/docs/overview",
      base_url: "https://api.openai.com/v1",
      note: "官方 OpenAI 网关；Responses 协议建议把版本前缀直接落在基础 URL 上。",
      is_enabled: true,
      is_custom: false,
    },
  },
  {
    id: "anthropic-official",
    title: "Claude 官方",
    summary: "适合 Claude 官方直连，后续模型走 Anthropic Messages 协议。",
    payload: {
      name: "Claude 官方",
      vendor: "anthropic",
      official_url: "https://docs.anthropic.com/en/api/getting-started",
      base_url: "https://api.anthropic.com",
      note: "官方 Anthropic 网关。",
      is_enabled: true,
      is_custom: false,
    },
  },
  {
    id: "gemini-official",
    title: "Gemini 官方",
    summary: "适合 Gemini 官方直连，默认走 Google GenerateContent API。",
    payload: {
      name: "Gemini 官方",
      vendor: "google",
      official_url: "https://ai.google.dev/gemini-api/docs",
      base_url: "https://generativelanguage.googleapis.com/v1beta",
      note: "官方 Gemini 网关；GenerateContent 建议直接使用版本化基础 URL。",
      is_enabled: true,
      is_custom: false,
    },
  },
  {
    id: "glm-official",
    title: "GLM 官方",
    summary: "智谱 GLM 官方网关，适合直连 GLM 系列模型。",
    payload: {
      name: "GLM 官方",
      vendor: "zhipu",
      official_url: "https://open.bigmodel.cn/dev/howuse/introduction",
      base_url: "https://open.bigmodel.cn/api/paas/v4",
      note: "智谱 GLM 官方网关。",
      is_enabled: true,
      is_custom: false,
    },
  },
  {
    id: "kimi-official",
    title: "Kimi 官方",
    summary: "Moonshot Kimi 官方网关。",
    payload: {
      name: "Kimi 官方",
      vendor: "moonshot",
      official_url: "https://platform.moonshot.cn/docs",
      base_url: "https://api.moonshot.cn/v1",
      note: "Moonshot Kimi 官方网关。",
      is_enabled: true,
      is_custom: false,
    },
  },
  {
    id: "minmax-official",
    title: "MiniMax 官方",
    summary: "MiniMax 官方网关；具体模型协议按模型模板配置。",
    payload: {
      name: "MiniMax 官方",
      vendor: "minmax",
      official_url: "https://platform.minimaxi.com/document/Platform%20Introduction",
      base_url: "https://api.minimaxi.com/v1",
      note: "MiniMax 官方网关，当前可直接挂 OpenAI-compatible 文本模型模板。",
      is_enabled: true,
      is_custom: false,
    },
  },
  {
    id: "deepseek-official",
    title: "DeepSeek 官方",
    summary: "DeepSeek 官方网关，通常走 OpenAI Compatible 风格。",
    payload: {
      name: "DeepSeek 官方",
      vendor: "deepseek",
      official_url: "https://api-docs.deepseek.com/",
      base_url: "https://api.deepseek.com",
      note: "DeepSeek 官方网关。",
      is_enabled: true,
      is_custom: false,
    },
  },
  {
    id: "openclaudecode-relay",
    title: "OpenClaudeCode",
    summary: "官方文档要求不同协议带不同 UA；Claude 与 Codex 的 base URL 规则也不同。",
    payload: {
      name: "OpenClaudeCode",
      vendor: "openclaudecode",
      official_url: "https://www.micuapi.ai",
      base_url: "https://www.micuapi.ai",
      note: "建议在网关下继续添加 Claude / Grok / Codex / 国产模型模板；当前实测 Grok 优先走 Anthropic Messages + Claude CLI UA，Codex 模板仍只给真正兼容 Responses 的模型使用。",
      is_enabled: true,
      is_custom: false,
    },
  },
  {
    id: "custom-relay",
    title: "自定义中转",
    summary: "用于配置 OpenAI / Claude / Gemini 兼容的私有网关或中转站。",
    payload: {
      name: "自定义 AI 网关",
      vendor: "custom",
      official_url: null,
      base_url: "",
      note: "请按网关协议自行填写模型模板。",
      is_enabled: true,
      is_custom: true,
    },
  },
];

export const aiModelTemplates: AIModelTemplate[] = [
  {
    id: "openai-codex-official",
    title: "OpenAI 官方 Codex / GPT",
    summary: "官方 OpenAI Responses 协议模板，适合 GPT / Codex 系列模型。",
    supportedGatewayVendors: ["openai"],
    payload: {
      display_name: "OpenAI 官方模型",
      upstream_vendor: "codex",
      protocol_type: "openai_responses",
      auth_mode: "authorization_bearer",
      base_url_override: null,
      user_agent: null,
      model_identifier: "gpt-5.4",
      supports_vision: true,
      supports_stream: true,
      is_enabled: true,
      note: "OpenAI 官方模板；当前以 Responses 协议接入。",
    },
  },
  {
    id: "anthropic-claude-official",
    title: "Claude 官方",
    summary: "Anthropic Messages 协议模板，官方鉴权使用 x-api-key。",
    supportedGatewayVendors: ["anthropic"],
    payload: {
      display_name: "Claude 官方模型",
      upstream_vendor: "claude",
      protocol_type: "anthropic_messages",
      auth_mode: "x_api_key",
      base_url_override: null,
      user_agent: null,
      model_identifier: "claude-sonnet-4-5",
      supports_vision: true,
      supports_stream: true,
      is_enabled: true,
      note: "Anthropic 官方模板；请求头需要 `x-api-key` 与 `anthropic-version`。",
    },
  },
  {
    id: "gemini-official",
    title: "Gemini 官方",
    summary: "GenerateContent 协议模板，官方 REST 文档默认通过查询参数传 API Key。",
    supportedGatewayVendors: ["google"],
    payload: {
      display_name: "Gemini 官方模型",
      upstream_vendor: "gemini",
      protocol_type: "gemini_generate_content",
      auth_mode: "query_api_key",
      base_url_override: null,
      user_agent: null,
      model_identifier: "gemini-2.5-flash",
      supports_vision: true,
      supports_stream: true,
      is_enabled: true,
      note: "Gemini 官方模板；当前 REST 方式使用 `?key=` 查询参数鉴权。",
    },
  },
  {
    id: "glm-official",
    title: "GLM 官方",
    summary: "智谱 GLM 官方 OpenAI-compatible 模板。",
    supportedGatewayVendors: ["zhipu"],
    payload: {
      display_name: "GLM 官方模型",
      upstream_vendor: "glm",
      protocol_type: "openai_compatible",
      auth_mode: "authorization_bearer",
      base_url_override: null,
      user_agent: null,
      model_identifier: "glm-4.5",
      supports_vision: true,
      supports_stream: true,
      is_enabled: true,
      note: "智谱官方兼容模板；如需切换模型名，可直接改 `model_identifier`。",
    },
  },
  {
    id: "kimi-official",
    title: "Kimi 官方",
    summary: "Moonshot Kimi 官方 OpenAI-compatible 模板。",
    supportedGatewayVendors: ["moonshot"],
    payload: {
      display_name: "Kimi 官方模型",
      upstream_vendor: "kimi",
      protocol_type: "openai_compatible",
      auth_mode: "authorization_bearer",
      base_url_override: null,
      user_agent: null,
      model_identifier: "kimi-k2-latest",
      supports_vision: true,
      supports_stream: true,
      is_enabled: true,
      note: "Moonshot 官方兼容模板；如实际模型名不同，请按控制台为准修改。",
    },
  },
  {
    id: "minmax-official",
    title: "MiniMax 官方",
    summary: "MiniMax 官方 OpenAI-compatible 模板，默认按文本模型初始化。",
    supportedGatewayVendors: ["minmax"],
    payload: {
      display_name: "MiniMax 官方模型",
      upstream_vendor: "minmax",
      protocol_type: "openai_compatible",
      auth_mode: "authorization_bearer",
      base_url_override: null,
      user_agent: null,
      model_identifier: "MiniMax-M1",
      supports_vision: false,
      supports_stream: true,
      is_enabled: true,
      note: "MiniMax OpenAI-compatible 文档当前以文本输入为主；如果你接的是视觉模型，可手动打开视觉能力。",
    },
  },
  {
    id: "deepseek-official",
    title: "DeepSeek 官方",
    summary: "DeepSeek 官方 OpenAI-compatible 模板。",
    supportedGatewayVendors: ["deepseek"],
    payload: {
      display_name: "DeepSeek 官方模型",
      upstream_vendor: "deepseek",
      protocol_type: "openai_compatible",
      auth_mode: "authorization_bearer",
      base_url_override: null,
      user_agent: null,
      model_identifier: "deepseek-chat",
      supports_vision: false,
      supports_stream: true,
      is_enabled: true,
      note: "DeepSeek 官方模板；如接入支持视觉的上游模型，可在这里手动打开视觉能力。",
    },
  },
  {
    id: "openclaudecode-claude",
    title: "OpenClaudeCode Claude",
    summary: "Anthropic Messages 协议，不带 /v1，必须带 Claude CLI UA。",
    supportedGatewayVendors: ["openclaudecode"],
    preferredSourceLabel: "OpenClaudeCode Claude 外接",
    payload: {
      display_name: "OpenClaudeCode Claude",
      upstream_vendor: "claude",
      protocol_type: "anthropic_messages",
      auth_mode: "authorization_bearer",
      base_url_override: null,
      user_agent: OPENCLAUDECODE_CLAUDE_UA,
      model_identifier: "",
      supports_vision: true,
      supports_stream: true,
      is_enabled: true,
      note: "OpenClaudeCode 文档中的 Claude 外接模板。",
    },
  },
  {
    id: "openclaudecode-grok",
    title: "OpenClaudeCode Grok",
    summary: "Anthropic Messages 协议，必须带 Claude CLI UA；适合 OpenClaudeCode 下的 Grok 模型。",
    supportedGatewayVendors: ["openclaudecode"],
    preferredSourceLabel: "OpenClaudeCode Grok 外接",
    payload: {
      display_name: "OpenClaudeCode Grok",
      upstream_vendor: "custom",
      protocol_type: "anthropic_messages",
      auth_mode: "authorization_bearer",
      base_url_override: null,
      user_agent: OPENCLAUDECODE_CLAUDE_UA,
      model_identifier: "grok-4.20-fast",
      supports_vision: true,
      supports_stream: true,
      is_enabled: true,
      note: "OpenClaudeCode 下的 Grok 模板；当前实测应优先走 Anthropic Messages，并沿用 Claude CLI User-Agent。",
    },
  },
  {
    id: "openclaudecode-codex",
    title: "OpenClaudeCode Codex",
    summary: "OpenAI Responses 协议，必须走 /v1，并带 Codex CLI UA。",
    supportedGatewayVendors: ["openclaudecode"],
    preferredSourceLabel: "OpenClaudeCode Codex 外接",
    payload: {
      display_name: "OpenClaudeCode Codex",
      upstream_vendor: "codex",
      protocol_type: "openai_responses",
      auth_mode: "authorization_bearer",
      base_url_override: "https://www.micuapi.ai/v1",
      user_agent: OPENCLAUDECODE_CODEX_UA,
      model_identifier: "gpt-5.4",
      supports_vision: true,
      supports_stream: true,
      is_enabled: true,
      note: "OpenClaudeCode 文档中的 Codex 外接模板；如果某个模型在这里返回非 JSON 或统计 AI 无法解析，通常说明它并不真正兼容 Responses。",
    },
  },
  {
    id: "openclaudecode-domestic",
    title: "OpenClaudeCode 国产模型",
    summary: "国产模型外接场景，建议带浏览器型 UA，协议和模型标识按实际渠道填写。",
    supportedGatewayVendors: ["openclaudecode"],
    preferredSourceLabel: "OpenClaudeCode 国产模型外接",
    payload: {
      display_name: "OpenClaudeCode 国产模型",
      upstream_vendor: "custom",
      protocol_type: "openai_compatible",
      auth_mode: "authorization_bearer",
      base_url_override: null,
      user_agent: OPENCLAUDECODE_BROWSER_UA,
      model_identifier: "",
      supports_vision: true,
      supports_stream: true,
      is_enabled: true,
      note: "OpenClaudeCode 文档中的通用兼容模板；当第三方模型没有独立品牌模板时，通常先从这一类协议兼容入口尝试。",
    },
  },
  {
    id: "relay-openai-compatible",
    title: "通用中转 OpenAI-Compatible",
    summary: "适合大多数兼容 OpenAI Chat Completions 的中转商或私有网关。",
    supportedGatewayVendors: ["relay", "custom"],
    payload: {
      display_name: "通用 OpenAI-Compatible 模型",
      upstream_vendor: "custom",
      protocol_type: "openai_compatible",
      auth_mode: "authorization_bearer",
      base_url_override: null,
      user_agent: null,
      model_identifier: "",
      supports_vision: true,
      supports_stream: true,
      is_enabled: true,
      note: "通用兼容模板；如果中转要求 `/v1`、自定义 UA 或 query key，请在模型或网关里补齐。",
    },
  },
  {
    id: "relay-anthropic-messages",
    title: "通用中转 Claude / Messages",
    summary: "适合支持 Anthropic Messages 的代理、中转和私有网关。",
    supportedGatewayVendors: ["relay", "custom"],
    payload: {
      display_name: "通用 Claude / Messages 模型",
      upstream_vendor: "claude",
      protocol_type: "anthropic_messages",
      auth_mode: "authorization_bearer",
      base_url_override: null,
      user_agent: null,
      model_identifier: "",
      supports_vision: true,
      supports_stream: true,
      is_enabled: true,
      note: "通用 Claude 兼容模板；如果是 Anthropic 官方，请改成 x-api-key。",
    },
  },
  {
    id: "relay-gemini-generate-content",
    title: "通用中转 Gemini",
    summary: "适合代理或私有网关转发 Gemini GenerateContent 协议。",
    supportedGatewayVendors: ["relay", "custom"],
    payload: {
      display_name: "通用 Gemini 模型",
      upstream_vendor: "gemini",
      protocol_type: "gemini_generate_content",
      auth_mode: "authorization_bearer",
      base_url_override: null,
      user_agent: null,
      model_identifier: "",
      supports_vision: true,
      supports_stream: true,
      is_enabled: true,
      note: "通用 Gemini 模板；官方 REST 默认是 query key，中转场景按网关要求填写。",
    },
  },
];

/**
 * 根据网关品牌筛出当前可快速创建的模型模板。
 */
export function getModelTemplatesForGatewayVendor(
  vendor: AIGatewayVendor,
): AIModelTemplate[] {
  return aiModelTemplates.filter((item) => item.supportedGatewayVendors.includes(vendor));
}
