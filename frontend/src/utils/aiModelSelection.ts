import type { AIRuntimeModelOption } from "@/types/models";

const preferredRuntimeModelStorageKey = "yunduan:preferred-runtime-model-id";

/**
 * 从本地存储读取用户上一次选择的运行时模型编号。
 * 这里只接受正整数，避免把脏值继续带回界面。
 */
export function getStoredPreferredRuntimeModelId(): number | null {
  if (typeof window === "undefined") {
    return null;
  }

  const rawValue = window.localStorage.getItem(preferredRuntimeModelStorageKey);
  if (!rawValue) {
    return null;
  }

  const parsedValue = Number.parseInt(rawValue, 10);
  if (!Number.isInteger(parsedValue) || parsedValue <= 0) {
    return null;
  }

  return parsedValue;
}

/**
 * 持久化当前运行时模型选择。
 * 当传入空值时主动清除，避免残留无效模型编号。
 */
export function setStoredPreferredRuntimeModelId(modelId: number | null): void {
  if (typeof window === "undefined") {
    return;
  }

  if (modelId === null) {
    window.localStorage.removeItem(preferredRuntimeModelStorageKey);
    return;
  }

  window.localStorage.setItem(preferredRuntimeModelStorageKey, String(modelId));
}

/**
 * 按“上次选择优先，否则回退首个可用模型”的规则解析默认模型。
 * 当上次选择的模型已被删除或所属网关被移除时，会自动回退到当前仍可用的第一项。
 */
export function resolvePreferredRuntimeModelId(
  runtimeModels: readonly AIRuntimeModelOption[],
  preferredModelId: number | null,
): number | null {
  if (runtimeModels.length === 0) {
    return null;
  }

  if (preferredModelId !== null && runtimeModels.some((item) => item.id === preferredModelId)) {
    return preferredModelId;
  }

  return runtimeModels[0].id;
}
