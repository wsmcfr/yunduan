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
 * Element Plus `datetime` 组件回传的是本地时间格式 `YYYY-MM-DDTHH:mm:ss`，
 * 这里需要在提交前把它转换成带时区语义的 ISO 字符串，避免后端收到无时区时间。
 */
export function normalizeOptionalDateTime(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }

  const trimmedValue = value.trim();
  if (!trimmedValue) {
    return null;
  }

  /**
   * 优先按本地日期时间输入格式手动解析。
   * 这样可以避免不同运行时对“无时区 ISO 字符串”的解析细节不一致。
   */
  const localDateTimeMatch =
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(trimmedValue);

  if (localDateTimeMatch) {
    const [, yearText, monthText, dayText, hourText, minuteText, secondText = "00"] =
      localDateTimeMatch;
    const parsedDate = new Date(
      Number(yearText),
      Number(monthText) - 1,
      Number(dayText),
      Number(hourText),
      Number(minuteText),
      Number(secondText),
    );

    if (Number.isNaN(parsedDate.getTime())) {
      return null;
    }

    return parsedDate.toISOString();
  }

  /**
   * 如果调用方已经提供了带时区的 ISO 字符串，则统一转成标准 ISO 输出。
   */
  const parsedDate = new Date(trimmedValue);
  if (Number.isNaN(parsedDate.getTime())) {
    return null;
  }

  return parsedDate.toISOString();
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
