import { afterEach, describe, expect, it } from "vitest";

import type { AIRuntimeModelOption } from "@/types/models";

import {
  getStoredPreferredRuntimeModelId,
  resolvePreferredRuntimeModelId,
  setStoredPreferredRuntimeModelId,
} from "./aiModelSelection";

function createFakeRuntimeModel(id: number, displayName: string): AIRuntimeModelOption {
  return {
    id,
    displayName,
    upstreamVendor: "codex",
    protocolType: "openai_responses",
    userAgent: null,
    modelIdentifier: displayName,
    supportsVision: true,
    supportsStream: true,
    gatewayId: id,
    gatewayName: `gateway-${id}`,
    gatewayVendor: "openai",
    baseUrl: "https://example.com/v1",
  };
}

function createStorageHarness() {
  const storage = new Map<string, string>();
  const originalWindow = globalThis.window;

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {
      localStorage: {
        getItem(key: string) {
          return storage.get(key) ?? null;
        },
        setItem(key: string, value: string) {
          storage.set(key, value);
        },
        removeItem(key: string) {
          storage.delete(key);
        },
      },
    },
  });

  return {
    storage,
    restore() {
      Object.defineProperty(globalThis, "window", {
        configurable: true,
        value: originalWindow,
      });
    },
  };
}

let restoreWindow: (() => void) | null = null;

afterEach(() => {
  restoreWindow?.();
  restoreWindow = null;
});

describe("ai model selection utilities", () => {
  it("可以读取并写入上一次选择的模型编号", () => {
    const harness = createStorageHarness();
    restoreWindow = harness.restore;

    setStoredPreferredRuntimeModelId(23);

    expect(getStoredPreferredRuntimeModelId()).toBe(23);
  });

  it("遇到无效本地存储值时返回空", () => {
    const harness = createStorageHarness();
    restoreWindow = harness.restore;
    harness.storage.set("yunduan:preferred-runtime-model-id", "not-a-number");

    expect(getStoredPreferredRuntimeModelId()).toBeNull();
  });

  it("优先恢复仍然存在的上次模型选择", () => {
    const runtimeModels = [
      createFakeRuntimeModel(7, "模型 A"),
      createFakeRuntimeModel(9, "模型 B"),
    ];

    expect(resolvePreferredRuntimeModelId(runtimeModels, 9)).toBe(9);
  });

  it("当上次模型已删除时自动回退到第一个可用模型", () => {
    const runtimeModels = [
      createFakeRuntimeModel(7, "模型 A"),
      createFakeRuntimeModel(9, "模型 B"),
    ];

    expect(resolvePreferredRuntimeModelId(runtimeModels, 999)).toBe(7);
  });
});
