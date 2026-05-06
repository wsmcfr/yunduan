import type {
  DeviceCreateRequestDto,
  DeviceDeleteResponseDto,
  DeviceListResponseDto,
  DeviceResponseDto,
  DeviceStatus,
  DeviceUpdateRequestDto,
} from "@/types/api";

import { apiRequest } from "./client";

export interface DeviceListQuery {
  readonly keyword?: string;
  readonly status?: DeviceStatus;
  readonly skip?: number;
  readonly limit?: number;
}

/**
 * 获取设备列表。
 */
export function fetchDevices(query: DeviceListQuery = {}): Promise<DeviceListResponseDto> {
  const params = new URLSearchParams();

  /**
   * 设备列表支持按编码、名称和状态筛选。
   */
  if (query.keyword) {
    params.set("keyword", query.keyword);
  }
  if (query.status) {
    params.set("status", query.status);
  }
  params.set("skip", String(query.skip ?? 0));
  params.set("limit", String(query.limit ?? 20));

  return apiRequest<DeviceListResponseDto>(`/api/v1/devices?${params.toString()}`);
}

/**
 * 创建设备档案。
 */
export function createDevice(payload: DeviceCreateRequestDto): Promise<DeviceResponseDto> {
  return apiRequest<DeviceResponseDto>("/api/v1/devices", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * 更新指定设备档案。
 */
export function updateDevice(
  deviceId: number,
  payload: DeviceUpdateRequestDto,
): Promise<DeviceResponseDto> {
  return apiRequest<DeviceResponseDto>(`/api/v1/devices/${deviceId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

/**
 * 彻底删除指定 MP157 设备及其关联检测历史。
 */
export function deleteDevice(deviceId: number): Promise<DeviceDeleteResponseDto> {
  return apiRequest<DeviceDeleteResponseDto>(`/api/v1/devices/${deviceId}`, {
    method: "DELETE",
  });
}
