import type {
  ApiMessageResponseDto,
  CompanyAdminApplicationItemDto,
  CompanyAdminApplicationListResponseDto,
  CompanyInviteCodeResetResponseDto,
  CompanyListResponseDto,
  CurrentCompanyResponseDto,
  PurgeCompanyRequestDto,
} from "@/types/api";

import { apiRequest } from "./client";

/**
 * 获取当前登录用户所属公司的详细信息。
 */
export function fetchCurrentCompany(): Promise<CurrentCompanyResponseDto> {
  return apiRequest<CurrentCompanyResponseDto>("/api/v1/companies/current");
}

/**
 * 重置当前公司固定邀请码。
 */
export function resetCurrentCompanyInviteCode(): Promise<CompanyInviteCodeResetResponseDto> {
  return apiRequest<CompanyInviteCodeResetResponseDto>("/api/v1/companies/current/reset-invite-code", {
    method: "POST",
  });
}

/**
 * 分页拉取平台默认管理员可见的“新公司管理员申请”列表。
 */
export function fetchCompanyAdminApplications(query?: {
  keyword?: string;
  applicationStatus?: string;
  skip?: number;
  limit?: number;
}): Promise<CompanyAdminApplicationListResponseDto> {
  const searchParams = new URLSearchParams();

  if (query?.keyword) {
    searchParams.set("keyword", query.keyword);
  }
  if (query?.applicationStatus) {
    searchParams.set("application_status", query.applicationStatus);
  }
  if (query?.skip !== undefined) {
    searchParams.set("skip", String(query.skip));
  }
  if (query?.limit !== undefined) {
    searchParams.set("limit", String(query.limit));
  }

  const queryString = searchParams.toString();
  return apiRequest<CompanyAdminApplicationListResponseDto>(
    `/api/v1/companies/admin-applications${queryString ? `?${queryString}` : ""}`,
  );
}

/**
 * 批准指定管理员申请，并自动创建对应公司。
 */
export function approveCompanyAdminApplication(
  userId: number,
): Promise<CompanyAdminApplicationItemDto> {
  return apiRequest<CompanyAdminApplicationItemDto>(
    `/api/v1/companies/admin-applications/${userId}/approve`,
    {
      method: "POST",
    },
  );
}

/**
 * 拒绝指定管理员申请。
 */
export function rejectCompanyAdminApplication(
  userId: number,
): Promise<CompanyAdminApplicationItemDto> {
  return apiRequest<CompanyAdminApplicationItemDto>(
    `/api/v1/companies/admin-applications/${userId}/reject`,
    {
      method: "POST",
    },
  );
}

/**
 * 分页拉取平台默认管理员可见的公司列表。
 */
export function fetchCompanies(query?: {
  keyword?: string;
  isActive?: boolean;
  skip?: number;
  limit?: number;
}): Promise<CompanyListResponseDto> {
  const searchParams = new URLSearchParams();

  if (query?.keyword) {
    searchParams.set("keyword", query.keyword);
  }
  if (query?.isActive !== undefined) {
    searchParams.set("is_active", String(query.isActive));
  }
  if (query?.skip !== undefined) {
    searchParams.set("skip", String(query.skip));
  }
  if (query?.limit !== undefined) {
    searchParams.set("limit", String(query.limit));
  }

  const queryString = searchParams.toString();
  return apiRequest<CompanyListResponseDto>(`/api/v1/companies${queryString ? `?${queryString}` : ""}`);
}

/**
 * 停用指定公司。
 */
export function deactivateCompany(companyId: number): Promise<CurrentCompanyResponseDto> {
  return apiRequest<CurrentCompanyResponseDto>(`/api/v1/companies/${companyId}/deactivate`, {
    method: "POST",
  });
}

/**
 * 彻底删除指定公司及其业务空间。
 */
export function purgeCompany(
  companyId: number,
  payload: PurgeCompanyRequestDto,
): Promise<ApiMessageResponseDto> {
  return apiRequest<ApiMessageResponseDto>(`/api/v1/companies/${companyId}/purge`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
