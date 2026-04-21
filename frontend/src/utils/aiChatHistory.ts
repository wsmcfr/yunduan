import type { AIChatHistoryMessageDto, AIChatRole } from "@/types/api";

/**
 * 单次用户提问允许的最大字符数。
 * 这里和后端 schema 保持一致，避免前端把明显会被 422 拒绝的内容继续发出去。
 */
export const AI_CHAT_QUESTION_MAX_CHARACTERS = 2000;

/**
 * 单条历史消息发送到后端时的安全字符上限。
 * 后端真实上限是 4000，这里预留一点空间给“已省略”提示文案，避免裁剪后仍然越界。
 */
const DEFAULT_MAX_HISTORY_MESSAGE_CHARACTERS = 3800;

/**
 * 一次请求里最多保留多少条历史消息。
 * 只保留最近几轮，避免会话越聊越长后把整段历史都原样回传。
 */
const DEFAULT_MAX_HISTORY_MESSAGES = 10;

/**
 * 一次请求里历史消息合计的最大字符预算。
 * 从最新消息开始倒序保留，优先保证最近上下文可用。
 */
const DEFAULT_MAX_HISTORY_TOTAL_CHARACTERS = 16000;

/**
 * 在已经保住最新消息之后，继续追加更早历史时所要求的最小可用字符数。
 * 预算只剩几字符时，发送残缺旧消息反而会污染上下文，因此直接停止回溯。
 */
const MIN_INCREMENTAL_HISTORY_CHARACTERS = 16;

/**
 * 超长消息被压缩时插入的占位提示。
 * 这样既保留前后关键上下文，也能明确告诉模型中间内容已经被省略。
 */
const HISTORY_OMIT_MARKER = "\n...[中间内容已省略]...\n";

/**
 * 可参与历史消息归一化的最小消息结构。
 * 统计页和单条复检页都会传入本地消息数组，这里只关心角色和正文。
 */
export interface AiChatHistorySourceMessage {
  role: AIChatRole;
  content: string;
}

/**
 * 历史消息归一化时可调的预算项。
 * 默认值面向当前项目的 AI 多轮对话链路，必要时也允许单独覆盖。
 */
export interface BuildAiChatHistoryOptions {
  maxMessages?: number;
  maxCharactersPerMessage?: number;
  maxTotalCharacters?: number;
}

/**
 * 把单条消息裁剪到安全长度。
 * 超长时保留“开头 + 结尾”，中间插入省略标记，避免只保留前半段导致语义失真。
 */
function truncateHistoryContent(content: string, maxCharacters: number): string {
  const normalizedContent = content.trim();
  if (!normalizedContent || maxCharacters <= 0) {
    return "";
  }

  if (normalizedContent.length <= maxCharacters) {
    return normalizedContent;
  }

  /**
   * 当剩余预算太小，已经放不下“前段 + 提示 + 后段”时，
   * 直接硬截断，至少保证还能返回一段合法字符串。
   */
  if (maxCharacters <= HISTORY_OMIT_MARKER.length + 8) {
    return normalizedContent.slice(0, maxCharacters);
  }

  const remainingCharacters = maxCharacters - HISTORY_OMIT_MARKER.length;
  const headCharacters = Math.max(1, Math.ceil(remainingCharacters * 0.65));
  const tailCharacters = Math.max(1, remainingCharacters - headCharacters);

  return `${normalizedContent.slice(0, headCharacters)}${HISTORY_OMIT_MARKER}${normalizedContent.slice(-tailCharacters)}`;
}

/**
 * 把前端本地消息数组归一化成后端 AI 接口需要的历史 payload。
 * 规则：
 * 1. 只保留 user / assistant 两类消息。
 * 2. 去掉空白消息。
 * 3. 单条消息裁剪到安全上限。
 * 4. 从最近消息开始倒序保留，受总条数和总字符预算共同限制。
 */
export function buildAiChatHistoryPayload(
  messages: ReadonlyArray<AiChatHistorySourceMessage>,
  options: BuildAiChatHistoryOptions = {},
): AIChatHistoryMessageDto[] {
  const maxMessages = Math.max(1, options.maxMessages ?? DEFAULT_MAX_HISTORY_MESSAGES);
  const maxCharactersPerMessage = Math.max(
    1,
    options.maxCharactersPerMessage ?? DEFAULT_MAX_HISTORY_MESSAGE_CHARACTERS,
  );
  const maxTotalCharacters = Math.max(
    1,
    options.maxTotalCharacters ?? DEFAULT_MAX_HISTORY_TOTAL_CHARACTERS,
  );

  /**
   * 先做角色过滤和空白清理，再只取最近若干条候选消息。
   * 这样能把后续预算分配聚焦到真正对当前追问还有帮助的上下文。
   */
  const normalizedMessages = messages
    .filter(
      (item): item is AiChatHistorySourceMessage =>
        item.role === "user" || item.role === "assistant",
    )
    .map((item) => ({
      role: item.role,
      content: item.content.trim(),
    }))
    .filter((item) => item.content.length > 0)
    .slice(-maxMessages);

  const reversedHistory: AIChatHistoryMessageDto[] = [];
  let usedCharacters = 0;

  /**
   * 从最新消息往前回收预算。
   * 这样即使历史很长，也优先保住最近几轮对话，而不是让很早的旧消息挤掉新上下文。
   */
  for (let index = normalizedMessages.length - 1; index >= 0; index -= 1) {
    const remainingCharacters = maxTotalCharacters - usedCharacters;
    if (remainingCharacters <= 0) {
      break;
    }

    /**
     * 最新消息已经保住后，如果剩余预算过小，就不再继续拼接更早历史，
     * 避免产生只有几个字的残缺旧消息。
     */
    if (reversedHistory.length > 0 && remainingCharacters < MIN_INCREMENTAL_HISTORY_CHARACTERS) {
      break;
    }

    const candidate = normalizedMessages[index];
    const safeContent = truncateHistoryContent(
      candidate.content,
      Math.min(maxCharactersPerMessage, remainingCharacters),
    );
    if (!safeContent) {
      continue;
    }

    reversedHistory.push({
      role: candidate.role,
      content: safeContent,
    });
    usedCharacters += safeContent.length;
  }

  return reversedHistory.reverse();
}
