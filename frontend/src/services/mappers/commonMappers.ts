import type {
  DailyTrendItemDto,
  DefectDistributionItemDto,
  DeviceDto,
  DetectionRecordDetailDto,
  DetectionRecordDto,
  FileObjectDto,
  PartDto,
  ReviewRecordDto,
  SummaryStatisticsDto,
  UserProfileDto,
} from "@/types/api";
import type {
  DailyTrendItem,
  DefectDistributionItem,
  DeviceModel,
  DetectionRecordModel,
  FileObjectModel,
  PartModel,
  ReviewRecordModel,
  SummaryStatistics,
  UserProfile,
} from "@/types/models";

/**
 * 将后端用户 DTO 映射为前端展示模型。
 */
export function mapUserProfileDto(dto: UserProfileDto): UserProfile {
  return {
    id: dto.id,
    username: dto.username,
    displayName: dto.display_name,
    role: dto.role,
    isActive: dto.is_active,
    lastLoginAt: dto.last_login_at,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  };
}

/**
 * 将统计概览 DTO 转成前端模型。
 */
export function mapSummaryStatisticsDto(dto: SummaryStatisticsDto): SummaryStatistics {
  return {
    totalCount: dto.total_count,
    goodCount: dto.good_count,
    badCount: dto.bad_count,
    uncertainCount: dto.uncertain_count,
    reviewedCount: dto.reviewed_count,
    pendingReviewCount: dto.pending_review_count,
    passRate: dto.pass_rate,
  };
}

/**
 * 映射每日趋势项。
 */
export function mapDailyTrendItemDto(dto: DailyTrendItemDto): DailyTrendItem {
  return {
    date: dto.date,
    totalCount: dto.total_count,
    goodCount: dto.good_count,
    badCount: dto.bad_count,
    uncertainCount: dto.uncertain_count,
  };
}

/**
 * 映射缺陷分布项。
 */
export function mapDefectDistributionItemDto(
  dto: DefectDistributionItemDto,
): DefectDistributionItem {
  return {
    defectType: dto.defect_type,
    count: dto.count,
  };
}

/**
 * 映射零件 DTO。
 */
export function mapPartDto(dto: PartDto): PartModel {
  return {
    id: dto.id,
    partCode: dto.part_code,
    name: dto.name,
    category: dto.category,
    description: dto.description,
    isActive: dto.is_active,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  };
}

/**
 * 映射设备 DTO。
 */
export function mapDeviceDto(dto: DeviceDto): DeviceModel {
  return {
    id: dto.id,
    deviceCode: dto.device_code,
    name: dto.name,
    deviceType: dto.device_type,
    status: dto.status,
    firmwareVersion: dto.firmware_version,
    ipAddress: dto.ip_address,
    lastSeenAt: dto.last_seen_at,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  };
}

/**
 * 映射审核记录 DTO。
 */
export function mapReviewRecordDto(dto: ReviewRecordDto): ReviewRecordModel {
  return {
    id: dto.id,
    reviewerDisplayName: dto.reviewer_display_name,
    reviewSource: dto.review_source,
    decision: dto.decision,
    defectType: dto.defect_type,
    comment: dto.comment,
    reviewedAt: dto.reviewed_at,
  };
}

/**
 * 映射文件对象 DTO。
 */
export function mapFileObjectDto(dto: FileObjectDto): FileObjectModel {
  return {
    id: dto.id,
    fileKind: dto.file_kind,
    storageProvider: dto.storage_provider,
    objectKey: dto.object_key,
    bucketName: dto.bucket_name,
    region: dto.region,
    contentType: dto.content_type,
    sizeBytes: dto.size_bytes,
    uploadedAt: dto.uploaded_at,
    storageLastModified: dto.storage_last_modified,
  };
}

/**
 * 映射检测记录 DTO。
 */
export function mapDetectionRecordDto(dto: DetectionRecordDto): DetectionRecordModel {
  return {
    id: dto.id,
    recordNo: dto.record_no,
    result: dto.result,
    effectiveResult: dto.effective_result,
    reviewStatus: dto.review_status,
    surfaceResult: dto.surface_result,
    backlightResult: dto.backlight_result,
    eddyResult: dto.eddy_result,
    defectType: dto.defect_type,
    defectDesc: dto.defect_desc,
    confidenceScore: dto.confidence_score,
    capturedAt: dto.captured_at,
    detectedAt: dto.detected_at,
    uploadedAt: dto.uploaded_at,
    storageLastModified: dto.storage_last_modified,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
    part: {
      id: dto.part.id,
      partCode: dto.part.part_code,
      name: dto.part.name,
    },
    device: {
      id: dto.device.id,
      deviceCode: dto.device.device_code,
      name: dto.device.name,
    },
  };
}

/**
 * 映射检测记录详情 DTO。
 */
export function mapDetectionRecordDetailDto(
  dto: DetectionRecordDetailDto,
): DetectionRecordModel {
  return {
    ...mapDetectionRecordDto(dto),
    files: dto.files.map(mapFileObjectDto),
    reviews: dto.reviews.map(mapReviewRecordDto),
  };
}
