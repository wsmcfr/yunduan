export type UserRole = "admin" | "operator" | "reviewer";
export type DeviceType = "mp157" | "f4" | "gateway" | "other";
export type DeviceStatus = "online" | "offline" | "fault";
export type DetectionResult = "good" | "bad" | "uncertain";
export type ReviewStatus = "pending" | "reviewed" | "ai_reserved";
export type ReviewSource = "manual" | "ai_reserved";
export type FileKind = "source" | "annotated" | "thumbnail";
export type StorageProvider = "cos";

export interface ApiErrorResponseDto {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
  request_id: string;
}

export interface UserProfileDto {
  id: number;
  username: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface LoginResponseDto {
  access_token: string;
  token_type: string;
  user: UserProfileDto;
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

export interface PartDto {
  id: number;
  part_code: string;
  name: string;
  category: string | null;
  description: string | null;
  is_active: boolean;
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

export interface PartBriefDto {
  id: number;
  part_code: string;
  name: string;
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
  provider_hint: string | null;
  note: string | null;
}

export interface AIReviewResponseDto {
  status: string;
  message: string;
  record_id: number;
}
