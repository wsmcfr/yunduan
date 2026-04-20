import type { DetectionRecordModel, FileObjectModel } from "@/types/models";
import type { FileKind } from "@/types/api";

const aiFilePriority: Record<FileKind, number> = {
  annotated: 0,
  source: 1,
  thumbnail: 2,
};

const fileKindLabelMap: Record<FileKind, string> = {
  annotated: "标注图",
  source: "源图",
  thumbnail: "缩略图",
};

/**
 * 返回文件类型标签。
 * 这样 AI 对话区和文件预览区不会各自维护一套类型文案。
 */
export function getAiFileKindLabel(fileKind: FileKind): string {
  return fileKindLabelMap[fileKind];
}

/**
 * 为文件对象构造可直接预览的 URL。
 * 当前优先兼容两种情况：
 * 1. 后端已经返回了签名预览地址
 * 2. `objectKey` 本身就是完整 URL
 * 3. `bucket + region + objectKey` 可以拼出 COS 公网地址
 */
export function buildAiPreviewUrl(
  file: Pick<FileObjectModel, "objectKey" | "bucketName" | "region"> & {
    previewUrl?: string | null;
  },
): string | null {
  if (file.previewUrl) {
    return file.previewUrl;
  }

  if (!file.objectKey) {
    return null;
  }

  if (file.objectKey.startsWith("http://") || file.objectKey.startsWith("https://")) {
    return file.objectKey;
  }

  if (!file.bucketName || !file.region) {
    return null;
  }

  const encodedObjectKey = file.objectKey
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");

  return `https://${file.bucketName}.cos.${file.region}.myqcloud.com/${encodedObjectKey}`;
}

/**
 * 对 AI 对话里展示的文件做稳定排序。
 * 优先级：标注图 -> 源图 -> 缩略图；同类型内按上传时间倒序。
 */
export function sortAiDisplayFiles<T extends Pick<FileObjectModel, "fileKind" | "uploadedAt">>(
  files: readonly T[],
): T[] {
  return [...files].sort((left, right) => {
    const priorityDiff = aiFilePriority[left.fileKind] - aiFilePriority[right.fileKind];
    if (priorityDiff !== 0) {
      return priorityDiff;
    }

    const leftTime = left.uploadedAt ? new Date(left.uploadedAt).getTime() : 0;
    const rightTime = right.uploadedAt ? new Date(right.uploadedAt).getTime() : 0;
    return rightTime - leftTime;
  });
}

/**
 * 生成 AI 对话弹窗的首条引导语。
 * 打开弹窗后先明确告诉用户：当前是在“这条记录”的上下文里问问题。
 */
export function createAiOpeningMessage(record: DetectionRecordModel): string {
  return [
    `已进入记录 ${record.recordNo} 的 AI 对话模式。`,
    `当前零件为 ${record.part.name}（${record.part.partCode}），设备为 ${record.device.name}（${record.device.deviceCode}）。`,
    `MP 初检结果是 ${record.result}，当前最终结果是 ${record.effectiveResult}。你可以直接围绕当前图片对象、检测结果、缺陷信息和复核历史继续追问。`,
  ].join("\n");
}

/**
 * 返回打开 AI 对话后默认展示的推荐问题。
 */
export function createDefaultAiSuggestedQuestions(record: DetectionRecordModel): string[] {
  return [
    `结合当前 ${record.part.name} 的图片对象和检测结果，先帮我总结风险点。`,
    "根据当前记录给出人工复核建议。",
    "如果这是误检，最可能出现在检测链路的哪一步？",
    "解释这条记录的拍摄、检测完成和上传时间链路。",
  ];
}
