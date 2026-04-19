/**
 * 将 ISO 时间字符串格式化为更适合后台界面阅读的本地时间。
 */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "未记录";
  }

  const parsedDate = new Date(value);
  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  return parsedDate.toLocaleString("zh-CN", {
    hour12: false,
  });
}

/**
 * 将 0-1 置信度转成百分比文本。
 */
export function formatConfidence(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "未给出";
  }

  return `${Math.round(value * 100)}%`;
}
