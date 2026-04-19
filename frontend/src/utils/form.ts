/**
 * 将可选文本字段规范化为空值或裁剪后的字符串。
 * 这样在提交接口时可以明确区分“用户清空了字段”和“字段本来没填”。
 */
export function normalizeOptionalText(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }

  const trimmedValue = value.trim();
  return trimmedValue.length > 0 ? trimmedValue : null;
}

/**
 * 规范化可选日期时间字符串。
 */
export function normalizeOptionalDateTime(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  return value;
}

/**
 * 将 ISO 时间转换成 Element Plus datetime 组件更容易回填的本地字符串。
 */
export function formatDateTimeInputValue(value: string | null | undefined): string {
  if (!value) {
    return "";
  }

  const parsedDate = new Date(value);
  if (Number.isNaN(parsedDate.getTime())) {
    return "";
  }

  const pad = (input: number) => String(input).padStart(2, "0");

  return `${parsedDate.getFullYear()}-${pad(parsedDate.getMonth() + 1)}-${pad(parsedDate.getDate())}T${pad(parsedDate.getHours())}:${pad(parsedDate.getMinutes())}:${pad(parsedDate.getSeconds())}`;
}

/**
 * 生成当前时间对应的本地日期时间字符串，适合作为表单默认值。
 */
export function createCurrentDateTimeInputValue(): string {
  return formatDateTimeInputValue(new Date().toISOString());
}
