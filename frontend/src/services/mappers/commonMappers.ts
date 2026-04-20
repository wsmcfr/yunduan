import type {
  AIChatResponseDto,
  AIContextFileDto,
  AIDiscoveredModelCandidateDto,
  AIRecordContextDto,
  AIGatewayDto,
  AIModelProfileDto,
  AIRuntimeModelOptionDto,
  DailyTrendItemDto,
  DefectDistributionItemDto,
  DeviceQualityItemDto,
  DeviceDto,
  DetectionRecordDetailDto,
  DetectionRecordDto,
  FileObjectDto,
  PartDto,
  PartQualityItemDto,
  ResultDistributionItemDto,
  ReviewRecordDto,
  ReviewStatusDistributionItemDto,
  StatisticsAIAnalysisResponseDto,
  StatisticsFiltersDto,
  StatisticsOverviewDto,
  StatisticsPartImageGroupDto,
  StatisticsSampleGalleryResponseDto,
  StatisticsSampleImageItemDto,
  SummaryStatisticsDto,
  UserProfileDto,
} from "@/types/api";
import type {
  AIChatResponse,
  AIContextFile,
  AIDiscoveredModelCandidate,
  AIRecordContext,
  AIGatewayModel,
  AIModelProfile,
  AIRuntimeModelOption,
  DailyTrendItem,
  DefectDistributionItem,
  DeviceQualityItem,
  DeviceModel,
  DetectionRecordModel,
  FileObjectModel,
  PartModel,
  PartQualityItem,
  ResultDistributionItem,
  ReviewRecordModel,
  ReviewStatusDistributionItem,
  StatisticsAIAnalysisResponse,
  StatisticsFilters,
  StatisticsOverview,
  StatisticsPartImageGroup,
  StatisticsSampleGallery,
  StatisticsSampleImageItem,
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
 * 映射最终结果分布项。
 */
export function mapResultDistributionItemDto(dto: ResultDistributionItemDto): ResultDistributionItem {
  return {
    result: dto.result,
    count: dto.count,
  };
}

/**
 * 映射审核状态分布项。
 */
export function mapReviewStatusDistributionItemDto(
  dto: ReviewStatusDistributionItemDto,
): ReviewStatusDistributionItem {
  return {
    reviewStatus: dto.review_status,
    count: dto.count,
  };
}

/**
 * 映射零件质量排行项。
 */
export function mapPartQualityItemDto(dto: PartQualityItemDto): PartQualityItem {
  return {
    partId: dto.part_id,
    partCode: dto.part_code,
    partName: dto.part_name,
    totalCount: dto.total_count,
    goodCount: dto.good_count,
    badCount: dto.bad_count,
    uncertainCount: dto.uncertain_count,
    passRate: dto.pass_rate,
  };
}

/**
 * 映射设备质量排行项。
 */
export function mapDeviceQualityItemDto(dto: DeviceQualityItemDto): DeviceQualityItem {
  return {
    deviceId: dto.device_id,
    deviceCode: dto.device_code,
    deviceName: dto.device_name,
    totalCount: dto.total_count,
    goodCount: dto.good_count,
    badCount: dto.bad_count,
    uncertainCount: dto.uncertain_count,
    passRate: dto.pass_rate,
  };
}

/**
 * 映射统计页当前筛选快照。
 */
export function mapStatisticsFiltersDto(dto: StatisticsFiltersDto): StatisticsFilters {
  return {
    startDate: dto.start_date,
    endDate: dto.end_date,
    days: dto.days,
    partId: dto.part_id,
    deviceId: dto.device_id,
  };
}

/**
 * 映射统计页图库中的单条样本卡片。
 */
export function mapStatisticsSampleImageItemDto(
  dto: StatisticsSampleImageItemDto,
): StatisticsSampleImageItem {
  return {
    recordId: dto.record_id,
    recordNo: dto.record_no,
    partId: dto.part_id,
    partCode: dto.part_code,
    partName: dto.part_name,
    partCategory: dto.part_category,
    deviceId: dto.device_id,
    deviceCode: dto.device_code,
    deviceName: dto.device_name,
    imageFileId: dto.image_file_id,
    imageFileKind: dto.image_file_kind,
    imageCount: dto.image_count,
    previewUrl: dto.preview_url,
    uploadedAt: dto.uploaded_at,
    capturedAt: dto.captured_at,
    effectiveResult: dto.effective_result,
    reviewStatus: dto.review_status,
    defectType: dto.defect_type,
    defectDesc: dto.defect_desc,
  };
}

/**
 * 映射统计页图库中的单个零件分组。
 */
export function mapStatisticsPartImageGroupDto(
  dto: StatisticsPartImageGroupDto,
): StatisticsPartImageGroup {
  return {
    partId: dto.part_id,
    partCode: dto.part_code,
    partName: dto.part_name,
    partCategory: dto.part_category,
    recordCount: dto.record_count,
    imageCount: dto.image_count,
    latestUploadedAt: dto.latest_uploaded_at,
    items: dto.items.map(mapStatisticsSampleImageItemDto),
  };
}

/**
 * 映射统计页图库摘要。
 */
export function mapStatisticsSampleGalleryResponseDto(
  dto: StatisticsSampleGalleryResponseDto,
): StatisticsSampleGallery {
  return {
    totalRecordCount: dto.total_record_count,
    totalImageCount: dto.total_image_count,
    totalPartCount: dto.total_part_count,
    latestUploadedAt: dto.latest_uploaded_at,
    groups: dto.groups.map(mapStatisticsPartImageGroupDto),
  };
}

/**
 * 映射统计页完整概览 DTO。
 */
export function mapStatisticsOverviewDto(dto: StatisticsOverviewDto): StatisticsOverview {
  return {
    filters: mapStatisticsFiltersDto(dto.filters),
    summary: mapSummaryStatisticsDto(dto.summary),
    dailyTrend: dto.daily_trend.map(mapDailyTrendItemDto),
    defectDistribution: dto.defect_distribution.map(mapDefectDistributionItemDto),
    resultDistribution: dto.result_distribution.map(mapResultDistributionItemDto),
    reviewStatusDistribution: dto.review_status_distribution.map(
      mapReviewStatusDistributionItemDto,
    ),
    partQualityRanking: dto.part_quality_ranking.map(mapPartQualityItemDto),
    deviceQualityRanking: dto.device_quality_ranking.map(mapDeviceQualityItemDto),
    keyFindings: dto.key_findings,
    sampleGallery: mapStatisticsSampleGalleryResponseDto(dto.sample_gallery),
    generatedAt: dto.generated_at,
  };
}

/**
 * 映射统计页 AI 分析响应 DTO。
 */
export function mapStatisticsAIAnalysisResponseDto(
  dto: StatisticsAIAnalysisResponseDto,
): StatisticsAIAnalysisResponse {
  return {
    status: dto.status,
    answer: dto.answer,
    providerHint: dto.provider_hint,
    generatedAt: dto.generated_at,
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
    recordCount: dto.record_count,
    imageCount: dto.image_count,
    latestCapturedAt: dto.latest_captured_at,
    latestUploadedAt: dto.latest_uploaded_at,
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
    previewUrl: dto.preview_url,
    uploadedAt: dto.uploaded_at,
    storageLastModified: dto.storage_last_modified,
  };
}

/**
 * 映射 AI 对话文件上下文 DTO。
 */
export function mapAIContextFileDto(dto: AIContextFileDto): AIContextFile {
  return {
    id: dto.id,
    fileKind: dto.file_kind,
    bucketName: dto.bucket_name,
    region: dto.region,
    objectKey: dto.object_key,
    uploadedAt: dto.uploaded_at,
    previewUrl: dto.preview_url,
  };
}

/**
 * 映射 AI 对话记录上下文 DTO。
 */
export function mapAIRecordContextDto(dto: AIRecordContextDto): AIRecordContext {
  return {
    recordId: dto.record_id,
    recordNo: dto.record_no,
    partName: dto.part_name,
    partCode: dto.part_code,
    deviceName: dto.device_name,
    deviceCode: dto.device_code,
    result: dto.result,
    effectiveResult: dto.effective_result,
    reviewStatus: dto.review_status,
    defectType: dto.defect_type,
    defectDesc: dto.defect_desc,
    confidenceScore: dto.confidence_score,
    visionContext: dto.vision_context,
    sensorContext: dto.sensor_context,
    decisionContext: dto.decision_context,
    deviceContext: dto.device_context,
    capturedAt: dto.captured_at,
    detectedAt: dto.detected_at,
    uploadedAt: dto.uploaded_at,
    storageLastModified: dto.storage_last_modified,
    fileCount: dto.file_count,
    reviewCount: dto.review_count,
    availableFileKinds: dto.available_file_kinds,
    latestReviewDecision: dto.latest_review_decision,
    latestReviewComment: dto.latest_review_comment,
    latestReviewedAt: dto.latest_reviewed_at,
  };
}

/**
 * 映射 AI 对话响应 DTO。
 */
export function mapAIChatResponseDto(dto: AIChatResponseDto): AIChatResponse {
  return {
    status: dto.status,
    answer: dto.answer,
    recordId: dto.record_id,
    providerHint: dto.provider_hint,
    context: mapAIRecordContextDto(dto.context),
    referencedFiles: dto.referenced_files.map(mapAIContextFileDto),
    suggestedQuestions: dto.suggested_questions,
  };
}

/**
 * 映射 AI 模型配置 DTO。
 */
export function mapAIModelProfileDto(dto: AIModelProfileDto): AIModelProfile {
  return {
    id: dto.id,
    gatewayId: dto.gateway_id,
    displayName: dto.display_name,
    upstreamVendor: dto.upstream_vendor,
    protocolType: dto.protocol_type,
    authMode: dto.auth_mode,
    baseUrlOverride: dto.base_url_override,
    userAgent: dto.user_agent,
    modelIdentifier: dto.model_identifier,
    supportsVision: dto.supports_vision,
    supportsStream: dto.supports_stream,
    isEnabled: dto.is_enabled,
    note: dto.note,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  };
}

/**
 * 映射 AI 网关 DTO。
 */
export function mapAIGatewayDto(dto: AIGatewayDto): AIGatewayModel {
  return {
    id: dto.id,
    name: dto.name,
    vendor: dto.vendor,
    officialUrl: dto.official_url,
    baseUrl: dto.base_url,
    note: dto.note,
    isEnabled: dto.is_enabled,
    isCustom: dto.is_custom,
    hasApiKey: dto.has_api_key,
    apiKeyMask: dto.api_key_mask,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
    models: dto.models.map(mapAIModelProfileDto),
  };
}

/**
 * 映射运行时 AI 模型选项 DTO。
 */
export function mapAIRuntimeModelOptionDto(
  dto: AIRuntimeModelOptionDto,
): AIRuntimeModelOption {
  return {
    id: dto.id,
    displayName: dto.display_name,
    upstreamVendor: dto.upstream_vendor,
    protocolType: dto.protocol_type,
    userAgent: dto.user_agent,
    modelIdentifier: dto.model_identifier,
    supportsVision: dto.supports_vision,
    supportsStream: dto.supports_stream,
    gatewayId: dto.gateway_id,
    gatewayName: dto.gateway_name,
    gatewayVendor: dto.gateway_vendor,
    baseUrl: dto.base_url,
  };
}

/**
 * 映射自动探测到的模型候选项 DTO。
 */
export function mapAIDiscoveredModelCandidateDto(
  dto: AIDiscoveredModelCandidateDto,
): AIDiscoveredModelCandidate {
  return {
    modelIdentifier: dto.model_identifier,
    displayName: dto.display_name,
    upstreamVendor: dto.upstream_vendor,
    protocolType: dto.protocol_type,
    authMode: dto.auth_mode,
    baseUrl: dto.base_url,
    userAgent: dto.user_agent,
    supportsVision: dto.supports_vision,
    supportsStream: dto.supports_stream,
    sourceLabel: dto.source_label,
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
    visionContext: dto.vision_context,
    sensorContext: dto.sensor_context,
    decisionContext: dto.decision_context,
    deviceContext: dto.device_context,
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
