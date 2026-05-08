import { afterEach, describe, expect, it, vi } from "vitest";

import { deleteRecord } from "@/services/api/records";

/**
 * 构造最小 JSON Response，避免每个 API 测试重复拼装响应头。
 *
 * 参数:
 *   payload: 后端返回的 JSON 内容。
 *
 * 返回:
 *   带 `application/json` 响应头的成功响应。
 */
function createJsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

describe("records api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("deleteRecord calls the mounted record delete endpoint with DELETE", async () => {
    const fetchMock = vi.fn().mockResolvedValue(createJsonResponse({
      message: "检测记录已删除。",
    }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await deleteRecord(13);

    expect(response.message).toBe("检测记录已删除。");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/records/13",
      expect.objectContaining({
        method: "DELETE",
        credentials: "include",
      }),
    );
  });
});
