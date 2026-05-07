export type UserRole = "admin" | "operator" | "reviewer";
export type AdminApplicationStatus = "not_applicable" | "pending" | "approved" | "rejected";
export type PasswordChangeRequestStatus = "pending" | "approved" | "rejected";
export type PasswordChangeRequestType = "reset_to_default" | "change_to_requested";
export type DeviceType = "mp157" | "f4" | "gateway" | "other";
export type DeviceStatus = "online" | "offline" | "fault";
export type DetectionResult = "good" | "bad" | "uncertain";
export type ReviewStatus = "pending" | "reviewed" | "ai_reserved";
export type ReviewSource = "manual" | "ai_reserved";
export type FileKind = "source" | "annotated" | "thumbnail";
export type StorageProvider = "cos";
export type AIChatRole = "user" | "assistant";
export type StatisticsPdfExportMode = "visual" | "lightweight";
export type RegisterMode = "invite_join" | "company_admin_request";
export type AIGatewayVendor =
  | "openai"
  | "anthropic"
  | "google"
  | "zhipu"
  | "moonshot"
  | "minmax"
  | "deepseek"
  | "openclaudecode"
  | "relay"
  | "custom";
export type AIProtocolType =
  | "anthropic_messages"
  | "openai_compatible"
  | "openai_responses"
  | "gemini_generate_content";
export type AIAuthMode =
  | "x_api_key"
  | "authorization_bearer"
  | "both"
  | "query_api_key";
export type AIModelVendor =
  | "codex"
  | "claude"
  | "gemini"
  | "deepseek"
  | "glm"
  | "kimi"
  | "minmax"
  | "custom";

export type StructuredContextValueDto =
  | string
  | number
  | boolean
  | null
  | StructuredContextValueDto[]
  | {
      [key: string]: StructuredContextValueDto;
    };

export interface ApiErrorResponseDto {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
  request_id: string;
}

export interface ApiMessageResponseDto {
  message: string;
}

export interface AuthRuntimeOptionsDto {
  registration_enabled: boolean;
  password_reset_enabled: boolean;
  password_policy_hint: string;
}

export interface CompanyBriefDto {
  id: number;
  name: string;
  is_active: boolean;
  is_system_reserved: boolean;
}

