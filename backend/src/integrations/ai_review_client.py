"""AI 复核与对话集成客户端。"""

from __future__ import annotations

import base64
import json
import mimetypes
from datetime import datetime
from typing import Any, Callable, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from src.core.errors import BadRequestError, IntegrationError
from src.core.logging import get_logger
from src.integrations.cos_client import CosClient

logger = get_logger(__name__)


class AICompletionResult:
    """封装一次供应商回答文本及供应商响应编号。

    字段说明：
    - `text`：模型返回给用户看的中文答案。
    - `provider_response_id`：OpenAI Responses 兼容接口返回的响应 ID；前端可保存用于
      调试和供应商追踪。米醋 / OpenClaudeCode 实测不能在 HTTP Responses 上用它
      承接上下文，因此上下文仍由本地历史和压缩摘要负责。
    """

    def __init__(self, *, text: str, provider_response_id: str | None = None) -> None:
        """初始化供应商回答结果。"""

        self.text = text
        self.provider_response_id = provider_response_id


class AIReviewClient:
    """负责把当前记录上下文转成不同 AI 协议的真实请求。"""

    def __init__(self, *, timeout_seconds: int = 90, max_image_bytes: int = 5 * 1024 * 1024) -> None:
        """初始化 AI 集成客户端。

        参数说明：
        - `timeout_seconds`：调用外部模型接口与抓取图片时共用的超时时间。
        - `max_image_bytes`：单张图像允许拉取的最大字节数，避免把过大的图片直接塞进多模态请求。
        """

        self.timeout_seconds = timeout_seconds
        self.max_image_bytes = max_image_bytes
        self.cos_client = CosClient()

    def _build_model_lines(self, *, model_context: dict[str, Any] | None) -> list[str]:
        """根据当前选中的模型配置生成协议与网关说明。"""

        if model_context is None:
            return [
                "当前没有显式指定运行时模型配置，因此回答仍使用占位联调逻辑，不代表真实外部模型已经接通。"
            ]

        return [
            (
                f"当前选用模型为 {model_context['display_name']}（{model_context['model_identifier']}），"
                f"来源品牌 {model_context['upstream_vendor']}。"
            ),
            (
                f"所属网关为 {model_context['gateway_name']}，协议类型为 {model_context['protocol_type']}，"
                f"鉴权方式为 {model_context['auth_mode']}，请求基地址为 {model_context['base_url']}。"
            ),
            (
                f"当前模型要求的 User-Agent 为 {model_context['user_agent']}。"
                if model_context.get("user_agent")
                else "当前模型没有额外要求专用 User-Agent。"
            ),
        ]

    def _build_core_observation_lines(self, *, context: dict[str, Any]) -> list[str]:
        """根据检测记录上下文生成本轮回答的基础观察点。"""

        observation_lines = [
            (
                f"当前记录 {context['record_no']} 对应零件 {context['part_name']}"
                f"（{context['part_code']}），设备 {context['device_name']}"
                f"（{context['device_code']}）。"
            ),
            (
                f"MP 初检结果为 {context['result']}，当前最终结果为 {context['effective_result']}，"
                f"复核状态为 {context['review_status']}。"
            ),
        ]

        if context.get("defect_type"):
            observation_lines.append(f"当前记录的缺陷类型登记为 {context['defect_type']}。")

        if context.get("defect_desc"):
            observation_lines.append(f"缺陷说明为：{context['defect_desc']}")

        confidence_score = context.get("confidence_score")
        if confidence_score is not None:
            observation_lines.append(f"模型置信度约为 {round(confidence_score * 100)}%。")

        if context.get("vision_context"):
            observation_lines.append("当前记录还附带了视觉检测上下文，可继续追问模型版本、各通道结果和图像判定依据。")

        if context.get("sensor_context"):
            observation_lines.append("当前记录还附带了传感器上下文，可继续追问电感/阈值/越界判断与缺陷结论的关系。")

        if context.get("decision_context"):
            observation_lines.append("当前记录还附带了最终判定依据上下文，可继续追问为什么会判成当前结果。")

        if context.get("device_context"):
            observation_lines.append("当前记录还附带了设备运行上下文，可继续追问设备批次、任务号、固件版本或采集参数。")

        if context.get("review_count", 0) > 0 and context.get("latest_review_decision"):
            observation_lines.append(
                (
                    f"最近一次人工复核结论为 {context['latest_review_decision']}，"
                    f"复核时间为 {context['latest_reviewed_at']}。"
                )
            )

        return observation_lines

    def _build_file_lines(self, *, referenced_files: list[dict[str, Any]]) -> list[str]:
        """根据文件对象列表生成图像上下文说明。"""

        if not referenced_files:
            return ["当前记录尚未登记源图、标注图或缩略图，因此我只能基于检测结果和文本上下文回答。"]

        file_kind_summary = "、".join([
            (
                f"{item['file_kind']}:{item['object_key']}"
                f"（{item.get('analysis_purpose') or '未登记用途说明'}）"
            )
            for item in referenced_files
        ])
        return [
            f"当前会话已带入 {len(referenced_files)} 个图像对象上下文，优先参考：{file_kind_summary}。",
            "如果你继续追问缺陷位置、疑似误检原因或人工复核建议，我会继续围绕这些图像对象和检测结果回答。",
        ]

    def _build_question_specific_lines(
        self,
        *,
        question: str,
        context: dict[str, Any],
        referenced_files: list[dict[str, Any]],
    ) -> list[str]:
        """根据用户问题关键词生成更聚焦的回答片段。"""

        focused_lines: list[str] = []
        lower_question = question.lower()

        if any(keyword in question for keyword in ["误检", "复核", "建议", "怎么处理"]):
            if context["result"] == "uncertain" or context["review_status"] == "pending":
                focused_lines.append(
                    "这条记录仍然适合走人工复核或 AI 辅助复核链路，尤其是在初检为待确认或仍未完成人工复核时。"
                )
            else:
                focused_lines.append(
                    "这条记录已经具备明确的最终结论，后续更适合围绕结论依据、缺陷定位和可追溯信息继续追问。"
                )

        if any(keyword in question for keyword in ["图片", "图像", "看图", "位置", "标注"]):
            if referenced_files:
                focused_lines.append(
                    "你现在问的是图像相关问题；我会优先把标注图和源图当成证据入口，再结合缺陷类型与最终结果给出分析。"
                )
            else:
                focused_lines.append(
                    "你现在问的是图像相关问题，但当前记录没有可用图像对象登记，建议先补充源图或标注图。"
                )

        if any(keyword in question for keyword in ["时间", "拍摄", "上传", "检测完成"]):
            focused_lines.append(
                (
                    f"这条记录的时间链路是：拍摄时间 {context['captured_at']}，"
                    f"检测完成时间 {context['detected_at']}，上传完成时间 {context['uploaded_at']}。"
                )
            )

        if any(keyword in lower_question for keyword in ["confidence", "置信", "概率"]):
            if context.get("confidence_score") is not None:
                focused_lines.append(
                    f"当前模型置信度为 {round(context['confidence_score'] * 100)}%，这可以作为人工复核优先级的参考，但不能替代最终复核结论。"
                )
            else:
                focused_lines.append("当前记录没有登记置信度字段，因此不能直接从模型概率角度判断。")

        if not focused_lines:
            focused_lines.append(
                "我会优先围绕当前记录的图片对象、检测结果、缺陷信息和复核历史回答你的问题。你也可以继续追问缺陷位置、误检判断依据或人工复核建议。"
            )

        return focused_lines

    def _build_single_side_review_guard_lines(self) -> list[str]:
        """返回单面工业检测场景下必须遵守的回答约束。"""

        return [
            "当前业务默认只检测零件的单面图像。除非上下文明确给出了另一面、另一工位或多角度图像，否则不要要求补拍另一面、背面、多面或多工位图片。",
            "如果当前单面图像证据不足，只能建议在这一面的外轮廓、内孔边缘、表面划伤、压痕、毛刺、缺口、变形或异物等位置做人工近距离确认，不要把不适用的补图方案当默认建议。",
            "不要把厚度、公差、背面状态、内部结构等当前单面图像无法直接确认的内容写成已观察到的事实；如需提及，只能归入“当前无法确认的边界”。",
            "回答对象是一线质检员和普通管理人员，语言要专业但通俗，少用英文缩写、算法黑话和空泛套话；如果必须提专业术语，要先解释它在当前记录里的实际含义。",
        ]

    def _build_board_correction_prompt_lines(self) -> list[str]:
        """返回 AI 结论与 MP157 初检冲突时的板端修正填写规则。

        这里把修正弹窗的字段名固定写入提示词，避免模型只说“建议人工改判”，
        却没有告诉现场人员在 `修正板端结果` 弹窗中具体应该填什么。
        """

        return [
            "当你给出的质量建议与 MP157 初检结果（record_context.result）不一致时，必须追加一个小节：修正板端结果填写建议。",
            "该小节要明确说明：当前 MP157 初检结果（record_context.result）是什么、你的建议结论是什么、为什么需要修正板端历史结果。",
            "如果 MP157 初检结果（record_context.result）为 good，但你根据图像和字段更倾向不良，修正板端结果填写建议必须写：decision 填 bad；defect_type 填你判断出的缺陷类型；cloud_reason 填一句可直接复制到修正原因框的中文说明，例如“云端复核发现边缘划痕，板端原判良品需要修正。”",
            "如果 MP157 初检结果（record_context.result）为 bad，但你根据图像和字段更倾向良品，修正板端结果填写建议必须写：decision 填 good；defect_type 填 null 或“无明显缺陷”；cloud_reason 填一句可直接复制到修正原因框的中文说明，例如“云端复核认为当前证据更支持良品，板端原判坏品需要修正。”",
            "如果你认为证据不足或需要继续人工复判，并且这个判断与 MP157 初检结果不一致，修正板端结果填写建议必须写：decision 填 uncertain；defect_type 填可疑缺陷类型或 null；cloud_reason 说明当前证据不足、需要人工复判的具体原因。",
        ]

    def _build_suggested_questions(self, *, context: dict[str, Any]) -> list[str]:
        """为前端返回下一轮推荐追问。"""

        suggestions = [
            "结合当前这一面的图片对象，帮我用通俗的话总结这条记录最需要人工确认的风险点。",
            "如果只看当前这一面，哪些证据支持现在的判定，哪些地方还需要人工确认？",
            "根据当前检测结果和缺陷信息，给出一份现场可执行的人工复核建议。",
            "按当前记录的时间链路解释拍摄、检测完成和上传之间的关系。",
        ]

        if context.get("defect_type"):
            suggestions.append(
                f"围绕“{context['defect_type']}”说明当前这一面最该重点看哪里，为什么会被判成现在这个结果。"
            )
        if context.get("sensor_context"):
            suggestions.append("结合传感器上下文，解释这条记录的传感器信号是否支持当前结论。")
        if context.get("decision_context"):
            suggestions.append("根据判定依据上下文，拆解这条记录为什么会被判成当前结果。")

        return suggestions[:4]

    def _serialize_context_value(self, value: Any) -> Any:
        """把上下文中的复杂对象转换成可序列化的稳定文本。

        AI 请求体里会混入 `datetime`、枚举 value、列表等对象。
        这里统一做一次显式转换，避免不同协议分支各自手写序列化逻辑。
        """

        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, list):
            return [self._serialize_context_value(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): self._serialize_context_value(item)
                for key, item in value.items()
            }
        return value

    def _normalize_history(
        self,
        *,
        history: list[dict[str, str]],
        current_question: str,
    ) -> list[dict[str, str]]:
        """整理多轮历史，避免前端把当前问题重复传入两次。"""

        normalized_history: list[dict[str, str]] = []
        normalized_question = current_question.strip()

        for item in history:
            role = str(item.get("role", "")).strip()
            content = str(item.get("content", "")).strip()
            if role not in {"user", "assistant"} or not content:
                continue
            normalized_history.append({"role": role, "content": content})

        # 前端弹窗会先放一条本地 assistant 开场白，用于说明“已进入当前记录上下文”。
        # 这类消息不是模型真实回答，不能作为上游多轮历史发送；否则首个用户问题会变成
        # “assistant 历史 + 4 张图片”的组合，米醋 Responses 容易返回 Cloudflare 502。
        while normalized_history and normalized_history[0]["role"] != "user":
            normalized_history.pop(0)

        if normalized_history:
            last_item = normalized_history[-1]
            if last_item["role"] == "user" and last_item["content"] == normalized_question:
                return normalized_history[:-1]

        return normalized_history

    def _build_history_context_block(self, *, history: list[dict[str, str]], question: str) -> str | None:
        """把最近几轮对话整理成可直接放进当前提示词的历史上下文。

        标准的多消息 `history` 仍会继续传给供应商；这里额外把历史写入当前
        user prompt，是为了兼容部分中转网关或协议回退路径对消息数组处理不稳定的情况。

        参数:
            history: 经过清洗且已去掉当前问题重复项的历史消息。
            question: 当前用户问题，用于识别“可以”“继续”等短确认追问。

        返回:
            有可用历史时返回历史块；没有历史时返回 None。
        """

        if not history:
            return None

        normalized_question = question.strip()
        short_confirmation_words = {
            "可以",
            "好",
            "好的",
            "行",
            "嗯",
            "继续",
            "对",
            "是的",
            "写",
            "帮我写",
        }
        role_labels = {
            "user": "用户",
            "assistant": "AI",
        }
        history_lines = [
            "同一弹窗历史对话：",
            "以下内容是用户在当前检测记录弹窗里的上一轮问答。你必须承接这些历史理解用户追问里的指代，例如“这个位置”“刚才说的风险”“为什么这样判断”。",
            "如果当前用户问题是“可以”“好的”“继续”“写”等短确认词，必须先查看上一轮 AI 是否提出了可继续执行的动作；如果上一轮 AI 说“可以帮你写复核备注/判定说明/修正板端填写内容”，本轮就要直接生成对应内容，不要重新从头判断良品或坏品。",
            "如果历史过长或部分内容被省略，必须先根据历史里的最近结论、风险位置和待执行动作继续回答；只有确实无法解析指代时，才说明需要用户补充具体对象。",
        ]

        for index, item in enumerate(history[-8:], start=1):
            role = role_labels.get(item["role"], item["role"])
            content = item["content"].strip()
            if not content:
                continue
            history_lines.append(f"{index}. {role}：{content}")

        if normalized_question in short_confirmation_words:
            history_lines.append(
                f"当前用户只回复了短确认词“{normalized_question}”，请把它理解为确认上一轮 AI 最后提出的继续动作。"
            )

        if len(history_lines) <= 4:
            return None
        return "\n".join(history_lines)

    def _append_history_context_to_prompt(self, *, user_prompt: str, history_context_block: str | None) -> str:
        """把历史上下文追加到当前用户提示词末尾。

        这里刻意不把历史块放到最前面。模型供应商的前缀缓存通常依赖请求开头
        稳定一致；如果每轮都把动态历史塞在开头，`instructions + 记录上下文`
        这些稳定内容就无法形成可复用前缀。
        """

        if not history_context_block:
            return user_prompt

        return "\n\n".join(
            [
                user_prompt,
                "多轮上下文承接要求：",
                history_context_block,
            ]
        )

    def _build_statistics_history_context_block(
        self,
        *,
        history: list[dict[str, str]],
        question: str,
    ) -> str | None:
        """把统计页追问历史压缩成可放进当前 user prompt 的短上下文。

        米醋 / OpenClaudeCode 的 Responses 请求不发送独立历史 input，因此统计页也
        必须把最近问答写进当前 prompt。这样用户追问“那这个设备呢”时，模型仍能
        看到上一轮关于统计窗口、风险设备或缺陷分布的结论。
        """

        if not history:
            return None

        role_labels = {
            "user": "用户",
            "assistant": "AI",
        }
        history_lines = [
            "统计页历史对话：",
            "以下是当前统计分析弹窗里的最近问答。你必须承接这些历史里的统计窗口、筛选条件、上一轮结论和用户指代。",
        ]
        for index, item in enumerate(history[-6:], start=1):
            role = role_labels.get(item["role"], item["role"])
            history_lines.append(f"{index}. {role}: {self._trim_prompt_text(item['content'], max_chars=260)}")

        normalized_question = question.strip()
        if normalized_question in {"可以", "好的", "继续", "写", "帮我写"}:
            history_lines.append(f"当前用户只回复了“{normalized_question}”，请直接执行上一轮 AI 最后提出的统计分析动作。")

        return "\n".join(history_lines)

    def _is_openclaudecode_responses_vision_request(
        self,
        *,
        model_context: dict[str, Any],
        image_assets: list[dict[str, str]],
    ) -> bool:
        """判断当前请求是否需要走米醋 Responses 视觉紧凑提示词。

        这个判断只针对已经确认的问题组合：OpenClaudeCode / 米醋网关、
        OpenAI Responses 协议、并且本轮实际附带了图片。其他供应商仍保持原来的
        完整提示词，避免无关模型行为被一起改动。
        """

        if not image_assets:
            return False
        if str(model_context.get("protocol_type") or "") != "openai_responses":
            return False

        return self._is_openclaudecode_gateway(model_context=model_context)

    def _should_use_openclaudecode_compact_prompt(self, *, model_context: dict[str, Any]) -> bool:
        """判断当前请求是否应使用米醋 / OpenClaudeCode 的紧凑提示词。

        米醋 Responses 网关在带图和长上下文叠加时容易出现 502；后续追问即使不再
        重发图片，也应该继续使用紧凑摘要与压缩历史，避免把上一轮长回答完整塞回网关。
        """

        if str(model_context.get("protocol_type") or "") != "openai_responses":
            return False
        return self._is_openclaudecode_gateway(model_context=model_context)

    def _trim_prompt_text(self, value: Any, *, max_chars: int = 180) -> str:
        """把任意上下文值压缩成适合放进提示词的短文本。

        参数:
            value: 可能来自数据库、JSON 字段或历史消息的原始值。
            max_chars: 最多保留的字符数，超过后用省略号截断。

        返回:
            返回已序列化并压缩后的字符串，避免长调试块把视觉请求体撑大。
        """

        serialized_value = self._serialize_context_value(value)
        if isinstance(serialized_value, (dict, list)):
            text_value = json.dumps(serialized_value, ensure_ascii=False, separators=(",", ":"))
        elif serialized_value is None:
            text_value = "null"
        else:
            text_value = str(serialized_value)

        normalized_text = " ".join(text_value.split())
        if len(normalized_text) <= max_chars:
            return normalized_text
        return f"{normalized_text[:max_chars]}..."

    def _build_compact_nested_context_lines(self, *, context: dict[str, Any]) -> list[str]:
        """提取视觉、传感器、判定和设备上下文里的短字段。

        生产记录里这些字段可能包含调试 blob、原始数组或长日志；紧凑视觉请求只保留
        少量可读标量，长字段只说明“已登记”，不把原文塞进供应商 payload。
        """

        context_labels = {
            "vision_context": "视觉上下文",
            "sensor_context": "传感器上下文",
            "decision_context": "判定上下文",
            "device_context": "设备上下文",
        }
        skipped_key_markers = {"debug", "blob", "raw", "base64", "bytes", "image", "trace", "log"}
        lines: list[str] = []

        for context_key, context_label in context_labels.items():
            raw_context = context.get(context_key)
            if not isinstance(raw_context, dict) or not raw_context:
                continue

            compact_items: list[str] = []
            for key, value in raw_context.items():
                normalized_key = str(key).lower()
                if any(marker in normalized_key for marker in skipped_key_markers):
                    continue
                if isinstance(value, (dict, list)) and len(json.dumps(value, ensure_ascii=False, default=str)) > 240:
                    continue

                compact_items.append(f"{key}={self._trim_prompt_text(value, max_chars=80)}")
                if len(compact_items) >= 5:
                    break

            if compact_items:
                lines.append(f"- {context_label}: {'；'.join(compact_items)}")
            else:
                lines.append(f"- {context_label}: 已登记，但内容以长调试/原始数据为主，本轮不展开原文。")

        return lines

    def _build_context_explanation_lines(self, *, context: dict[str, Any]) -> list[str]:
        """把云端中文上下文解释压缩成 AI 提示词里的独立文本块。

        参数:
            context: 当前记录上下文字典，可能包含 `context_explanations`。

        返回:
            返回多行中文解释文本；没有解释时返回空列表，调用方可直接跳过该块。
        """

        context_explanations = context.get("context_explanations")
        if not isinstance(context_explanations, dict):
            return []

        lines = ["中文上下文解释："]
        summary = str(context_explanations.get("summary") or "").strip()
        if summary:
            lines.append(f"- 总览：{self._trim_prompt_text(summary, max_chars=220)}")

        groups = context_explanations.get("groups")
        if not isinstance(groups, list):
            return lines

        for group in groups:
            if not isinstance(group, dict):
                continue
            title = str(group.get("title") or group.get("key") or "上下文").strip()
            group_summary = str(group.get("summary") or "").strip()
            if group_summary:
                lines.append(f"- {title}：{self._trim_prompt_text(group_summary, max_chars=260)}")

            items = group.get("items")
            if not isinstance(items, list):
                continue
            for item in items[:4]:
                if not isinstance(item, dict):
                    continue
                source_path = str(item.get("source_path") or "").strip()
                explanation = str(item.get("explanation") or "").strip()
                if not explanation:
                    continue
                prefix = f"{source_path} -> " if source_path else ""
                lines.append(f"  - {prefix}{self._trim_prompt_text(explanation, max_chars=240)}")

        return lines

    def _build_compact_record_context(self, *, context: dict[str, Any]) -> str:
        """构造紧凑结构化摘要，替代完整 JSON 上下文。

        返回:
            一段短文本，保留良坏判断、时间链路、复核状态、文件数量等关键字段；
            不展开 `vision_context`、`device_context` 等可能很长的原始调试对象。
        """

        field_pairs = [
            ("record_id", context.get("record_id")),
            ("record_no", context.get("record_no")),
            ("part", f"{context.get('part_name')} / {context.get('part_code')}"),
            ("device", f"{context.get('device_name')} / {context.get('device_code')}"),
            ("mp157_result", context.get("result")),
            ("effective_result", context.get("effective_result")),
            ("review_status", context.get("review_status")),
            ("defect_type", context.get("defect_type")),
            ("defect_desc", context.get("defect_desc")),
            ("confidence_score", context.get("confidence_score")),
            ("captured_at", context.get("captured_at")),
            ("detected_at", context.get("detected_at")),
            ("uploaded_at", context.get("uploaded_at")),
            ("storage_last_modified", context.get("storage_last_modified")),
            ("file_count", context.get("file_count")),
            ("available_file_kinds", context.get("available_file_kinds")),
            ("review_count", context.get("review_count")),
            ("latest_review_decision", context.get("latest_review_decision")),
            ("latest_review_comment", context.get("latest_review_comment")),
            ("latest_reviewed_at", context.get("latest_reviewed_at")),
        ]

        lines = ["紧凑结构化摘要："]
        for field_name, field_value in field_pairs:
            lines.append(f"- {field_name}: {self._trim_prompt_text(field_value, max_chars=160)}")
        lines.extend(self._build_context_explanation_lines(context=context))
        lines.extend(self._build_compact_nested_context_lines(context=context))
        return "\n".join(lines)

    def _infer_compact_file_purpose(self, *, file_object: dict[str, Any]) -> str:
        """在文件用途缺失时，根据文件名推断图片在模型链路里的角色。"""

        if purpose := str(file_object.get("analysis_purpose") or "").strip():
            return self._trim_prompt_text(purpose, max_chars=180)

        object_key = str(file_object.get("object_key") or "").lower()
        file_name = object_key.rsplit("/", 1)[-1]
        if "_mask" in file_name or file_name.endswith("mask.png"):
            return "UNet mask：显示疑似缺陷像素区域，用于判断分割模型认为哪里异常。"
        if "_overlay" in file_name or file_name.endswith("overlay.jpg") or file_name.endswith("overlay.png"):
            return "UNet overlay：把 mask 叠加到原图上，用于定位缺陷落在零件哪个区域。"
        if any(marker in file_name for marker in ["mobilenet", "classification", "classify", "classifier"]):
            return "MobileNetV3-Small 分类结果图：用于核对整图 good/bad 分类倾向。"
        if "_raw" in file_name or file_name.endswith("raw.jpg") or file_object.get("file_kind") == "source":
            return "原始采集图：未叠加模型颜色的真实外观，用于观察划伤、缺口、毛刺、污渍和变形。"
        return "补充证据图：需要结合文件名、记录字段和其它图像共同判断。"

    def _build_compact_file_context(self, *, referenced_files: list[dict[str, Any]]) -> str:
        """构造四张模型产物图的紧凑用途说明。

        这里固定解释 UNet 和 MobileNetV3-Small 的角色，避免模型只看到图片却不知道
        mask、overlay、分类图和原始图分别该怎样参与良坏判断。

        普通追问轮次不会重复上传图片本体，因此这里必须同时给出 `preview_url`
        或 COS 对象位置。模型如果需要承接上一轮视觉依据，就能知道这几张图
        分别在哪里，而不是把追问当成完全无图的新问题。
        """

        lines = [
            "图像证据用途说明：",
            "- UNet mask：看疑似缺陷像素区域，不等于最终缺陷，需结合原图确认。",
            "- UNet overlay：看疑似缺陷在零件上的位置，例如外轮廓、内孔边缘或表面。",
            "- MobileNetV3-Small 分类结果图：看整图 good/bad 倾向，需与 UNet 和原图交叉验证。",
            "- 原始采集图：看真实外观，是判断划伤、缺口、毛刺、污渍、压痕、变形的主要视觉证据。",
        ]

        if not referenced_files:
            lines.append("- 当前没有登记文件对象；如果仍附带图片，请直接按图像内容分析。")
            return "\n".join(lines)

        for index, file_object in enumerate(referenced_files[:4], start=1):
            preview_url = str(file_object.get("preview_url") or "").strip()
            readable_location = (
                f"preview_url={self._trim_prompt_text(preview_url, max_chars=220)}"
                if preview_url
                else (
                    "preview_url=未登记；"
                    f"bucket={self._trim_prompt_text(file_object.get('bucket_name'), max_chars=80)}；"
                    f"region={self._trim_prompt_text(file_object.get('region'), max_chars=40)}"
                )
            )
            lines.append(
                (
                    f"- 第 {index} 张：kind={file_object.get('file_kind')}；"
                    f"object_key={self._trim_prompt_text(file_object.get('object_key'), max_chars=150)}；"
                    f"{readable_location}；用途={self._infer_compact_file_purpose(file_object=file_object)}"
                )
            )

        return "\n".join(lines)

    def _build_compact_history_context_block(self, *, history: list[dict[str, str]], question: str) -> str | None:
        """把多轮对话历史压缩成短上下文，保留追问记忆但控制请求体大小。"""

        if not history:
            return None

        short_confirmation_words = {"可以", "好", "好的", "行", "嗯", "继续", "对", "是的", "写", "帮我写"}
        role_labels = {
            "user": "用户",
            "assistant": "AI",
        }
        lines = [
            "压缩后的同一弹窗历史：",
            "必须承接最近结论、风险位置和上一轮承诺的动作；短确认词要理解为确认上一轮动作。",
        ]

        for index, item in enumerate(history[-4:], start=1):
            role = role_labels.get(item["role"], item["role"])
            lines.append(f"{index}. {role}: {self._trim_prompt_text(item['content'], max_chars=220)}")

        normalized_question = question.strip()
        if normalized_question in short_confirmation_words:
            lines.append(f"当前用户只回复了“{normalized_question}”，请直接执行上一轮 AI 最后提出的可继续动作。")

        return "\n".join(lines)

    def _build_compact_history_for_provider(self, *, history: list[dict[str, str]]) -> list[dict[str, str]]:
        """压缩传给 Responses `input` 数组的历史消息。

        压缩后的历史仍让模型保留上下文记忆，但不会把上一轮长回答和长问题完整重复上传，
        从而降低米醋 / Cloudflare 在带图请求上的 502 风险。
        """

        compact_history: list[dict[str, str]] = []
        for item in history[-4:]:
            compact_history.append(
                {
                    "role": item["role"],
                    "content": self._trim_prompt_text(item["content"], max_chars=360),
                }
            )
        return compact_history

    def _build_provider_history_for_compact_prompt(
        self,
        *,
        model_context: dict[str, Any],
        history: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """为紧凑提示词链路决定是否还需要向供应商发送独立历史消息。

        米醋 / OpenClaudeCode 的 HTTP Responses 对“纯文本追问 + 多条历史 input”
        组合不稳定，生产第二轮追问会在 SSE 中返回 Cloudflare 502。这里按 CLI /
        opencode 的本地会话思路处理：历史先由后端压缩并写进当前 user prompt，
        上游 `input` 数组只保留本轮 user 消息，避免网关把追问当成多消息会话失败。

        其他网关仍保留压缩历史消息，避免无关供应商的多轮行为被一起改变。
        """

        if self._is_openclaudecode_gateway(model_context=model_context):
            return []
        return self._build_compact_history_for_provider(history=history)

    def _build_compact_system_instruction(
        self,
        *,
        model_context: dict[str, Any],
        has_loaded_images: bool,
        task_mode: str,
    ) -> str:
        """构造米醋 Responses 视觉请求专用的短系统提示词。"""

        image_line = (
            "本轮已附带图像，必须观察图片并结合字段判断。"
            if has_loaded_images
            else "本轮没有附带图像字节，只能基于结构化摘要和文件用途说明回答。"
        )
        task_line = (
            "输出小节：1. 直接回答；2. 判断依据；3. 风险边界；4. 修正板端结果填写建议；5. 下一步建议。"
            if task_mode == "chat"
            else "输出小节：1. 复核结论；2. 关键证据；3. 风险边界；4. 修正板端结果填写建议；5. 处置建议。"
        )
        return "\n".join(
            [
                "你是工业缺陷检测系统里的 AI 复核助理，只围绕当前这一条记录回答，必须使用中文。",
                image_line,
                "用户问良品还是坏品时，先给倾向结论：更像良品、更像不良或证据不足；随后解释为什么。",
                "不能把“尚未人工审核”当作回避判断的前提，它只能作为风险边界或下一步复核建议。",
                "当前业务默认单面检测；不要默认要求背面、多角度或多工位补图，只能围绕当前这一面可见证据分析。",
                "四张常见图片含义：UNet mask 看疑似缺陷像素，UNet overlay 看缺陷位置，MobileNetV3-Small 图看 good/bad 分类倾向，原始采集图看真实外观。",
                "如果 AI 建议与 MP157 初检 result 不一致，必须写“修正板端结果填写建议”：decision 填 good/bad/uncertain，defect_type 填缺陷类型或 null，cloud_reason 写一句可复制的中文原因。",
                "区分确定事实和推断；图像不清或字段缺失时说明不确定性，但仍要给当前证据下的建议。",
                f"当前模型：{model_context.get('display_name')} / {model_context.get('model_identifier')}；协议：{model_context.get('protocol_type')}。",
                task_line,
            ]
        )

    def _build_compact_chat_user_prompt(
        self,
        *,
        question: str,
        context: dict[str, Any],
        referenced_files: list[dict[str, Any]],
        image_assets: list[dict[str, str]],
        history_context_block: str | None,
    ) -> str:
        """构造米醋 Responses 带图对话的紧凑用户提示词。"""

        image_status = f"本轮实际附带图片数量：{len(image_assets)}。" if image_assets else "本轮未附带图片字节。"
        prompt_parts = [
            "请基于当前记录、图像证据用途说明、同一弹窗历史和下方紧凑摘要回答；如果本轮没有图像字节，不要声称重新看到了图片。",
            image_status,
            self._build_compact_file_context(referenced_files=referenced_files),
            self._build_compact_record_context(context=context),
        ]
        if history_context_block:
            prompt_parts.append(history_context_block)
        prompt_parts.extend(
            [
                "回答要求：先说这个更像好的、坏的还是证据不足；再说明图像依据、字段依据、冲突点和不确定性。",
                "如果你的建议与 MP157 初检 result 冲突，补充 decision、defect_type、cloud_reason 的填写建议。",
                f"用户问题：{question.strip()}",
            ]
        )
        return "\n\n".join(prompt_parts)

    def _build_compact_no_image_chat_user_prompt(
        self,
        *,
        question: str,
        context: dict[str, Any],
        referenced_files: list[dict[str, Any]],
        history_context_block: str | None,
    ) -> str:
        """构造带图请求失败后同端点纯文本重试的紧凑提示词。

        这条路径必须继续保留文件用途和压缩历史，但明确告诉模型本次没有图像字节，
        只能基于上一轮上下文、结构化摘要和文件说明给出建议。
        """

        prompt_parts = [
            "上一轮带图 Responses 请求失败，本轮改为同端点纯文本重试。",
            "本轮没有成功附带图像字节，请不要声称重新看到了图片；可以基于同一弹窗历史、结构化摘要和文件用途说明继续回答。",
            self._build_compact_file_context(referenced_files=referenced_files),
            self._build_compact_record_context(context=context),
        ]
        if history_context_block:
            prompt_parts.append(history_context_block)
        prompt_parts.extend(
            [
                "回答要求：承接上一轮结论，不要重新当成第一次对话；如果用户问修正板端结果，直接给 decision、defect_type、cloud_reason。",
                f"用户问题：{question.strip()}",
            ]
        )
        return "\n\n".join(prompt_parts)

    def _build_compact_review_user_prompt(
        self,
        *,
        note: str | None,
        context: dict[str, Any],
        referenced_files: list[dict[str, Any]],
        image_assets: list[dict[str, str]],
    ) -> str:
        """构造米醋 Responses 带图复核摘要的紧凑用户提示词。"""

        review_note = (note or "").strip() or "无"
        image_status = f"本轮实际附带图片数量：{len(image_assets)}。" if image_assets else "本轮未附带图片字节。"
        return "\n\n".join(
            [
                "请给出当前检测记录的 AI 复核意见。",
                image_status,
                self._build_compact_file_context(referenced_files=referenced_files),
                self._build_compact_record_context(context=context),
                f"补充要求：{self._trim_prompt_text(review_note, max_chars=260)}",
                "必须输出明确倾向、关键证据、风险边界、修正板端结果填写建议和现场处置建议。",
            ]
        )

    def _build_context_snapshot(
        self,
        *,
        context: dict[str, Any],
        referenced_files: list[dict[str, Any]],
    ) -> str:
        """把当前检测记录上下文整理成模型容易消费的结构化快照。"""

        normalized_context = self._serialize_context_value(context)
        normalized_files = [
            {
                "id": item.get("id"),
                "file_kind": item.get("file_kind"),
                "object_key": item.get("object_key"),
                "uploaded_at": self._serialize_context_value(item.get("uploaded_at")),
                "preview_url": item.get("preview_url"),
                "analysis_purpose": item.get("analysis_purpose"),
            }
            for item in referenced_files
        ]
        return json.dumps(
            {
                "record_context": normalized_context,
                "referenced_files": normalized_files,
            },
            ensure_ascii=False,
            indent=2,
        )

    def _build_system_instruction(
        self,
        *,
        model_context: dict[str, Any],
        has_loaded_images: bool,
        task_mode: str,
    ) -> str:
        """生成所有协议共用的系统提示词。"""

        vision_line = (
            "当前请求已附带可直接读取的图像内容，你必须把图像证据作为核心依据之一，并与结构化上下文交叉核对。"
            if has_loaded_images
            else "当前请求没有成功附带图像字节，你必须明确说明“本轮未取得图像证据”，并仅基于结构化上下文回答。"
        )
        model_line = (
            f"当前运行模型：{model_context['display_name']} / {model_context['model_identifier']}；"
            f"协议：{model_context['protocol_type']}；网关：{model_context['gateway_name']}。"
        )
        output_contract = (
            [
                "回答结构固定为：1. 直接回答；2. 关键依据；3. 风险与不确定性；4. 下一步建议。",
                "如果用户问题只涉及某一维度，例如时间链路、缺陷位置或误检原因，也必须把该维度讲透，并补充边界说明。",
                "如果用户问题比较宽泛，你需要主动补全成一份完整的记录解读，至少覆盖结果、证据、风险和复核动作。",
                "回答时不要只机械复述字段，而要把字段和图像证据翻译成普通人能执行的质检判断。",
            ]
            if task_mode == "chat"
            else [
                "回答结构固定为：1. 复核结论；2. 关键证据；3. 风险判断；4. 处置建议；5. 仍需补充的数据或现场确认项。",
                "复核结论不能只给一句模糊描述，必须明确指出更倾向良品、不良、待人工复核，还是证据不足。",
                "你必须把结论拆成明确的证据链，说明哪些来自结构化字段、哪些来自图像、哪些只是基于现有证据的推断。",
                "如果当前单面图像已经足够支撑结论，不要为了凑格式而强行要求补图。",
            ]
        )
        return "\n".join(
            [
                "你是工业缺陷检测系统里的 AI 复核助理。",
                "你只能围绕当前这一条检测记录回答，不能脱离记录上下文泛泛而谈。",
                "回答必须使用中文。",
                "你必须优先核对以下维度：初检结果、最终结果、审核状态、缺陷类型、缺陷说明、置信度、复核历史、时间链路、图像/文件证据是否完整。",
                "你还必须补充检查：是否存在多工位结果冲突、是否存在字段缺失、是否存在时间先后异常、是否存在‘当前结论已经被人工复核覆盖’但用户仍在引用旧结果的情况。",
                "如果图像证据不足、模型不支持视觉、或上下文信息不足，必须直接说明，不得编造，不得把推测写成事实。",
                "当结构化字段与图像、初检结果与人工复核、时间链路前后含义存在冲突时，你必须显式指出冲突，而不是自行抹平。",
                "你给出的结论需要区分“确定事实”和“基于现有证据的推断”；凡是推断都要用“可能/倾向于/需进一步确认”等措辞。",
                "你必须结合当前记录是否已有人工复核、是否仍待审核、是否存在多张图像、是否缺少关键字段，给出操作层面的建议；但不能把“尚未人工审核”当成回避判断的理由。",
                "如果用户追问‘好的还是坏的’、‘为什么这样判’、‘是否误检’、‘需不需要人工复核’，必须先给出基于当前图像和字段的良品/不良/证据不足倾向，再说明判断依据，不要只重复结果标签或审核状态。",
                "给出复核重点时，优先围绕当前图像可见的外轮廓、内孔边缘、毛刺、缺口、划伤、压痕、污渍、锈蚀、变形和异物等具体外观项展开。",
                vision_line,
                model_line,
                *self._build_single_side_review_guard_lines(),
                *self._build_board_correction_prompt_lines(),
                *output_contract,
            ]
        )

    def _build_chat_user_prompt(
        self,
        *,
        question: str,
        context: dict[str, Any],
        referenced_files: list[dict[str, Any]],
        image_assets: list[dict[str, str]],
    ) -> str:
        """构造 AI 对话问题对应的用户提示词。"""

        image_status = (
            f"已成功附带 {len(image_assets)} 张图像内容，可用于当前轮分析。"
            if image_assets
            else "本轮没有成功附带图像内容，只能参考结构化字段与文件对象信息。"
        )
        context_snapshot = self._build_context_snapshot(
            context=context,
            referenced_files=referenced_files,
        )
        context_explanation_block = "\n".join(self._build_context_explanation_lines(context=context))
        return "\n\n".join(
            [
                "请基于下面这条检测记录进行分析，不要跳出当前记录。",
                "当前业务默认只检测单面图像，请严格基于当前这一面回答；除非上下文明确存在另一面或多工位信息，否则不要要求补拍另一面、背面或多角度图片。",
                "分析时请至少检查：结果一致性、缺陷信息、复核历史、时间链路、图像证据是否充分、当前这一面能确认什么、还有什么只能人工兜底确认。",
                "如果用户的问题本身没有指明分析维度，你要主动补全为：当前记录总体判断、主要证据、风险边界、下一步建议。",
                "如果结构化结果、人工复核、文件证据之间有任何不一致，必须单独指出冲突，不允许默认它们完全一致。",
                "这批图片通常由 UNet + MobileNetV3-Small 链路产生：原始采集图用于看真实外观，UNet mask 用于看疑似缺陷像素区域，UNet overlay 用于定位缺陷落在零件哪里，MobileNetV3-Small 分类结果图用于核对整图 good/bad 分类标签。",
                "用户询问“好的还是坏的”时，必须先给出倾向结论：更像良品、更像不良，或证据不足；随后说明这个建议来自哪些图像、哪些结构化字段和哪些不确定性。",
                "不能把“尚未人工审核”当成回避判断的理由；它只能作为风险边界或下一步复核建议，不能替代你对当前图像和模型输出的综合分析。",
                *self._build_board_correction_prompt_lines(),
                image_status,
                context_explanation_block,
                "结构化上下文：",
                context_snapshot,
                "请先直接回答用户问题，再补充关键依据、风险边界和建议动作。回答要自然、具体、普通人能看懂；如果需要补充证据，默认只建议当前这一面的更清晰近景、标注或缺失字段，不要默认另一面。",
                f"用户问题：{question.strip()}",
            ]
        )

    def _build_review_user_prompt(
        self,
        *,
        note: str | None,
        context: dict[str, Any],
        referenced_files: list[dict[str, Any]],
        image_assets: list[dict[str, str]],
    ) -> str:
        """构造 AI 复核摘要对应的用户提示词。"""

        review_note = (note or "").strip()
        note_block = f"补充要求：{review_note}" if review_note else "补充要求：无"
        image_status = (
            f"已成功附带 {len(image_assets)} 张图像内容。"
            if image_assets
            else "本轮没有成功附带图像内容。"
        )
        context_snapshot = self._build_context_snapshot(
            context=context,
            referenced_files=referenced_files,
        )
        context_explanation_block = "\n".join(self._build_context_explanation_lines(context=context))
        return "\n\n".join(
            [
                "请对当前检测记录给出一份完整、谨慎、可落地的 AI 复核意见。",
                "当前业务默认只检测单面图像。除非上下文明确提供了另一面、另一工位或多角度图像，否则不要建议补拍另一面，也不要把另一面的假设写进结论。",
                "你必须覆盖：最终判定倾向、关键证据、是否存在误检/漏检风险、是否应继续人工复核、当前这一面还缺哪些证据或现场确认动作。",
                "你必须逐项检查：初检结果与最终结果是否一致、缺陷描述是否支撑当前结论、时间链路是否合理、历史复核是否改变了结论、图像证据是否足以支撑判断、是否需要升级为人工复判。",
                "如果需要给现场动作，请明确写清楚重点看哪里，例如外轮廓、内孔边缘、划伤、压痕、毛刺、缺口、变形、异物或污渍，而不是只写“建议复核”。",
                "输出要求：使用 5 个小节，内容要充分但不要空泛重复；每个小节都应围绕当前记录的真实字段展开，并让非算法人员也能看懂。",
                *self._build_board_correction_prompt_lines(),
                image_status,
                note_block,
                context_explanation_block,
                "结构化上下文：",
                context_snapshot,
            ]
        )

    def _build_statistics_system_instruction(self, *, model_context: dict[str, Any]) -> str:
        """构造统计页批次分析专用系统提示词。"""

        model_line = (
            f"当前运行模型：{model_context['display_name']} / {model_context['model_identifier']}；"
            f"协议：{model_context['protocol_type']}；网关：{model_context['gateway_name']}。"
        )
        return "\n".join(
            [
                "你是工业缺陷检测系统里的统计复盘分析助理。",
                "你只能围绕本次给出的统计窗口、筛选条件、批次指标、趋势数据、缺陷分布、零件排行和设备排行进行分析。",
                "回答必须使用中文，不能脱离给定统计范围泛泛而谈，也不能把局部筛选结果误写成全局产线结论。",
                "你必须优先分析以下维度：总体良率、不良/待确认规模、时间趋势波动、缺陷集中度、零件风险集中、设备风险集中、审核积压、数据完整性。",
                "你还必须显式检查：样本量是否足够、趋势是否只由个别峰值造成、缺陷是否高度集中在单一类型、是否存在审核积压掩盖真实良率、局部筛选是否会放大单一零件或单一设备的异常。",
                "凡是明确来自数据的内容，要作为事实陈述；凡是对原因的解释，都必须标注为推断或可能原因，不能伪装成已证实结论。",
                "如果样本量过小、时间窗口过短、筛选条件过窄或数据明显不足，必须明确指出统计结论的局限性。",
                "如果关键发现之间存在张力，例如良率总体还可以但某一设备不良异常集中、或待确认数量较高导致结论不稳，你必须把这种张力讲清楚。",
                "输出结构固定为：1. 总体结论；2. 核心数据发现；3. 风险定位；4. 可能原因（注明推断）；5. 建议动作（按优先级）；6. 仍需补充的数据与后续观察点。",
                "建议动作必须尽量落到具体执行层，例如：优先复核哪些缺陷、追查哪些设备、补采哪些样本、监控哪些指标。",
                model_line,
            ]
        )

    def _build_statistics_user_prompt(
        self,
        *,
        note: str | None,
        statistics_context: dict[str, Any],
    ) -> str:
        """构造统计页 AI 批次分析用户提示词。"""

        analysis_note = (note or "").strip()
        note_block = f"补充关注点：{analysis_note}" if analysis_note else "补充关注点：无"
        return "\n\n".join(
            [
                "请基于下面这份统计报告，对当前批次或当前筛选窗口内的产品质量状态进行完整分析。",
                "你需要结合统计概览、趋势、缺陷分布、零件排行、设备排行和系统提炼出的关键发现一起判断。",
                "分析时请不要只重复图表数值，而要指出哪些现象最值得业务侧优先处理、哪些只是背景信息、哪些结论仍然不稳。",
                "如果当前筛选条件只覆盖某个零件、某台设备或较短时间窗口，请把结论限定在这个范围内。",
                note_block,
                "统计报告摘要：",
                self._build_statistics_snapshot_for_prompt(statistics_context=statistics_context),
            ]
        )

    def _build_statistics_chat_system_instruction(self, *, model_context: dict[str, Any]) -> str:
        """构造统计页多轮追问专用系统提示词。"""

        model_line = (
            f"当前运行模型：{model_context['display_name']} / {model_context['model_identifier']}；"
            f"协议：{model_context['protocol_type']}；网关：{model_context['gateway_name']}。"
        )
        return "\n".join(
            [
                "你是工业缺陷检测系统里的统计复盘追问助理。",
                "你只能围绕当前这一个统计窗口、当前筛选条件以及当前会话历史回答，不得跳出范围泛泛而谈。",
                "回答必须使用中文，并且要让现场质检员、产线负责人和普通管理人员都能看懂。",
                "如果用户的问题聚焦某一个维度，例如趋势、缺陷类型、零件、设备、待审核积压或样本量，你要优先直接回答这一维度，再补充它对整体判断的影响。",
                "如果用户的问题比较宽泛，你要先给结论，再解释关键数据依据、风险边界和后续动作。",
                "你必须始终检查并说明：当前样本量是否足够、筛选范围是否会放大局部异常、待审核数量是否会影响结论稳定性、原因判断哪些只是推断。",
                "凡是明确来自统计快照的数据，要当作事实陈述；凡是对原因的解释，都必须标注为推断、倾向或可能原因。",
                "如果数据不足、窗口过短、筛选条件过窄或当前问题超出统计快照可支撑的范围，必须直接指出限制，不能编造。",
                "输出结构固定为：1. 直接回答；2. 关键数据依据；3. 风险与不确定性；4. 建议动作或后续观察点。",
                model_line,
            ]
        )

    def _build_statistics_chat_user_prompt(
        self,
        *,
        question: str,
        note: str | None,
        statistics_context: dict[str, Any],
    ) -> str:
        """构造统计页多轮追问的用户提示词。"""

        analysis_note = (note or "").strip()
        note_block = f"补充关注点：{analysis_note}" if analysis_note else "补充关注点：无"
        return "\n\n".join(
            [
                "请继续围绕下面这份统计报告回答用户追问，不要脱离当前统计窗口。",
                "如果当前问题只覆盖某一部分，请先针对该问题直接作答，再补充它对整体批次判断的影响。",
                "如果问题涉及设备责任、零件风险、缺陷集中、审核积压或时间趋势，请明确说明判断依据来自哪些统计字段，而不是只给结论。",
                "如果原因只能推断，必须说明这是推断，不得写成已经验证的事实。",
                note_block,
                "统计报告摘要：",
                self._build_statistics_snapshot_for_prompt(statistics_context=statistics_context),
                f"用户问题：{question.strip()}",
            ]
        )

    def _build_statistics_snapshot_for_prompt(
        self,
        *,
        statistics_context: dict[str, Any],
    ) -> str:
        """把统计概览整理成更适合模型消费的结构化文本摘要。

        这里刻意不直接塞整包 JSON，原因有两个：
        1. 统计页原始快照里包含较深的嵌套结构和图库数据，提示词会显著膨胀。
        2. 生产实测 `OpenClaudeCode + Grok + /v1/messages` 在用户消息中携带较长 JSON 块时，
           可能只返回 `message_start` 后直接结束，导致“已消费但没有输出”。
        因此这里统一压缩成稳定的文本摘要，既减小输入体积，也规避该兼容性问题。
        """

        filters = statistics_context.get("filters") if isinstance(statistics_context.get("filters"), dict) else {}
        summary = statistics_context.get("summary") if isinstance(statistics_context.get("summary"), dict) else {}
        daily_trend = statistics_context.get("daily_trend") if isinstance(statistics_context.get("daily_trend"), list) else []
        defect_distribution = (
            statistics_context.get("defect_distribution")
            if isinstance(statistics_context.get("defect_distribution"), list)
            else []
        )
        result_distribution = (
            statistics_context.get("result_distribution")
            if isinstance(statistics_context.get("result_distribution"), list)
            else []
        )
        review_status_distribution = (
            statistics_context.get("review_status_distribution")
            if isinstance(statistics_context.get("review_status_distribution"), list)
            else []
        )
        part_quality_ranking = (
            statistics_context.get("part_quality_ranking")
            if isinstance(statistics_context.get("part_quality_ranking"), list)
            else []
        )
        device_quality_ranking = (
            statistics_context.get("device_quality_ranking")
            if isinstance(statistics_context.get("device_quality_ranking"), list)
            else []
        )
        key_findings = statistics_context.get("key_findings") if isinstance(statistics_context.get("key_findings"), list) else []

        lines = [
            "【筛选条件】",
            (
                f"- 开始日期：{filters.get('start_date') or '未指定'}；"
                f"结束日期：{filters.get('end_date') or '未指定'}；"
                f"回看天数：{filters.get('days') or '未指定'}。"
            ),
            (
                f"- 零件 ID：{filters.get('part_id') or '全部'}；"
                f"设备 ID：{filters.get('device_id') or '全部'}。"
            ),
            "【汇总指标】",
            (
                f"- 总数：{summary.get('total_count', 0)}；良品：{summary.get('good_count', 0)}；"
                f"不良：{summary.get('bad_count', 0)}；待确认：{summary.get('uncertain_count', 0)}；"
                f"已审核：{summary.get('reviewed_count', 0)}；待审核：{summary.get('pending_review_count', 0)}；"
                f"良率：{summary.get('pass_rate', 0)}。"
            ),
        ]

        if daily_trend:
            lines.append("【时间趋势（最多 7 条）】")
            for item in daily_trend[:7]:
                lines.append(
                    f"- {item.get('date') or '未知日期'}：总数 {item.get('total_count', 0)}，"
                    f"良品 {item.get('good_count', 0)}，不良 {item.get('bad_count', 0)}，"
                    f"待确认 {item.get('uncertain_count', 0)}。"
                )

        if defect_distribution:
            lines.append("【缺陷分布（最多 8 条）】")
            for item in defect_distribution[:8]:
                lines.append(f"- {item.get('defect_type') or '未分类'}：{item.get('count', 0)}。")

        if result_distribution:
            lines.append("【结果分布】")
            for item in result_distribution[:8]:
                lines.append(f"- {item.get('result') or '未知'}：{item.get('count', 0)}。")

        if review_status_distribution:
            lines.append("【审核状态分布】")
            for item in review_status_distribution[:8]:
                lines.append(f"- {item.get('review_status') or '未知'}：{item.get('count', 0)}。")

        if part_quality_ranking:
            lines.append("【零件风险排行（最多 5 条）】")
            for item in part_quality_ranking[:5]:
                lines.append(
                    f"- {item.get('part_name') or '未知零件'}（{item.get('part_code') or '无编码'}）："
                    f"总数 {item.get('total_count', 0)}，不良 {item.get('bad_count', 0)}，"
                    f"待确认 {item.get('uncertain_count', 0)}，良率 {item.get('pass_rate', 0)}。"
                )

        if device_quality_ranking:
            lines.append("【设备风险排行（最多 5 条）】")
            for item in device_quality_ranking[:5]:
                lines.append(
                    f"- {item.get('device_name') or '未知设备'}（{item.get('device_code') or '无编码'}）："
                    f"总数 {item.get('total_count', 0)}，不良 {item.get('bad_count', 0)}，"
                    f"待确认 {item.get('uncertain_count', 0)}，良率 {item.get('pass_rate', 0)}。"
                )

        if key_findings:
            lines.append("【关键发现】")
            for item in key_findings[:8]:
                if isinstance(item, str) and item.strip():
                    lines.append(f"- {item.strip()}")

        generated_at = statistics_context.get("generated_at")
        if isinstance(generated_at, str) and generated_at.strip():
            lines.append("【生成时间】")
            lines.append(f"- {generated_at}")

        return "\n".join(lines)

    def _build_statistics_suggested_questions(
        self,
        *,
        statistics_context: dict[str, Any],
    ) -> list[str]:
        """根据统计快照生成下一轮推荐追问。"""

        suggestions = [
            "这批数据里现在最值得优先处理的风险点是什么？",
            "从现有统计看，更像是设备侧问题还是零件批次问题？",
            "当前待审核数量会不会掩盖真实良率？",
            "还需要补哪些数据，才能把当前结论说得更稳？",
        ]

        defect_distribution = statistics_context.get("defect_distribution")
        if isinstance(defect_distribution, list) and defect_distribution:
            top_defect = defect_distribution[0]
            defect_type = str(top_defect.get("defect_type") or "").strip()
            if defect_type:
                suggestions.insert(0, f"围绕“{defect_type}”继续看，当前最该先排查什么？")

        part_ranking = statistics_context.get("part_quality_ranking")
        if isinstance(part_ranking, list) and part_ranking:
            top_part = part_ranking[0]
            part_name = str(top_part.get("part_name") or "").strip()
            if part_name:
                suggestions.append(f"{part_name} 这一类零件为什么会排到当前风险前列？")

        device_ranking = statistics_context.get("device_quality_ranking")
        if isinstance(device_ranking, list) and device_ranking:
            top_device = device_ranking[0]
            device_name = str(top_device.get("device_name") or "").strip()
            if device_name:
                suggestions.append(f"{device_name} 这台设备的异常更像采集问题还是实际质量问题？")

        return suggestions[:4]

    def _resolve_visual_source_url(self, *, file_object: dict[str, Any]) -> str | None:
        """解析文件对象可用于后端抓取字节流的来源地址。"""

        preview_url = str(file_object.get("preview_url") or "").strip()
        if preview_url.startswith(("http://", "https://")):
            return preview_url

        bucket_name = str(file_object.get("bucket_name") or "").strip()
        region = str(file_object.get("region") or "").strip()
        object_key = str(file_object.get("object_key") or "").strip()
        return self.cos_client.build_object_access_url(
            bucket_name=bucket_name,
            region=region,
            object_key=object_key,
        )

    def _fetch_image_asset(self, *, file_object: dict[str, Any]) -> dict[str, str] | None:
        """抓取单个图片对象并转成多协议可复用的图像结构。

        之所以在服务端统一拉取字节，而不是把前端 URL 原样交给不同供应商，
        是因为不同协议对图片字段的格式要求不同：
        - OpenAI Responses / OpenAI-compatible 优先使用供应商可访问的 HTTPS URL
        - Anthropic Messages 需要 `base64` 或 `url`
        - Gemini GenerateContent 需要 `inline_data`

        返回值同时保留 `image_url` 与 base64 形式：OpenAI 类协议走 URL，
        其他协议继续走 base64，避免把大体积 `data:` URL 塞进米醋 Responses
        中转请求体。
        """

        try:
            response_payload = self.cos_client.read_file_bytes(
                bucket_name=str(file_object.get("bucket_name") or "").strip(),
                region=str(file_object.get("region") or "").strip(),
                object_key=str(file_object.get("object_key") or "").strip(),
                timeout_seconds=self.timeout_seconds,
                max_bytes=self.max_image_bytes,
            )
            source_url = str(response_payload["access_url"])
            content_type = str(response_payload["content_type"])
            image_bytes = bytes(response_payload["data"])
        except IntegrationError as exc:
            logger.warning(
                "ai_review.image_fetch_failed object_key=%s url=%s error=%s",
                file_object.get("object_key"),
                self._resolve_visual_source_url(file_object=file_object),
                exc,
            )
            return None

        mime_type = content_type or mimetypes.guess_type(source_url)[0] or "application/octet-stream"
        if not mime_type.startswith("image/"):
            logger.warning(
                "ai_review.image_content_type_invalid object_key=%s mime_type=%s",
                file_object.get("object_key"),
                mime_type,
            )
            return None

        encoded_image = base64.b64encode(image_bytes).decode("utf-8")
        return {
            "mime_type": mime_type,
            "data_base64": encoded_image,
            "data_url": f"data:{mime_type};base64,{encoded_image}",
            "image_url": source_url,
            "object_key": str(file_object.get("object_key") or ""),
            "file_kind": str(file_object.get("file_kind") or ""),
        }

    def _load_image_assets(
        self,
        *,
        model_context: dict[str, Any],
        referenced_files: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        """根据模型能力与记录文件列表准备多模态图片输入。"""

        if not model_context.get("supports_vision"):
            return []

        image_assets: list[dict[str, str]] = []
        for file_object in referenced_files:
            image_asset = self._fetch_image_asset(file_object=file_object)
            if image_asset is not None:
                image_assets.append(image_asset)

        return image_assets

    def _should_load_images_for_chat_turn(
        self,
        *,
        model_context: dict[str, Any],
        question: str,
        normalized_history: list[dict[str, str]],
        previous_response_id: str | None,
    ) -> bool:
        """判断当前聊天轮次是否需要重新下载并发送图片字节。

        规则说明：
        - 该优化只针对生产问题链路：米醋 / OpenClaudeCode 的 OpenAI Responses。
          其他供应商继续沿用原行为，避免扩大协议兼容风险。
        - 第一轮没有历史时，需要把图片发给模型建立视觉判断基础。
        - 米醋 / OpenClaudeCode 不依赖供应商侧 `previous_response_id` 记忆；已有本地历史时，
          默认用压缩历史和图片读取位置承接，不重发图，避免后续追问每次都上传同一组图片。
        - 用户明确要求“重新看图 / 再看图片 / 按图片重新判断”时，重新附带图片。
        """

        if not self._should_use_openclaudecode_compact_prompt(model_context=model_context):
            return True
        if not normalized_history:
            return True
        if not any(item.get("role") == "user" for item in normalized_history):
            return True
        normalized_question = "".join(question.strip().lower().split())
        if not normalized_question:
            return False

        explicit_image_review_markers = [
            "重新看图",
            "再看图",
            "再看看图",
            "重新看图片",
            "再看图片",
            "按图片重新判断",
            "根据图片重新判断",
            "重新判断图片",
            "重新分析图片",
            "重新发图",
            "读取图片",
            "重新读取图片",
            "重新加载图片",
        ]
        return any(marker in normalized_question for marker in explicit_image_review_markers)

    def _should_retry_without_images(
        self,
        *,
        model_context: dict[str, Any],
        error: IntegrationError,
        image_assets: list[dict[str, str]],
    ) -> bool:
        """判断当前失败是否适合自动降级为纯文本重试。

        这里主要兜底“模型被误标成支持视觉，但供应商实际只接受纯文本”的场景。
        例如用户把 `deepseek-reasoner` 手动勾成视觉后，OpenAI-compatible 协议会因为
        `image_url` 消息块而返回反序列化错误。
        """

        if not image_assets:
            return False
        if str(model_context.get("protocol_type") or "") == "openai_responses":
            return False
        if error.code != "ai_provider_http_error":
            return False

        error_details = error.details or {}
        status_code = error_details.get("status_code")
        if status_code not in {400, 422}:
            return False

        normalized_response = str(error_details.get("response") or "").lower()
        if not normalized_response:
            return False

        image_rejection_markers = [
            "unknown variant `image_url`",
            "unknown variant \"image_url\"",
            "unknown variant `input_image`",
            "unknown variant \"input_image\"",
            "failed to deserialize",
            "does not support image",
            "does not support vision",
            "image input is not supported",
            "multimodal is not supported",
        ]
        has_image_payload_marker = any(
            marker in normalized_response for marker in ["image_url", "input_image", "inline_data"]
        )
        has_text_only_marker = any(
            marker in normalized_response for marker in ["expected `text`", "expected text", "text only", "text-only"]
        )

        if any(marker in normalized_response for marker in image_rejection_markers):
            return True

        # 这里保守兜底：只有同时出现“图像字段”与“文本期望”时才自动退回纯文本，避免误吞其他协议错误。
        return has_image_payload_marker and has_text_only_marker

    def _should_retry_openai_responses_without_images(
        self,
        *,
        model_context: dict[str, Any],
        error: IntegrationError,
        image_assets: list[dict[str, str]],
    ) -> bool:
        """判断 OpenAI Responses 带图失败时是否可同端点退回纯文本重试。

        该函数保留给统计或非视觉场景扩展，但当前记录质检问答不允许在带图请求失败后
        自动改成无图回答。否则用户问“这个是好的还是坏的”时，系统会在没有图像证据的
        情况下返回看似完整的结论，和现场要求冲突。
        """

        _ = model_context, error, image_assets
        return False

    def _log_image_retry_fallback(
        self,
        *,
        model_context: dict[str, Any],
        error: IntegrationError,
        task_mode: str,
        image_assets: list[dict[str, str]],
    ) -> None:
        """记录一次视觉失败后自动降级为纯文本的兜底日志。"""

        logger.warning(
            (
                "ai_review.image_retry_fallback event=ai_review.image_retry_fallback "
                "task_mode=%s protocol_type=%s gateway_vendor=%s model=%s status_code=%s image_count=%s"
            ),
            task_mode,
            model_context.get("protocol_type"),
            model_context.get("gateway_vendor"),
            model_context.get("model_identifier"),
            (error.details or {}).get("status_code"),
            len(image_assets),
        )

    def _log_responses_image_retry_fallback(
        self,
        *,
        model_context: dict[str, Any],
        error: IntegrationError,
        task_mode: str,
        image_assets: list[dict[str, str]],
    ) -> None:
        """记录 Responses 带图失败后同端点纯文本重试的降级日志。"""

        logger.warning(
            (
                "ai_review.responses_image_retry_fallback "
                "event=ai_review.responses_image_retry_fallback task_mode=%s gateway_vendor=%s "
                "model=%s status_code=%s image_count=%s"
            ),
            task_mode,
            model_context.get("gateway_vendor"),
            model_context.get("model_identifier"),
            (error.details or {}).get("status_code"),
            len(image_assets),
        )

    def _build_auth_headers(self, *, model_context: dict[str, Any]) -> dict[str, str]:
        """根据鉴权模式构造基础请求头。"""

        api_key = str(model_context.get("api_key") or "").strip()
        if not api_key:
            raise BadRequestError(code="ai_api_key_missing", message="当前 AI 网关未配置可用 API Key。")

        auth_mode = str(model_context.get("auth_mode") or "").strip()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if auth_mode in {"authorization_bearer", "both"}:
            headers["Authorization"] = f"Bearer {api_key}"
        if auth_mode in {"x_api_key", "both"}:
            headers["x-api-key"] = api_key
        if user_agent := str(model_context.get("user_agent") or "").strip():
            headers["User-Agent"] = user_agent

        return headers

    def _append_query_api_key(self, *, url: str, model_context: dict[str, Any]) -> str:
        """在需要时把 API Key 追加到查询字符串中。"""

        if str(model_context.get("auth_mode") or "") != "query_api_key":
            return url

        api_key = str(model_context.get("api_key") or "").strip()
        if not api_key:
            raise BadRequestError(code="ai_api_key_missing", message="当前 AI 网关未配置可用 API Key。")

        parsed_url = urlparse(url)
        existing_query = parsed_url.query
        next_query = urlencode({"key": api_key})
        merged_query = f"{existing_query}&{next_query}" if existing_query else next_query
        return urlunparse(parsed_url._replace(query=merged_query))

    def _build_openai_responses_request(
        self,
        *,
        model_context: dict[str, Any],
        system_instruction: str,
        history: list[dict[str, str]],
        user_prompt: str,
        image_assets: list[dict[str, str]],
        previous_response_id: str | None = None,
        stream: bool = False,
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        """构造 OpenAI Responses 协议请求。"""

        base_url = str(model_context["base_url"]).rstrip("/")
        endpoint_url = self._append_query_api_key(
            url=f"{base_url}/responses",
            model_context=model_context,
        )
        headers = self._build_auth_headers(model_context=model_context)
        should_send_previous_response_id = self._should_send_responses_previous_response_id(
            model_context=model_context,
            previous_response_id=previous_response_id,
            stream=stream,
        )

        # 米醋 / OpenClaudeCode 的上下文已经被压缩进本轮 user prompt。这里不能再把
        # 历史拆成多个 Responses input 项，否则生产第二轮追问会在网关侧返回 502。
        # 该保护放在协议请求构造层，确保流式 metadata、非流式聊天等入口行为一致。
        history_for_input = [] if self._is_openclaudecode_gateway(model_context=model_context) else history
        input_items: list[dict[str, Any]] = [
            {
                "role": item["role"],
                "content": [{"type": "input_text", "text": item["content"]}],
            }
            for item in history_for_input
        ]
        if should_send_previous_response_id:
            input_items = []

        user_content: list[dict[str, Any]] = [{"type": "input_text", "text": user_prompt}]
        user_content.extend(
            {"type": "input_image", "image_url": item.get("image_url") or item["data_url"]}
            for item in image_assets
        )
        input_items.append({"role": "user", "content": user_content})

        payload = {
            "model": model_context["model_identifier"],
            "instructions": system_instruction,
            "input": input_items,
            "temperature": 0.2,
            "store": True,
            "stream": stream,
        }
        if should_send_previous_response_id:
            payload["previous_response_id"] = previous_response_id
        return endpoint_url, headers, payload

    def _should_send_responses_previous_response_id(
        self,
        *,
        model_context: dict[str, Any],
        previous_response_id: str | None,
        stream: bool,
    ) -> bool:
        """判断当前 Responses 请求是否可以发送 `previous_response_id`。

        生产实测米醋 / OpenClaudeCode 的 HTTP 流式 Responses 会返回
        `previous_response_id is only supported on Responses WebSocket v2`；而实测
        `wss://www.micuapi.ai/v1/responses` 握手返回 404。这里按 Codex / opencode
        的本地会话策略处理：OpenClaudeCode 不依赖供应商侧 response 存储，
        统一通过压缩历史承接上下文。
        """

        if not previous_response_id:
            return False
        if self._is_openclaudecode_gateway(model_context=model_context):
            return False
        return True

    def _is_openclaudecode_gateway(self, *, model_context: dict[str, Any]) -> bool:
        """判断当前运行时模型是否来自 OpenClaudeCode / 米醋网关。"""

        gateway_vendor = str(model_context.get("gateway_vendor") or "").strip().lower()
        gateway_name = str(model_context.get("gateway_name") or "").strip().lower()
        return gateway_vendor == "openclaudecode" or "openclaudecode" in gateway_name

    def _build_openai_compatible_request(
        self,
        *,
        model_context: dict[str, Any],
        system_instruction: str,
        history: list[dict[str, str]],
        user_prompt: str,
        image_assets: list[dict[str, str]],
        stream: bool = False,
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        """构造 OpenAI-compatible Chat Completions 协议请求。"""

        base_url = str(model_context["base_url"]).rstrip("/")
        endpoint_url = self._append_query_api_key(
            url=f"{base_url}/chat/completions",
            model_context=model_context,
        )
        headers = self._build_auth_headers(model_context=model_context)

        messages: list[dict[str, Any]] = [{"role": "system", "content": system_instruction}]
        messages.extend(
            {"role": item["role"], "content": item["content"]}
            for item in history
        )

        user_content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
        user_content.extend(
            {
                "type": "image_url",
                "image_url": {
                    "url": item.get("image_url") or item["data_url"],
                },
            }
            for item in image_assets
        )
        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": model_context["model_identifier"],
            "messages": messages,
            "temperature": 0.2,
            "stream": stream,
        }
        return endpoint_url, headers, payload

    def _build_anthropic_messages_request(
        self,
        *,
        model_context: dict[str, Any],
        system_instruction: str,
        history: list[dict[str, str]],
        user_prompt: str,
        image_assets: list[dict[str, str]],
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        """构造 Anthropic Messages 协议请求。"""

        base_url = str(model_context["base_url"]).rstrip("/")
        endpoint_url = self._append_query_api_key(
            url=f"{base_url}/v1/messages",
            model_context=model_context,
        )
        headers = self._build_auth_headers(model_context=model_context)
        headers["anthropic-version"] = "2023-06-01"

        messages: list[dict[str, Any]] = [
            {"role": item["role"], "content": item["content"]}
            for item in history
        ]

        user_content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
        user_content.extend(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": item["mime_type"],
                    "data": item["data_base64"],
                },
            }
            for item in image_assets
        )
        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": model_context["model_identifier"],
            "system": system_instruction,
            "max_tokens": 1200,
            "messages": messages,
        }
        return endpoint_url, headers, payload

    def _build_gemini_generate_content_request(
        self,
        *,
        model_context: dict[str, Any],
        system_instruction: str,
        history: list[dict[str, str]],
        user_prompt: str,
        image_assets: list[dict[str, str]],
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        """构造 Gemini GenerateContent 协议请求。"""

        base_url = str(model_context["base_url"]).rstrip("/")
        endpoint_url = self._append_query_api_key(
            url=f"{base_url}/models/{model_context['model_identifier']}:generateContent",
            model_context=model_context,
        )
        headers = self._build_auth_headers(model_context=model_context)

        contents: list[dict[str, Any]] = [
            {
                "role": "model" if item["role"] == "assistant" else "user",
                "parts": [{"text": item["content"]}],
            }
            for item in history
        ]

        user_parts: list[dict[str, Any]] = [{"text": user_prompt}]
        user_parts.extend(
            {
                "inline_data": {
                    "mime_type": item["mime_type"],
                    "data": item["data_base64"],
                }
            }
            for item in image_assets
        )
        contents.append({"role": "user", "parts": user_parts})

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_instruction}],
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
            },
        }
        return endpoint_url, headers, payload

    def _post_json(self, *, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        """发送 JSON POST 请求并统一处理供应商错误响应。"""

        serialized_payload = json.dumps(payload, ensure_ascii=False)
        input_image_count = serialized_payload.count('"input_image"') + serialized_payload.count("'input_image'")
        logger.info(
            (
                "ai_review.provider_request event=ai_review.provider_request endpoint=%s "
                "model=%s input_image_count=%s payload_bytes=%s user_agent=%s"
            ),
            url,
            payload.get("model"),
            input_image_count,
            len(serialized_payload.encode("utf-8")),
            headers.get("User-Agent") or "",
        )

        request = Request(
            url,
            data=serialized_payload.encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_text = response.read().decode("utf-8")
        except HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            raise IntegrationError(
                code="ai_provider_http_error",
                message=f"AI 供应商调用失败，HTTP {exc.code}。",
                details={
                    "status_code": exc.code,
                    "endpoint": url,
                    "response": response_body[:800],
                },
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise IntegrationError(
                code="ai_provider_network_error",
                message="AI 供应商网络请求失败，请检查网关地址、网络和供应商状态。",
                details={
                    "endpoint": url,
                    "reason": str(exc),
                },
            ) from exc

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise IntegrationError(
                code="ai_provider_invalid_json",
                message="AI 供应商返回了无法解析的响应内容。",
                details={
                    "endpoint": url,
                    "response": response_text[:800],
                },
            ) from exc

    def _post_stream_events(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> Iterator[tuple[str | None, dict[str, Any]]]:
        """发送流式请求并逐个产出 SSE 事件载荷。

        兼容两种情况：
        1. 供应商按规范返回 `text/event-stream`
        2. 某些兼容网关虽然收到 `stream=true`，仍直接回完整 JSON
        """

        serialized_payload = json.dumps(payload, ensure_ascii=False)
        input_image_count = serialized_payload.count('"input_image"') + serialized_payload.count("'input_image'")
        logger.info(
            (
                "ai_review.provider_stream_request event=ai_review.provider_stream_request endpoint=%s "
                "model=%s input_image_count=%s payload_bytes=%s user_agent=%s"
            ),
            url,
            payload.get("model"),
            input_image_count,
            len(serialized_payload.encode("utf-8")),
            headers.get("User-Agent") or "",
        )

        request = Request(
            url,
            data=serialized_payload.encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                content_type = response.headers.get("Content-Type", "")
                if "text/event-stream" not in content_type:
                    response_text = response.read().decode("utf-8")
                    try:
                        yield "__json__", json.loads(response_text)
                    except json.JSONDecodeError as exc:
                        raise IntegrationError(
                            code="ai_provider_invalid_json",
                            message="AI 供应商返回了无法解析的流式响应内容。",
                            details={
                                "endpoint": url,
                                "response": response_text[:800],
                            },
                        ) from exc
                    return

                current_event_name: str | None = None
                current_data_lines: list[str] = []

                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")

                    if not line:
                        if current_data_lines:
                            data_text = "\n".join(current_data_lines).strip()
                            current_data_lines = []
                            event_name = current_event_name
                            current_event_name = None

                            if not data_text:
                                continue
                            if data_text == "[DONE]":
                                return

                            try:
                                yield event_name, json.loads(data_text)
                            except json.JSONDecodeError as exc:
                                raise IntegrationError(
                                    code="ai_provider_invalid_json",
                                    message="AI 供应商返回了无法解析的流式事件数据。",
                                    details={
                                        "endpoint": url,
                                        "response": data_text[:800],
                                        "event_name": event_name,
                                    },
                                ) from exc
                        continue

                    if line.startswith(":"):
                        continue
                    if line.startswith("event:"):
                        current_event_name = line[6:].strip() or None
                        continue
                    if line.startswith("data:"):
                        current_data_lines.append(line[5:].lstrip())
                        continue
        except HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            raise IntegrationError(
                code="ai_provider_http_error",
                message=f"AI 供应商流式调用失败，HTTP {exc.code}。",
                details={
                    "status_code": exc.code,
                    "endpoint": url,
                    "response": response_body[:800],
                },
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise IntegrationError(
                code="ai_provider_network_error",
                message="AI 供应商流式网络请求失败，请检查网关地址、网络和供应商状态。",
                details={
                    "endpoint": url,
                    "reason": str(exc),
                },
            ) from exc

    def _iter_text_chunks(self, *, text: str, chunk_char_limit: int = 48) -> Iterator[str]:
        """把一次性文本切成较短片段，供前端伪流式展示。"""

        normalized_text = text.strip()
        if not normalized_text:
            return

        buffer = ""
        for character in normalized_text:
            buffer += character
            if len(buffer) >= chunk_char_limit or character in {"\n", "。", "！", "？", "；", "："}:
                yield buffer
                buffer = ""

        if buffer:
            yield buffer

    def _raise_stream_event_error(
        self,
        *,
        event_name: str | None,
        event_data: dict[str, Any],
        endpoint_url: str,
    ) -> None:
        """把上游流式事件里的错误块转换成统一的集成错误。"""

        if event_name != "error" and event_data.get("type") != "error":
            return

        error_payload = event_data.get("error")
        normalized_error = error_payload if isinstance(error_payload, dict) else event_data
        error_message = str(normalized_error.get("message") or "AI 供应商返回了流式错误事件。")
        raise IntegrationError(
            code=str(normalized_error.get("code") or "ai_provider_stream_error"),
            message=error_message,
            details={
                "endpoint": endpoint_url,
                "response": json.dumps(event_data, ensure_ascii=False)[:800],
            },
        )

    def _extract_openai_responses_text(self, *, response_data: dict[str, Any]) -> str:
        """从 OpenAI Responses 风格响应中提取最终文本。"""

        output_texts: list[str] = []
        for item in response_data.get("output", []) or []:
            if item.get("type") != "message" or item.get("role") != "assistant":
                continue
            for content_item in item.get("content", []) or []:
                text = content_item.get("text")
                if content_item.get("type") == "output_text" and isinstance(text, str) and text.strip():
                    output_texts.append(text.strip())

        if not output_texts and isinstance(response_data.get("output_text"), str):
            text_value = response_data["output_text"].strip()
            if text_value:
                output_texts.append(text_value)

        if not output_texts:
            raise IntegrationError(
                code="ai_provider_empty_answer",
                message="AI 供应商未返回可用文本结果。",
            )

        return "\n".join(output_texts)

    def _extract_provider_response_id(self, *, response_data: dict[str, Any]) -> str | None:
        """从 Responses 响应中提取可用于下一轮承接的响应 ID。"""

        response_id = response_data.get("id")
        if isinstance(response_id, str) and response_id.strip():
            return response_id.strip()
        return None

    def _extract_openai_compatible_text(self, *, response_data: dict[str, Any]) -> str:
        """从 OpenAI-compatible Chat Completions 响应中提取文本。"""

        choices = response_data.get("choices") or []
        if not choices:
            raise IntegrationError(code="ai_provider_empty_answer", message="AI 供应商未返回候选答案。")

        content = ((choices[0] or {}).get("message") or {}).get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()

        if isinstance(content, list):
            text_chunks = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        text_chunks.append(text.strip())
            if text_chunks:
                return "\n".join(text_chunks)

        raise IntegrationError(code="ai_provider_empty_answer", message="AI 供应商未返回可读文本内容。")

    def _extract_openai_responses_stream_delta(self, *, event_data: dict[str, Any]) -> str:
        """从 OpenAI Responses 流式事件中提取本轮新增文本。"""

        event_type = str(event_data.get("type") or "")
        if event_type == "response.output_text.delta":
            delta_text = event_data.get("delta")
            return delta_text if isinstance(delta_text, str) else ""

        return ""

    def _extract_openai_compatible_stream_delta(self, *, response_data: dict[str, Any]) -> str:
        """从 Chat Completions 流式事件中提取本轮新增文本。"""

        text_chunks: list[str] = []

        for choice in response_data.get("choices") or []:
            if not isinstance(choice, dict):
                continue

            delta = choice.get("delta")
            if not isinstance(delta, dict):
                continue

            content = delta.get("content")
            if isinstance(content, str):
                text_chunks.append(content)
                continue

            if not isinstance(content, list):
                continue

            for item in content:
                if not isinstance(item, dict):
                    continue

                item_text = item.get("text")
                if isinstance(item_text, str):
                    text_chunks.append(item_text)
                    continue

                if item.get("type") in {"text", "output_text"}:
                    delta_text = item.get("delta")
                    if isinstance(delta_text, str):
                        text_chunks.append(delta_text)

        return "".join(text_chunks)

    def _extract_anthropic_text(self, *, response_data: dict[str, Any]) -> str:
        """从 Anthropic Messages 响应中提取文本。"""

        text_chunks = []
        for item in response_data.get("content", []) or []:
            if item.get("type") == "text" and isinstance(item.get("text"), str) and item["text"].strip():
                text_chunks.append(item["text"].strip())

        if not text_chunks:
            raise IntegrationError(code="ai_provider_empty_answer", message="Claude 未返回可读文本内容。")

        return "\n".join(text_chunks)

    def _extract_anthropic_stream_text_piece(self, *, event_data: dict[str, Any]) -> str:
        """从 Anthropic SSE 事件里提取当前这一个文本片段。

        OpenClaudeCode 下的部分 Messages 兼容模型即使没有显式开启 `stream=true`，
        也会直接返回 `text/event-stream`。这里统一兼容两类事件：
        1. `content_block_start` 里已经带了首段文本
        2. `content_block_delta` 通过 `delta.text` 逐段追加文本
        """

        event_type = str(event_data.get("type") or "")

        if event_type == "content_block_start":
            content_block = event_data.get("content_block")
            if isinstance(content_block, dict) and content_block.get("type") == "text":
                start_text = content_block.get("text")
                if isinstance(start_text, str):
                    return start_text

        if event_type == "content_block_delta":
            delta = event_data.get("delta")
            if isinstance(delta, dict):
                delta_text = delta.get("text")
                if isinstance(delta_text, str):
                    return delta_text

        return ""

    def _request_anthropic_messages_text(
        self,
        *,
        model_context: dict[str, Any],
        system_instruction: str,
        history: list[dict[str, str]],
        user_prompt: str,
        image_assets: list[dict[str, str]],
    ) -> str:
        """兼容 JSON 与 SSE 两种返回形态，获取 Anthropic Messages 文本结果。

        这样做的原因是：
        - Claude 官方通常会返回普通 JSON
        - OpenClaudeCode 下某些 Grok 模型会直接返回 SSE
        - 这两种都属于 `anthropic_messages` 协议，调用方不应该再各自分支
        """

        endpoint_url, headers, payload = self._build_anthropic_messages_request(
            model_context=model_context,
            system_instruction=system_instruction,
            history=history,
            user_prompt=user_prompt,
            image_assets=image_assets,
        )

        text_chunks: list[str] = []
        for event_name, event_data in self._post_stream_events(
            url=endpoint_url,
            headers=headers,
            payload=payload,
        ):
            if event_name == "__json__":
                return self._extract_anthropic_text(response_data=event_data)

            self._raise_stream_event_error(
                event_name=event_name,
                event_data=event_data,
                endpoint_url=endpoint_url,
            )

            text_piece = self._extract_anthropic_stream_text_piece(event_data=event_data)
            if text_piece:
                text_chunks.append(text_piece)

        answer_text = "".join(text_chunks).strip()
        if not answer_text:
            raise IntegrationError(
                code="ai_provider_empty_answer",
                message="Anthropic Messages 未返回可读文本内容。",
            )

        return answer_text

    def _extract_gemini_text(self, *, response_data: dict[str, Any]) -> str:
        """从 Gemini GenerateContent 响应中提取文本。"""

        candidates = response_data.get("candidates") or []
        if not candidates:
            raise IntegrationError(code="ai_provider_empty_answer", message="Gemini 未返回候选答案。")

        content = ((candidates[0] or {}).get("content") or {}).get("parts") or []
        text_chunks = []
        for item in content:
            text = item.get("text") if isinstance(item, dict) else None
            if isinstance(text, str) and text.strip():
                text_chunks.append(text.strip())

        if not text_chunks:
            raise IntegrationError(code="ai_provider_empty_answer", message="Gemini 未返回可读文本内容。")

        return "\n".join(text_chunks)

    def _request_openai_responses_text(
        self,
        *,
        model_context: dict[str, Any],
        system_instruction: str,
        history: list[dict[str, str]],
        user_prompt: str,
        image_assets: list[dict[str, str]],
        previous_response_id: str | None = None,
    ) -> AICompletionResult:
        """按当前模型选中的 OpenAI Responses 协议请求文本。

        这里故意不再做 `/chat/completions` 自动回退。设置页里的协议就是运行时契约：
        用户选中 `openai_responses` 时，请求日志必须只出现 `/responses`，否则线上排查
        会看到与配置不一致的路径。
        """

        endpoint_url, headers, payload = self._build_openai_responses_request(
            model_context=model_context,
            system_instruction=system_instruction,
            history=history,
            user_prompt=user_prompt,
            image_assets=image_assets,
            previous_response_id=previous_response_id,
        )

        response_data = self._post_json(url=endpoint_url, headers=headers, payload=payload)
        return AICompletionResult(
            text=self._extract_openai_responses_text(response_data=response_data),
            provider_response_id=self._extract_provider_response_id(response_data=response_data),
        )

    def _stream_openai_compatible_text(
        self,
        *,
        model_context: dict[str, Any],
        system_instruction: str,
        history: list[dict[str, str]],
        user_prompt: str,
        image_assets: list[dict[str, str]],
        previous_response_id: str | None = None,
    ) -> Iterator[str]:
        """按 Chat Completions 协议向前端逐片段产出文本。"""

        endpoint_url, headers, payload = self._build_openai_compatible_request(
            model_context=model_context,
            system_instruction=system_instruction,
            history=history,
            user_prompt=user_prompt,
            image_assets=image_assets,
            stream=True,
        )

        has_emitted_text = False
        for event_name, event_data in self._post_stream_events(
            url=endpoint_url,
            headers=headers,
            payload=payload,
        ):
            if event_name == "__json__":
                answer_text = self._extract_openai_compatible_text(response_data=event_data)
                yield from self._iter_text_chunks(text=answer_text)
                return

            self._raise_stream_event_error(
                event_name=event_name,
                event_data=event_data,
                endpoint_url=endpoint_url,
            )
            delta_text = self._extract_openai_compatible_stream_delta(response_data=event_data)
            if delta_text:
                has_emitted_text = True
                yield delta_text

        if not has_emitted_text:
            raise IntegrationError(
                code="ai_provider_empty_answer",
                message="AI 供应商未返回可流式输出的文本内容。",
            )

    def _stream_openai_responses_text(
        self,
        *,
        model_context: dict[str, Any],
        system_instruction: str,
        history: list[dict[str, str]],
        user_prompt: str,
        image_assets: list[dict[str, str]],
        previous_response_id: str | None = None,
    ) -> Iterator[str]:
        """按当前模型选中的 OpenAI Responses 协议流式输出文本。

        流式分支同样严格尊重模型协议配置。`openai_responses` 失败时把供应商错误
        交给上层 SSE 错误边界处理，不隐式改发 `/chat/completions`。
        """

        endpoint_url, headers, payload = self._build_openai_responses_request(
            model_context=model_context,
            system_instruction=system_instruction,
            history=history,
            user_prompt=user_prompt,
            image_assets=image_assets,
            previous_response_id=previous_response_id,
            stream=True,
        )

        has_emitted_text = False
        for event_name, event_data in self._post_stream_events(
            url=endpoint_url,
            headers=headers,
            payload=payload,
        ):
            if event_name == "__json__":
                answer_text = self._extract_openai_responses_text(response_data=event_data)
                yield from self._iter_text_chunks(text=answer_text)
                return

            self._raise_stream_event_error(
                event_name=event_name,
                event_data=event_data,
                endpoint_url=endpoint_url,
            )

            delta_text = self._extract_openai_responses_stream_delta(event_data=event_data)
            if delta_text:
                has_emitted_text = True
                yield delta_text
                continue

            if not has_emitted_text and str(event_data.get("type") or "") == "response.output_text.done":
                done_text = event_data.get("text")
                if isinstance(done_text, str) and done_text.strip():
                    yield from self._iter_text_chunks(text=done_text)
                    return

            if not has_emitted_text and str(event_data.get("type") or "") == "response.completed":
                response_payload = event_data.get("response")
                if isinstance(response_payload, dict):
                    answer_text = self._extract_openai_responses_text(response_data=response_payload)
                    yield from self._iter_text_chunks(text=answer_text)
                    return

        if not has_emitted_text:
            raise IntegrationError(
                code="ai_provider_empty_answer",
                message="AI 供应商未返回可流式输出的文本内容。",
            )

    def request_openai_responses_stream_metadata(
        self,
        *,
        model_context: dict[str, Any],
        system_instruction: str,
        history: list[dict[str, str]],
        user_prompt: str,
        image_assets: list[dict[str, str]],
        previous_response_id: str | None = None,
    ) -> Iterator[dict[str, str | None]]:
        """按 Responses 流式请求产出文本片段和最终响应 ID。

        记录页 AI 对话需要在 `done` 事件里把供应商响应 ID 返回给前端，便于调试追踪。
        这里必须保持上游 `stream=True`，否则浏览器虽然收到 SSE，却会等供应商整段回答
        完成后才看到后端切片。米醋 / OpenClaudeCode 的 HTTP Responses 不使用该 ID 承接
        上下文；实际上下文由前端传入历史和后端压缩摘要承接，和 CLI / opencode 的本地会话
        策略一致。
        """

        endpoint_url, headers, payload = self._build_openai_responses_request(
            model_context=model_context,
            system_instruction=system_instruction,
            history=history,
            user_prompt=user_prompt,
            image_assets=image_assets,
            previous_response_id=previous_response_id,
            stream=True,
        )

        has_emitted_text = False
        for event_name, event_data in self._post_stream_events(
            url=endpoint_url,
            headers=headers,
            payload=payload,
        ):
            if event_name == "__json__":
                yield {
                    "type": "metadata",
                    "provider_response_id": self._extract_provider_response_id(response_data=event_data),
                }
                answer_text = self._extract_openai_responses_text(response_data=event_data)
                for text_chunk in self._iter_text_chunks(text=answer_text):
                    yield {"type": "delta", "text": text_chunk}
                return

            self._raise_stream_event_error(
                event_name=event_name,
                event_data=event_data,
                endpoint_url=endpoint_url,
            )

            if str(event_data.get("type") or "") == "response.completed":
                response_payload = event_data.get("response")
                if isinstance(response_payload, dict):
                    yield {
                        "type": "metadata",
                        "provider_response_id": self._extract_provider_response_id(response_data=response_payload),
                    }
                    if not has_emitted_text:
                        answer_text = self._extract_openai_responses_text(response_data=response_payload)
                        for text_chunk in self._iter_text_chunks(text=answer_text):
                            yield {"type": "delta", "text": text_chunk}
                    return

            delta_text = self._extract_openai_responses_stream_delta(event_data=event_data)
            if delta_text:
                has_emitted_text = True
                yield {"type": "delta", "text": delta_text}
                continue

            if not has_emitted_text and str(event_data.get("type") or "") == "response.output_text.done":
                done_text = event_data.get("text")
                if isinstance(done_text, str) and done_text.strip():
                    for text_chunk in self._iter_text_chunks(text=done_text):
                        yield {"type": "delta", "text": text_chunk}
                    has_emitted_text = True

        if not has_emitted_text:
            raise IntegrationError(
                code="ai_provider_empty_answer",
                message="AI 供应商未返回可流式输出的文本内容。",
            )

    def _stream_anthropic_messages_text(
        self,
        *,
        model_context: dict[str, Any],
        system_instruction: str,
        history: list[dict[str, str]],
        user_prompt: str,
        image_assets: list[dict[str, str]],
        previous_response_id: str | None = None,
    ) -> Iterator[str]:
        """按 Anthropic Messages 协议直接转发 SSE 文本增量。

        如果上游仍返回普通 JSON，则退回后端切片输出，保持前端消费方式一致。
        """

        endpoint_url, headers, payload = self._build_anthropic_messages_request(
            model_context=model_context,
            system_instruction=system_instruction,
            history=history,
            user_prompt=user_prompt,
            image_assets=image_assets,
        )

        has_emitted_text = False
        for event_name, event_data in self._post_stream_events(
            url=endpoint_url,
            headers=headers,
            payload=payload,
        ):
            if event_name == "__json__":
                answer_text = self._extract_anthropic_text(response_data=event_data)
                yield from self._iter_text_chunks(text=answer_text)
                return

            self._raise_stream_event_error(
                event_name=event_name,
                event_data=event_data,
                endpoint_url=endpoint_url,
            )

            text_piece = self._extract_anthropic_stream_text_piece(event_data=event_data)
            if text_piece:
                has_emitted_text = True
                yield text_piece

        if not has_emitted_text:
            raise IntegrationError(
                code="ai_provider_empty_answer",
                message="Anthropic Messages 未返回可流式输出的文本内容。",
            )

    def _stream_protocol_text(
        self,
        *,
        model_context: dict[str, Any],
        system_instruction: str,
        history: list[dict[str, str]],
        user_prompt: str,
        image_assets: list[dict[str, str]],
        previous_response_id: str | None = None,
    ) -> Iterator[str]:
        """按协议类型产出文本增量。

        只有确认可用的流式协议走真实上游流式，其余协议统一退回“后端切片输出”，
        这样单条记录对话和统计分析都能在前端保持一致的流式体验。
        """

        protocol_type = str(model_context.get("protocol_type") or "")
        supports_stream = bool(model_context.get("supports_stream"))

        if supports_stream and protocol_type == "openai_responses":
            yield from self._stream_openai_responses_text(
                model_context=model_context,
                system_instruction=system_instruction,
                history=history,
                user_prompt=user_prompt,
                image_assets=image_assets,
                previous_response_id=previous_response_id,
            )
            return

        if supports_stream and protocol_type == "openai_compatible":
            yield from self._stream_openai_compatible_text(
                model_context=model_context,
                system_instruction=system_instruction,
                history=history,
                user_prompt=user_prompt,
                image_assets=image_assets,
            )
            return

        if supports_stream and protocol_type == "anthropic_messages":
            yield from self._stream_anthropic_messages_text(
                model_context=model_context,
                system_instruction=system_instruction,
                history=history,
                user_prompt=user_prompt,
                image_assets=image_assets,
            )
            return

        answer_text = self._request_protocol_text(
            model_context=model_context,
            system_instruction=system_instruction,
            history=history,
            user_prompt=user_prompt,
            image_assets=image_assets,
            previous_response_id=previous_response_id,
        )
        yield from self._iter_text_chunks(text=answer_text.text)

    def _request_protocol_text(
        self,
        *,
        model_context: dict[str, Any],
        system_instruction: str,
        history: list[dict[str, str]],
        user_prompt: str,
        image_assets: list[dict[str, str]],
        previous_response_id: str | None = None,
    ) -> AICompletionResult:
        """按当前模型协议发起一次文本补全请求。

        这里把“协议分支选择”集中到一个方法里，避免单条记录对话、AI 复核、
        统计分析分别复制一份 OpenAI / Claude / Gemini 的分发逻辑。
        """

        protocol_type = str(model_context.get("protocol_type") or "")

        if protocol_type == "openai_responses":
            return self._request_openai_responses_text(
                model_context=model_context,
                system_instruction=system_instruction,
                history=history,
                user_prompt=user_prompt,
                image_assets=image_assets,
                previous_response_id=previous_response_id,
            )

        if protocol_type == "openai_compatible":
            endpoint_url, headers, payload = self._build_openai_compatible_request(
                model_context=model_context,
                system_instruction=system_instruction,
                history=history,
                user_prompt=user_prompt,
                image_assets=image_assets,
            )
            response_data = self._post_json(url=endpoint_url, headers=headers, payload=payload)
            return AICompletionResult(text=self._extract_openai_compatible_text(response_data=response_data))

        if protocol_type == "anthropic_messages":
            return AICompletionResult(
                text=self._request_anthropic_messages_text(
                    model_context=model_context,
                    system_instruction=system_instruction,
                    history=history,
                    user_prompt=user_prompt,
                    image_assets=image_assets,
                )
            )

        if protocol_type == "gemini_generate_content":
            endpoint_url, headers, payload = self._build_gemini_generate_content_request(
                model_context=model_context,
                system_instruction=system_instruction,
                history=history,
                user_prompt=user_prompt,
                image_assets=image_assets,
            )
            response_data = self._post_json(url=endpoint_url, headers=headers, payload=payload)
            return AICompletionResult(text=self._extract_gemini_text(response_data=response_data))

        raise BadRequestError(
            code="ai_protocol_unsupported",
            message=f"当前模型协议 {protocol_type or 'unknown'} 暂未支持。",
        )

    def _request_model_completion(
        self,
        *,
        model_context: dict[str, Any],
        question: str,
        history: list[dict[str, str]],
        context: dict[str, Any],
        referenced_files: list[dict[str, Any]],
        previous_response_id: str | None = None,
    ) -> AICompletionResult:
        """根据协议类型发起真实模型调用并返回答案文本。"""

        normalized_history = self._normalize_history(
            history=history,
            current_question=question,
        )
        should_load_images = self._should_load_images_for_chat_turn(
            model_context=model_context,
            question=question,
            normalized_history=normalized_history,
            previous_response_id=previous_response_id,
        )
        image_assets = (
            self._load_image_assets(
                model_context=model_context,
                referenced_files=referenced_files,
            )
            if should_load_images
            else []
        )
        use_compact_vision_prompt = self._should_use_openclaudecode_compact_prompt(
            model_context=model_context,
        )
        if use_compact_vision_prompt:
            history_context_block = self._build_compact_history_context_block(
                history=normalized_history,
                question=question,
            )
            request_history = self._build_provider_history_for_compact_prompt(
                model_context=model_context,
                history=normalized_history,
            )
            system_instruction = self._build_compact_system_instruction(
                model_context=model_context,
                has_loaded_images=bool(image_assets),
                task_mode="chat",
            )
            user_prompt = self._build_compact_chat_user_prompt(
                question=question,
                context=context,
                referenced_files=referenced_files,
                image_assets=image_assets,
                history_context_block=history_context_block,
            )
        else:
            request_history = normalized_history
            system_instruction = self._build_system_instruction(
                model_context=model_context,
                has_loaded_images=bool(image_assets),
                task_mode="chat",
            )
            user_prompt = self._build_chat_user_prompt(
                question=question,
                context=context,
                referenced_files=referenced_files,
                image_assets=image_assets,
            )
            history_context_block = self._build_history_context_block(
                history=normalized_history,
                question=question,
            )
            user_prompt = self._append_history_context_to_prompt(
                user_prompt=user_prompt,
                history_context_block=history_context_block,
            )
        try:
            return self._request_protocol_text(
                model_context=model_context,
                system_instruction=system_instruction,
                history=request_history,
                user_prompt=user_prompt,
                image_assets=image_assets,
                previous_response_id=previous_response_id,
            )
        except IntegrationError as exc:
            if self._should_retry_openai_responses_without_images(
                model_context=model_context,
                error=exc,
                image_assets=image_assets,
            ):
                self._log_responses_image_retry_fallback(
                    model_context=model_context,
                    error=exc,
                    task_mode="chat",
                    image_assets=image_assets,
                )
                if use_compact_vision_prompt:
                    fallback_system_instruction = self._build_compact_system_instruction(
                        model_context=model_context,
                        has_loaded_images=False,
                        task_mode="chat",
                    )
                    fallback_user_prompt = self._build_compact_no_image_chat_user_prompt(
                        question=question,
                        context=context,
                        referenced_files=referenced_files,
                        history_context_block=history_context_block,
                    )
                else:
                    fallback_system_instruction = self._build_system_instruction(
                        model_context=model_context,
                        has_loaded_images=False,
                        task_mode="chat",
                    )
                    fallback_user_prompt = self._build_chat_user_prompt(
                        question=question,
                        context=context,
                        referenced_files=referenced_files,
                        image_assets=[],
                    )
                    fallback_user_prompt = self._append_history_context_to_prompt(
                        user_prompt=fallback_user_prompt,
                        history_context_block=history_context_block,
                    )
                return self._request_protocol_text(
                    model_context=model_context,
                    system_instruction=fallback_system_instruction,
                    history=request_history,
                    user_prompt=fallback_user_prompt,
                    image_assets=[],
                    previous_response_id=previous_response_id,
                )

            if not self._should_retry_without_images(
                model_context=model_context,
                error=exc,
                image_assets=image_assets,
            ):
                raise

            self._log_image_retry_fallback(
                model_context=model_context,
                error=exc,
                task_mode="chat",
                image_assets=image_assets,
            )
            fallback_system_instruction = self._build_system_instruction(
                model_context=model_context,
                has_loaded_images=False,
                task_mode="chat",
            )
            fallback_user_prompt = self._build_chat_user_prompt(
                question=question,
                context=context,
                referenced_files=referenced_files,
                image_assets=[],
            )
            fallback_user_prompt = self._append_history_context_to_prompt(
                user_prompt=fallback_user_prompt,
                history_context_block=history_context_block,
            )
            return self._request_protocol_text(
                model_context=model_context,
                system_instruction=fallback_system_instruction,
                history=request_history,
                user_prompt=fallback_user_prompt,
                image_assets=[],
                previous_response_id=previous_response_id,
            )

    def _stream_model_completion(
        self,
        *,
        model_context: dict[str, Any],
        question: str,
        history: list[dict[str, str]],
        context: dict[str, Any],
        referenced_files: list[dict[str, Any]],
        previous_response_id: str | None = None,
        metadata_callback: Callable[[str | None], None] | None = None,
    ) -> Iterator[str]:
        """根据协议类型发起真实模型调用，并逐片段产出答案文本。"""

        normalized_history = self._normalize_history(
            history=history,
            current_question=question,
        )
        should_load_images = self._should_load_images_for_chat_turn(
            model_context=model_context,
            question=question,
            normalized_history=normalized_history,
            previous_response_id=previous_response_id,
        )
        image_assets = (
            self._load_image_assets(
                model_context=model_context,
                referenced_files=referenced_files,
            )
            if should_load_images
            else []
        )
        use_compact_vision_prompt = self._should_use_openclaudecode_compact_prompt(
            model_context=model_context,
        )
        if use_compact_vision_prompt:
            history_context_block = self._build_compact_history_context_block(
                history=normalized_history,
                question=question,
            )
            request_history = self._build_provider_history_for_compact_prompt(
                model_context=model_context,
                history=normalized_history,
            )
            system_instruction = self._build_compact_system_instruction(
                model_context=model_context,
                has_loaded_images=bool(image_assets),
                task_mode="chat",
            )
            user_prompt = self._build_compact_chat_user_prompt(
                question=question,
                context=context,
                referenced_files=referenced_files,
                image_assets=image_assets,
                history_context_block=history_context_block,
            )
        else:
            request_history = normalized_history
            system_instruction = self._build_system_instruction(
                model_context=model_context,
                has_loaded_images=bool(image_assets),
                task_mode="chat",
            )
            user_prompt = self._build_chat_user_prompt(
                question=question,
                context=context,
                referenced_files=referenced_files,
                image_assets=image_assets,
            )
            history_context_block = self._build_history_context_block(
                history=normalized_history,
                question=question,
            )
            user_prompt = self._append_history_context_to_prompt(
                user_prompt=user_prompt,
                history_context_block=history_context_block,
            )

        try:
            if (
                metadata_callback is not None
                and bool(model_context.get("supports_stream"))
                and str(model_context.get("protocol_type") or "") == "openai_responses"
            ):
                for stream_item in self.request_openai_responses_stream_metadata(
                    model_context=model_context,
                    system_instruction=system_instruction,
                    history=request_history,
                    user_prompt=user_prompt,
                    image_assets=image_assets,
                    previous_response_id=previous_response_id,
                ):
                    if stream_item.get("type") == "metadata":
                        metadata_callback(stream_item.get("provider_response_id"))
                        continue
                    if stream_item.get("type") == "delta":
                        yield str(stream_item.get("text") or "")
                return

            yield from self._stream_protocol_text(
                model_context=model_context,
                system_instruction=system_instruction,
                history=request_history,
                user_prompt=user_prompt,
                image_assets=image_assets,
                previous_response_id=previous_response_id,
            )
        except IntegrationError as exc:
            if self._should_retry_openai_responses_without_images(
                model_context=model_context,
                error=exc,
                image_assets=image_assets,
            ):
                self._log_responses_image_retry_fallback(
                    model_context=model_context,
                    error=exc,
                    task_mode="chat",
                    image_assets=image_assets,
                )
                if use_compact_vision_prompt:
                    fallback_system_instruction = self._build_compact_system_instruction(
                        model_context=model_context,
                        has_loaded_images=False,
                        task_mode="chat",
                    )
                    fallback_user_prompt = self._build_compact_no_image_chat_user_prompt(
                        question=question,
                        context=context,
                        referenced_files=referenced_files,
                        history_context_block=history_context_block,
                    )
                else:
                    fallback_system_instruction = self._build_system_instruction(
                        model_context=model_context,
                        has_loaded_images=False,
                        task_mode="chat",
                    )
                    fallback_user_prompt = self._build_chat_user_prompt(
                        question=question,
                        context=context,
                        referenced_files=referenced_files,
                        image_assets=[],
                    )
                    fallback_user_prompt = self._append_history_context_to_prompt(
                        user_prompt=fallback_user_prompt,
                        history_context_block=history_context_block,
                    )
                fallback_result = self._request_protocol_text(
                    model_context=model_context,
                    system_instruction=fallback_system_instruction,
                    history=request_history,
                    user_prompt=fallback_user_prompt,
                    image_assets=[],
                    previous_response_id=previous_response_id,
                )
                yield from self._iter_text_chunks(text=fallback_result.text)
                return

            if not self._should_retry_without_images(
                model_context=model_context,
                error=exc,
                image_assets=image_assets,
            ):
                raise

            self._log_image_retry_fallback(
                model_context=model_context,
                error=exc,
                task_mode="chat",
                image_assets=image_assets,
            )
            fallback_system_instruction = self._build_system_instruction(
                model_context=model_context,
                has_loaded_images=False,
                task_mode="chat",
            )
            fallback_user_prompt = self._build_chat_user_prompt(
                question=question,
                context=context,
                referenced_files=referenced_files,
                image_assets=[],
            )
            fallback_user_prompt = self._append_history_context_to_prompt(
                user_prompt=fallback_user_prompt,
                history_context_block=history_context_block,
            )
            fallback_result = self._request_protocol_text(
                model_context=model_context,
                system_instruction=fallback_system_instruction,
                history=request_history,
                user_prompt=fallback_user_prompt,
                image_assets=[],
                previous_response_id=previous_response_id,
            )
            yield from self._iter_text_chunks(text=fallback_result.text)

    def request_review(
        self,
        *,
        record_id: int,
        provider_hint: str | None,
        note: str | None,
        context: dict[str, Any] | None = None,
        referenced_files: list[dict[str, Any]] | None = None,
        model_context: dict[str, Any] | None = None,
    ) -> dict:
        """返回 AI 复核摘要，未选模型时回退到预留提示。"""

        logger.info(
            "ai_review.reserved event=ai_review.reserved record_id=%s provider_hint=%s",
            record_id,
            provider_hint or "",
        )

        if model_context is None or context is None:
            return {
                "status": "reserved",
                "message": "AI 大模型复核接口已预留，但当前尚未选择可用模型配置。",
                "record_id": record_id,
            }

        image_assets = self._load_image_assets(
            model_context=model_context,
            referenced_files=referenced_files or [],
        )
        if self._is_openclaudecode_responses_vision_request(
            model_context=model_context,
            image_assets=image_assets,
        ):
            system_instruction = self._build_compact_system_instruction(
                model_context=model_context,
                has_loaded_images=bool(image_assets),
                task_mode="review",
            )
            user_prompt = self._build_compact_review_user_prompt(
                note=note,
                context=context,
                referenced_files=referenced_files or [],
                image_assets=image_assets,
            )
        else:
            system_instruction = self._build_system_instruction(
                model_context=model_context,
                has_loaded_images=bool(image_assets),
                task_mode="review",
            )
            user_prompt = self._build_review_user_prompt(
                note=note,
                context=context,
                referenced_files=referenced_files or [],
                image_assets=image_assets,
            )
        try:
            review_message = self._request_protocol_text(
                model_context=model_context,
                system_instruction=system_instruction,
                history=[],
                user_prompt=user_prompt,
                image_assets=image_assets,
            ).text
        except IntegrationError as exc:
            if self._should_retry_openai_responses_without_images(
                model_context=model_context,
                error=exc,
                image_assets=image_assets,
            ):
                self._log_responses_image_retry_fallback(
                    model_context=model_context,
                    error=exc,
                    task_mode="review",
                    image_assets=image_assets,
                )
                fallback_system_instruction = self._build_system_instruction(
                    model_context=model_context,
                    has_loaded_images=False,
                    task_mode="review",
                )
                fallback_user_prompt = self._build_review_user_prompt(
                    note=note,
                    context=context,
                    referenced_files=referenced_files or [],
                    image_assets=[],
                )
                review_message = self._request_protocol_text(
                    model_context=model_context,
                    system_instruction=fallback_system_instruction,
                    history=[],
                    user_prompt=fallback_user_prompt,
                    image_assets=[],
                ).text
                return {
                    "status": "completed",
                    "message": review_message,
                    "record_id": record_id,
                }

            if not self._should_retry_without_images(
                model_context=model_context,
                error=exc,
                image_assets=image_assets,
            ):
                raise

            self._log_image_retry_fallback(
                model_context=model_context,
                error=exc,
                task_mode="review",
                image_assets=image_assets,
            )
            fallback_system_instruction = self._build_system_instruction(
                model_context=model_context,
                has_loaded_images=False,
                task_mode="review",
            )
            fallback_user_prompt = self._build_review_user_prompt(
                note=note,
                context=context,
                referenced_files=referenced_files or [],
                image_assets=[],
            )
            review_message = self._request_protocol_text(
                model_context=model_context,
                system_instruction=fallback_system_instruction,
                history=[],
                user_prompt=fallback_user_prompt,
                image_assets=[],
            ).text

        return {
            "status": "completed",
            "message": review_message,
            "record_id": record_id,
        }

    def request_statistics_analysis(
        self,
        *,
        provider_hint: str | None,
        note: str | None,
        statistics_context: dict[str, Any],
        model_context: dict[str, Any],
    ) -> str:
        """基于统计快照生成批次级 AI 分析文本。"""

        logger.info(
            "ai_review.statistics_analysis event=ai_review.statistics_analysis provider_hint=%s",
            provider_hint or "",
        )

        system_instruction = self._build_statistics_system_instruction(
            model_context=model_context,
        )
        user_prompt = self._build_statistics_user_prompt(
            note=note,
            statistics_context=statistics_context,
        )
        return self._request_protocol_text(
            model_context=model_context,
            system_instruction=system_instruction,
            history=[],
            user_prompt=user_prompt,
            # 统计页分析基于聚合数据，不附带单条记录图像。
            image_assets=[],
        ).text

    def stream_statistics_analysis(
        self,
        *,
        provider_hint: str | None,
        note: str | None,
        statistics_context: dict[str, Any],
        model_context: dict[str, Any],
    ) -> Iterator[str]:
        """基于统计快照逐片段产出批次级 AI 分析文本。"""

        logger.info(
            "ai_review.statistics_analysis_stream event=ai_review.statistics_analysis_stream provider_hint=%s",
            provider_hint or "",
        )

        system_instruction = self._build_statistics_system_instruction(
            model_context=model_context,
        )
        user_prompt = self._build_statistics_user_prompt(
            note=note,
            statistics_context=statistics_context,
        )
        yield from self._stream_protocol_text(
            model_context=model_context,
            system_instruction=system_instruction,
            history=[],
            user_prompt=user_prompt,
            image_assets=[],
        )

    def stream_statistics_chat(
        self,
        *,
        provider_hint: str | None,
        question: str,
        note: str | None,
        history: list[dict[str, str]],
        statistics_context: dict[str, Any],
        model_context: dict[str, Any],
    ) -> Iterator[str]:
        """基于统计快照和会话历史逐片段返回追问结果。"""

        logger.info(
            "ai_review.statistics_chat_stream event=ai_review.statistics_chat_stream provider_hint=%s history_size=%s",
            provider_hint or "",
            len(history),
        )

        normalized_history = self._normalize_history(
            history=history,
            current_question=question,
        )
        system_instruction = self._build_statistics_chat_system_instruction(
            model_context=model_context,
        )
        user_prompt = self._build_statistics_chat_user_prompt(
            question=question,
            note=note,
            statistics_context=statistics_context,
        )
        history_context_block = self._build_statistics_history_context_block(
            history=normalized_history,
            question=question,
        )
        user_prompt = self._append_history_context_to_prompt(
            user_prompt=user_prompt,
            history_context_block=history_context_block,
        )
        # 米醋 / OpenClaudeCode 的 Responses 链路在多条独立 input 历史上不稳定；
        # 该网关的历史已写进 `user_prompt`，所以上游只发当前 user 消息。
        request_history = (
            []
            if self._is_openclaudecode_gateway(model_context=model_context)
            else normalized_history
        )
        yield from self._stream_protocol_text(
            model_context=model_context,
            system_instruction=system_instruction,
            history=request_history,
            user_prompt=user_prompt,
            # 统计追问仍然只围绕聚合数据，不附带单条图像。
            image_assets=[],
        )

    def build_suggested_questions_for_statistics(
        self,
        *,
        statistics_context: dict[str, Any],
    ) -> list[str]:
        """向外部暴露统计页推荐追问列表。"""

        return self._build_statistics_suggested_questions(
            statistics_context=statistics_context,
        )

    def stream_chat_about_record(
        self,
        *,
        record_id: int,
        provider_hint: str | None,
        question: str,
        history: list[dict[str, str]],
        context: dict[str, Any],
        referenced_files: list[dict[str, Any]],
        model_context: dict[str, Any],
        previous_response_id: str | None = None,
        metadata_callback: Callable[[str | None], None] | None = None,
    ) -> Iterator[str]:
        """基于当前检测记录上下文逐片段返回 AI 回答。"""

        logger.info(
            "ai_review.chat_stream event=ai_review.chat_stream record_id=%s provider_hint=%s history_size=%s",
            record_id,
            provider_hint or "",
            len(history),
        )

        yield from self._stream_model_completion(
            model_context=model_context,
            question=question,
            history=history,
            context=context,
            referenced_files=referenced_files,
            previous_response_id=previous_response_id,
            metadata_callback=metadata_callback,
        )

    def build_suggested_questions_for_context(self, *, context: dict[str, Any]) -> list[str]:
        """向外部暴露当前记录上下文下的推荐追问列表。"""

        return self._build_suggested_questions(context=context)

    def chat_about_record(
        self,
        *,
        record_id: int,
        provider_hint: str | None,
        question: str,
        history: list[dict[str, str]],
        context: dict[str, Any],
        referenced_files: list[dict[str, Any]],
        model_context: dict[str, Any] | None = None,
        previous_response_id: str | None = None,
    ) -> dict:
        """基于当前检测记录上下文返回一段可继续追问的 AI 回答。"""

        logger.info(
            "ai_review.chat event=ai_review.chat record_id=%s provider_hint=%s history_size=%s",
            record_id,
            provider_hint or "",
            len(history),
        )

        if model_context is None:
            provider_response_id = None
            answer_sections = [
                "我已经切到当前检测记录的上下文，会围绕这条记录的图片对象、检测结果和复核历史继续回答。",
                "\n".join(self._build_model_lines(model_context=model_context)),
                "\n".join(self._build_core_observation_lines(context=context)),
                "\n".join(self._build_file_lines(referenced_files=referenced_files)),
                "\n".join(
                    self._build_question_specific_lines(
                        question=question,
                        context=context,
                        referenced_files=referenced_files,
                    )
                ),
            ]

            if history:
                answer_sections.append("我已保留你当前会话中的追问上下文，因此可以继续基于上一轮回答向下分析。")

            answer_text = "\n\n".join(answer_sections)
            status = "contextual_response"
        else:
            completion_result = self._request_model_completion(
                model_context=model_context,
                question=question,
                history=history,
                context=context,
                referenced_files=referenced_files,
                previous_response_id=previous_response_id,
            )
            answer_text = completion_result.text
            provider_response_id = completion_result.provider_response_id
            status = "completed"

        return {
            "status": status,
            "answer": answer_text,
            "record_id": record_id,
            "provider_hint": provider_hint,
            "provider_response_id": provider_response_id,
            "context": context,
            "referenced_files": referenced_files,
            "suggested_questions": self._build_suggested_questions(context=context),
        }
