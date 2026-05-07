import { describe, expect, test } from "vitest";

import { aiGatewayPresets, aiModelTemplates } from "@/features/settings/aiSettingsCatalog";

describe("ai settings catalog", () => {
  test("OpenClaudeCode preset now points to the Micu API host", () => {
    const preset = aiGatewayPresets.find((item) => item.id === "openclaudecode-relay");

    expect(preset?.payload.official_url).toBe("https://www.micuapi.ai");
    expect(preset?.payload.base_url).toBe("https://www.micuapi.ai");
  });

  test("OpenClaudeCode Codex template keeps the Micu API v1 runtime override", () => {
    const template = aiModelTemplates.find((item) => item.id === "openclaudecode-codex");

    expect(template?.payload.base_url_override).toBe("https://www.micuapi.ai/v1");
  });
});