export interface UserProfileDto {
  id: number;
  username: string;
  email: string | null;
  display_name: string;
  role: UserRole;
  company: CompanyBriefDto | null;
  is_default_admin: boolean;
  admin_application_status: AdminApplicationStatus;
  is_active: boolean;
  can_use_ai_analysis: boolean;
  last_login_at: string | null;
  password_changed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuthSessionResponseDto {
  session_expires_at: string;
  user: UserProfileDto;
}

export interface AuthSessionStateDto {
  authenticated: boolean;
  user: UserProfileDto | null;
}

export interface RegisterResponseDto {
  status: "authenticated" | "application_submitted";
  message: string;
  session_expires_at: string | null;
  user: UserProfileDto | null;
}

export interface SystemUserListItemDto {
  id: number;
  username: string;
  email: string | null;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  can_use_ai_analysis: boolean;
  last_login_at: string | null;
  password_changed_at: string | null;
  password_change_request_status: PasswordChangeRequestStatus | null;
  password_change_request_type: PasswordChangeRequestType | null;
  password_change_requested_at: string | null;
  password_change_reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SystemUserListResponseDto {
  items: SystemUserListItemDto[];
  total: number;
  skip: number;
  limit: number;
}

export interface SystemUserAiPermissionUpdateRequestDto {
  can_use_ai_analysis: boolean;
}

export interface SystemUserStatusUpdateRequestDto {
  is_active: boolean;
}

export interface UserPasswordChangeRequestInfoDto {
  password_change_request_status: PasswordChangeRequestStatus | null;
  password_change_request_type: PasswordChangeRequestType | null;
  password_change_requested_at: string | null;
  password_change_reviewed_at: string | null;
  default_reset_password: string;
}

export interface SubmitPasswordChangeRequestDto {
  request_type: PasswordChangeRequestType;
  new_password: string | null;
}

export interface ApprovePasswordChangeRequestResponseDto {
  message: string;
  applied_password: string | null;
}

export interface AdminPasswordResetResponseDto {
  message: string;
  applied_password: string;
}

export interface LoginRequestDto {
  account: string;
  password: string;
}

export interface RegisterRequestDto {
  register_mode: RegisterMode;
  username: string;
  display_name: string;
  email: string;
  password: string;
  invite_code?: string | null;
  company_name?: string | null;
  company_contact_name?: string | null;
  company_note?: string | null;
}

export interface ForgotPasswordRequestDto {
  email: string;
}

export interface ResetPasswordRequestDto {
  token: string;
  new_password: string;
}

export interface CurrentCompanyResponseDto {
  id: number;
  name: string;
  contact_name: string | null;
  note: string | null;
  invite_code: string;
  is_active: boolean;
  is_system_reserved: boolean;
  created_at: string;
  updated_at: string;
}

export interface CompanySummaryResponseDto {
  id: number;
  name: string;
  contact_name: string | null;
  note: string | null;
  invite_code: string;
  is_active: boolean;
  is_system_reserved: boolean;
  user_count: number;
  part_count: number;
  device_count: number;
  record_count: number;
  gateway_count: number;
  created_at: string;
  updated_at: string;
}

export interface CompanyListResponseDto {
  items: CompanySummaryResponseDto[];
  total: number;
  skip: number;
  limit: number;
}

export interface CompanyInviteCodeResetResponseDto {
  invite_code: string;
  message: string;
}

export interface CompanyAdminApplicationItemDto {
  id: number;
  username: string;
  email: string | null;
  display_name: string;
  is_active: boolean;
  admin_application_status: AdminApplicationStatus;
  requested_company_name: string | null;
  requested_company_contact_name: string | null;
  requested_company_note: string | null;
  created_at: string;
  updated_at: string;
}

export interface CompanyAdminApplicationListResponseDto {
  items: CompanyAdminApplicationItemDto[];
  total: number;
  skip: number;
  limit: number;
}

export interface PurgeCompanyRequestDto {
  confirm_name: string;
}

export interface SummaryStatisticsDto {
  total_count: number;
  good_count: number;
  bad_count: number;
  uncertain_count: number;
  reviewed_count: number;
  pending_review_count: number;
  pass_rate: number;
}

export interface DailyTrendItemDto {
  date: string;
  total_count: number;
  good_count: number;
  bad_count: number;
  uncertain_count: number;
}

export interface DailyTrendResponseDto {
  items: DailyTrendItemDto[];
}

export interface DefectDistributionItemDto {
  defect_type: string;
  count: number;
}

export interface DefectDistributionResponseDto {
  items: DefectDistributionItemDto[];
}

export interface ResultDistributionItemDto {
  result: DetectionResult;
  count: number;
}

export interface ReviewStatusDistributionItemDto {
  review_status: ReviewStatus;
  count: number;
}

export interface PartQualityItemDto {
  part_id: number;
  part_code: string;
  part_name: string;
  total_count: number;
  good_count: number;
  bad_count: number;
  uncertain_count: number;
  pass_rate: number;
}

export interface DeviceQualityItemDto {
  device_id: number;
  device_code: string;
  device_name: string;
  total_count: number;
  good_count: number;
  bad_count: number;
  uncertain_count: number;
  pass_rate: number;
}

export interface StatisticsFiltersDto {
  start_date: string | null;
  end_date: string | null;
  days: number;
  part_id: number | null;
  device_id: number | null;
}

export interface StatisticsSampleImageItemDto {
  record_id: number;
  record_no: string;
  part_id: number;
  part_code: string;
  part_name: string;
  part_category: string | null;
  device_id: number;
  device_code: string;
  device_name: string;
  image_file_id: number | null;
  image_file_kind: FileKind | null;
  image_count: number;
  preview_url: string | null;
  uploaded_at: string | null;
  captured_at: string;
  effective_result: DetectionResult;
  review_status: ReviewStatus;
  defect_type: string | null;
  defect_desc: string | null;
}

export interface StatisticsPartImageGroupDto {
  part_id: number;
  part_code: string;
  part_name: string;
  part_category: string | null;
  record_count: number;
  image_count: number;
  latest_uploaded_at: string | null;
  items: StatisticsSampleImageItemDto[];
}

export interface StatisticsSampleGalleryResponseDto {
  total_record_count: number;
  total_image_count: number;
  total_part_count: number;
  latest_uploaded_at: string | null;
  groups: StatisticsPartImageGroupDto[];
}

export interface StatisticsOverviewDto {
  filters: StatisticsFiltersDto;
  summary: SummaryStatisticsDto;
  daily_trend: DailyTrendItemDto[];
  defect_distribution: DefectDistributionItemDto[];
  result_distribution: ResultDistributionItemDto[];
  review_status_distribution: ReviewStatusDistributionItemDto[];
  part_quality_ranking: PartQualityItemDto[];
  device_quality_ranking: DeviceQualityItemDto[];
  key_findings: string[];
  sample_gallery: StatisticsSampleGalleryResponseDto;
  generated_at: string;
}

export interface StatisticsAIAnalysisRequestDto {
  model_profile_id: number | null;
  provider_hint: string | null;
  note: string | null;
  start_date: string | null;
  end_date: string | null;
  days: number;
  part_id: number | null;
  device_id: number | null;
}

export interface StatisticsAIAnalysisResponseDto {
  status: string;
  answer: string;
  provider_hint: string | null;
  generated_at: string;
}

export interface StatisticsAIChatRequestDto {
  question: string;
  model_profile_id: number | null;
  provider_hint: string | null;
  note: string | null;
  start_date: string | null;
  end_date: string | null;
  days: number;
  part_id: number | null;
  device_id: number | null;
  history: AIChatHistoryMessageDto[];
}

export interface StatisticsAIChatResponseDto extends StatisticsAIAnalysisResponseDto {
  suggested_questions: string[];
}

export interface StatisticsExportConversationMessageDto {
  role: AIChatRole;
  content: string;
  created_at?: string | null;
}

export interface StatisticsExportPdfRequestDto {
  export_mode: StatisticsPdfExportMode;
  model_profile_id: number | null;
  provider_hint: string | null;
  note: string | null;
  start_date: string | null;
  end_date: string | null;
  days: number;
  part_id: number | null;
  device_id: number | null;
  include_ai_analysis: boolean;
  cached_ai_answer?: string | null;
  cached_ai_provider_hint?: string | null;
  cached_ai_generated_at?: string | null;
  cached_ai_conversation?: StatisticsExportConversationMessageDto[];
  include_sample_images: boolean;
  sample_image_limit: number;
}

export interface PartDto {
  id: number;
  part_code: string;
  name: string;
  category: string | null;
  description: string | null;
  is_active: boolean;
  record_count: number;
  image_count: number;
  device_count: number;
  latest_source_device: DeviceBriefDto | null;
  latest_captured_at: string | null;
  latest_uploaded_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PartListResponseDto {
  items: PartDto[];
  total: number;
  skip: number;
  limit: number;
}

export type PartResponseDto = PartDto;

export interface DeviceDto {
  id: number;
  device_code: string;
  name: string;
  device_type: DeviceType;
  status: DeviceStatus;
  firmware_version: string | null;
  ip_address: string | null;
  last_seen_at: string | null;
  record_count: number;
  image_count: number;
  created_at: string;
  updated_at: string;
}

export interface DeviceListResponseDto {
  items: DeviceDto[];
  total: number;
  skip: number;
  limit: number;
}

export type DeviceResponseDto = DeviceDto;

export interface DeviceDeleteResponseDto {
  message: string;
  deleted_record_count: number;
}

export interface PartBriefDto {
  id: number;
  part_code: string;
  name: string;
  category: string | null;
}

export interface DeviceBriefDto {
  id: number;
  device_code: string;
  name: string;
}

export interface FileObjectDto {
  id: number;
  detection_record_id: number;
  file_kind: FileKind;
  storage_provider: StorageProvider;
  bucket_name: string;
  region: string;
  object_key: string;
  content_type: string | null;
  size_bytes: number | null;
  etag: string | null;
  preview_url: string | null;
  uploaded_at: string | null;
  storage_last_modified: string | null;
  created_at: string;
}

export interface ReviewRecordDto {
  id: number;
  detection_record_id: number;
  reviewer_id: number | null;
  reviewer_display_name: string | null;
  review_source: ReviewSource;
  decision: DetectionResult;
  defect_type: string | null;
  comment: string | null;
  reviewed_at: string;
  created_at: string;
}

export interface DetectionRecordDto {
  id: number;
  record_no: string;
  part_id: number;
  device_id: number;
  result: DetectionResult;
  effective_result: DetectionResult;
  review_status: ReviewStatus;
  surface_result: DetectionResult | null;
  backlight_result: DetectionResult | null;
  eddy_result: DetectionResult | null;
  defect_type: string | null;
  defect_desc: string | null;
  confidence_score: number | null;
  vision_context: Record<string, StructuredContextValueDto> | null;
  sensor_context: Record<string, StructuredContextValueDto> | null;
  decision_context: Record<string, StructuredContextValueDto> | null;
  device_context: Record<string, StructuredContextValueDto> | null;
  captured_at: string;
  detected_at: string | null;
  uploaded_at: string | null;
  storage_last_modified: string | null;
  created_at: string;
  updated_at: string;
  part: PartBriefDto;
  device: DeviceBriefDto;
}

export interface DetectionRecordListResponseDto {
  items: DetectionRecordDto[];
  total: number;
  skip: number;
  limit: number;
}

export interface DetectionRecordDetailDto extends DetectionRecordDto {
  files: FileObjectDto[];
  reviews: ReviewRecordDto[];
}

export interface PartCreateRequestDto {
  part_code: string;
  name: string;
  category: string | null;
  description: string | null;
  is_active: boolean;
}

export interface PartUpdateRequestDto {
  part_code?: string;
  name?: string;
  category?: string | null;
  description?: string | null;
  is_active?: boolean;
}

export interface DeviceCreateRequestDto {
  device_code: string;
  name: string;
  device_type: DeviceType;
  status: DeviceStatus;
  firmware_version: string | null;
  ip_address: string | null;
  last_seen_at: string | null;
}

export interface DeviceUpdateRequestDto {
  device_code?: string;
  name?: string;
  device_type?: DeviceType;
  status?: DeviceStatus;
  firmware_version?: string | null;
  ip_address?: string | null;
  last_seen_at?: string | null;
}

export interface DetectionRecordCreateRequestDto {
  record_no: string | null;
  part_id: number;
  device_id: number;
  result: DetectionResult;
  review_status?: ReviewStatus;
  surface_result: DetectionResult | null;
  backlight_result: DetectionResult | null;
  eddy_result: DetectionResult | null;
  defect_type: string | null;
  defect_desc: string | null;
  confidence_score: number | null;
  vision_context?: Record<string, StructuredContextValueDto> | null;
  sensor_context?: Record<string, StructuredContextValueDto> | null;
  decision_context?: Record<string, StructuredContextValueDto> | null;
  device_context?: Record<string, StructuredContextValueDto> | null;
  captured_at: string;
  detected_at: string | null;
  uploaded_at?: string | null;
  storage_last_modified?: string | null;
}

export interface ManualReviewCreateRequestDto {
  decision: DetectionResult;
  defect_type: string | null;
  comment: string | null;
  reviewed_at: string | null;
}

export interface AIReviewRequestDto {
  model_profile_id: number | null;
  provider_hint: string | null;
  note: string | null;
}

export interface AIReviewResponseDto {
  status: string;
  message: string;
  record_id: number;
}

export interface AIChatHistoryMessageDto {
  role: AIChatRole;
  content: string;
}

export interface AIContextFileDto {
  id: number;
  file_kind: FileKind;
  bucket_name: string;
  region: string;
  object_key: string;
  uploaded_at: string | null;
  preview_url: string | null;
}

export interface AIRecordContextDto {
  record_id: number;
  record_no: string;
  part_name: string;
  part_code: string;
  device_name: string;
  device_code: string;
  result: DetectionResult;
  effective_result: DetectionResult;
  review_status: ReviewStatus;
  defect_type: string | null;
  defect_desc: string | null;
  confidence_score: number | null;
  vision_context: Record<string, StructuredContextValueDto> | null;
  sensor_context: Record<string, StructuredContextValueDto> | null;
  decision_context: Record<string, StructuredContextValueDto> | null;
  device_context: Record<string, StructuredContextValueDto> | null;
  captured_at: string;
  detected_at: string | null;
  uploaded_at: string | null;
  storage_last_modified: string | null;
  file_count: number;
  review_count: number;
  available_file_kinds: FileKind[];
  latest_review_decision: DetectionResult | null;
  latest_review_comment: string | null;
  latest_reviewed_at: string | null;
}

export interface AIChatRequestDto {
  question: string;
  model_profile_id: number | null;
  provider_hint: string | null;
  history: AIChatHistoryMessageDto[];
}

export interface AIChatResponseDto {
  status: string;
  answer: string;
  record_id: number;
  provider_hint: string | null;
  context: AIRecordContextDto;
  referenced_files: AIContextFileDto[];
  suggested_questions: string[];
}

export interface AIModelProfileDto {
  id: number;
  gateway_id: number;
  display_name: string;
  upstream_vendor: AIModelVendor;
  protocol_type: AIProtocolType;
  auth_mode: AIAuthMode;
  base_url_override: string | null;
  user_agent: string | null;
  model_identifier: string;
  supports_vision: boolean;
  supports_stream: boolean;
  is_enabled: boolean;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export interface AIGatewayDto {
  id: number;
  name: string;
  vendor: AIGatewayVendor;
  official_url: string | null;
  base_url: string;
  note: string | null;
  is_enabled: boolean;
  is_custom: boolean;
  has_api_key: boolean;
  api_key_mask: string | null;
  created_at: string;
  updated_at: string;
  models: AIModelProfileDto[];
}

export interface AIGatewayListResponseDto {
  items: AIGatewayDto[];
}

export interface AIGatewayCreateRequestDto {
  name: string;
  vendor: AIGatewayVendor;
  official_url: string | null;
  base_url: string;
  note: string | null;
  api_key: string;
  is_enabled: boolean;
  is_custom: boolean;
}

export interface AIGatewayUpdateRequestDto {
  name?: string;
  vendor?: AIGatewayVendor;
  official_url?: string | null;
  base_url?: string;
  note?: string | null;
  api_key?: string | null;
  is_enabled?: boolean;
  is_custom?: boolean;
}

export interface AIGatewayDiscoveryPreviewRequestDto {
  vendor: AIGatewayVendor;
  base_url: string;
  api_key: string;
}

export interface AIModelProfileCreateRequestDto {
  display_name: string;
  upstream_vendor: AIModelVendor;
  protocol_type: AIProtocolType;
  auth_mode: AIAuthMode;
  base_url_override: string | null;
  user_agent: string | null;
  model_identifier: string;
  supports_vision: boolean;
  supports_stream: boolean;
  is_enabled: boolean;
  note: string | null;
}

export interface AIModelProfileUpdateRequestDto {
  display_name?: string;
  upstream_vendor?: AIModelVendor;
  protocol_type?: AIProtocolType;
  auth_mode?: AIAuthMode;
  base_url_override?: string | null;
  user_agent?: string | null;
  model_identifier?: string;
  supports_vision?: boolean;
  supports_stream?: boolean;
  is_enabled?: boolean;
  note?: string | null;
}

export interface AIRuntimeModelOptionDto {
  id: number;
  display_name: string;
  upstream_vendor: AIModelVendor;
  protocol_type: AIProtocolType;
  user_agent: string | null;
  model_identifier: string;
  supports_vision: boolean;
  supports_stream: boolean;
  gateway_id: number;
  gateway_name: string;
  gateway_vendor: AIGatewayVendor;
  base_url: string;
}

export interface AIRuntimeModelOptionListResponseDto {
  items: AIRuntimeModelOptionDto[];
}

export interface AIDiscoveredModelCandidateDto {
  model_identifier: string;
  display_name: string;
  upstream_vendor: AIModelVendor;
  protocol_type: AIProtocolType;
  auth_mode: AIAuthMode;
  base_url: string;
  user_agent: string | null;
  supports_vision: boolean;
  supports_stream: boolean;
  source_label: string;
}

export interface AIDiscoveredModelListResponseDto {
  items: AIDiscoveredModelCandidateDto[];
}
