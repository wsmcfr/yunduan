import type {
  AdminApplicationStatus,
  AIChatRole,
  AIAuthMode,
  AIGatewayVendor,
  AIModelVendor,
  AIProtocolType,
  DetectionResult,
  DeviceStatus,
  DeviceType,
  FileKind,
  PasswordChangeRequestStatus,
  PasswordChangeRequestType,
  ReviewSource,
  ReviewStatus,
  StorageProvider,
  UserRole,
} from "@/types/api";

export type StructuredContextValue =
  | string
  | number
  | boolean
  | null
  | StructuredContextValue[]
  | {
      [key: string]: StructuredContextValue;
    };

export type StructuredContextBlock = Record<string, StructuredContextValue>;

export interface CompanyBrief {
  id: number;
  name: string;
  isActive: boolean;
  isSystemReserved: boolean;
}

export interface UserProfile {
  id: number;
  username: string;
  email: string | null;
  displayName: string;
  role: UserRole;
  company: CompanyBrief | null;
  isDefaultAdmin: boolean;
  adminApplicationStatus: AdminApplicationStatus;
  isActive: boolean;
  canUseAiAnalysis: boolean;
  lastLoginAt: string | null;
  passwordChangedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface RegisterResponse {
  status: "authenticated" | "application_submitted";
  message: string;
  sessionExpiresAt: string | null;
  user: UserProfile | null;
}

export interface AuthSessionState {
  authenticated: boolean;
  user: UserProfile | null;
}

export interface SystemUserListItem {
  id: number;
  username: string;
  email: string | null;
  displayName: string;
  role: UserRole;
  isActive: boolean;
  canUseAiAnalysis: boolean;
  lastLoginAt: string | null;
  passwordChangedAt: string | null;
  passwordChangeRequestStatus: PasswordChangeRequestStatus | null;
  passwordChangeRequestType: PasswordChangeRequestType | null;
  passwordChangeRequestedAt: string | null;
  passwordChangeReviewedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface UserPasswordChangeRequestInfo {
  passwordChangeRequestStatus: PasswordChangeRequestStatus | null;
  passwordChangeRequestType: PasswordChangeRequestType | null;
  passwordChangeRequestedAt: string | null;
  passwordChangeReviewedAt: string | null;
  defaultResetPassword: string;
}

export interface AuthRuntimeOptions {
  registrationEnabled: boolean;
  passwordResetEnabled: boolean;
  passwordPolicyHint: string;
}

export interface CurrentCompany {
  id: number;
  name: string;
  contactName: string | null;
  note: string | null;
  inviteCode: string;
  isActive: boolean;
  isSystemReserved: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface CompanySummary {
  id: number;
  name: string;
  contactName: string | null;
  note: string | null;
  inviteCode: string;
  isActive: boolean;
  isSystemReserved: boolean;
  userCount: number;
  partCount: number;
  deviceCount: number;
  recordCount: number;
  gatewayCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface CompanyAdminApplicationItem {
  id: number;
  username: string;
  email: string | null;
  displayName: string;
  isActive: boolean;
  adminApplicationStatus: AdminApplicationStatus;
  requestedCompanyName: string | null;
  requestedCompanyContactName: string | null;
  requestedCompanyNote: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface SummaryStatistics {
  totalCount: number;
  goodCount: number;
  badCount: number;
  uncertainCount: number;
  reviewedCount: number;
  pendingReviewCount: number;
  passRate: number;
}

export interface DailyTrendItem {
  date: string;
  totalCount: number;
  goodCount: number;
  badCount: number;
  uncertainCount: number;
}

export interface DefectDistributionItem {
  defectType: string;
  count: number;
}

export interface ResultDistributionItem {
  result: DetectionResult;
  count: number;
}

export interface ReviewStatusDistributionItem {
  reviewStatus: ReviewStatus;
  count: number;
}

export interface PartQualityItem {
  partId: number;
  partCode: string;
  partName: string;
  totalCount: number;
  goodCount: number;
  badCount: number;
  uncertainCount: number;
  passRate: number;
}

export interface DeviceQualityItem {
  deviceId: number;
  deviceCode: string;
  deviceName: string;
  totalCount: number;
  goodCount: number;
  badCount: number;
  uncertainCount: number;
  passRate: number;
}

export interface StatisticsFilters {
  startDate: string | null;
  endDate: string | null;
  days: number;
  partId: number | null;
  deviceId: number | null;
}

export interface StatisticsSampleImageItem {
  recordId: number;
  recordNo: string;
  partId: number;
  partCode: string;
  partName: string;
  partCategory: string | null;
  deviceId: number;
  deviceCode: string;
  deviceName: string;
  imageFileId: number | null;
  imageFileKind: FileKind | null;
  imageCount: number;
  previewUrl: string | null;
  uploadedAt: string | null;
  capturedAt: string;
  effectiveResult: DetectionResult;
  reviewStatus: ReviewStatus;
  defectType: string | null;
  defectDesc: string | null;
}

export interface StatisticsPartImageGroup {
  partId: number;
  partCode: string;
  partName: string;
  partCategory: string | null;
  recordCount: number;
  imageCount: number;
  latestUploadedAt: string | null;
  items: StatisticsSampleImageItem[];
}

export interface StatisticsSampleGallery {
  totalRecordCount: number;
  totalImageCount: number;
  totalPartCount: number;
  latestUploadedAt: string | null;
  groups: StatisticsPartImageGroup[];
}

export interface StatisticsOverview {
  filters: StatisticsFilters;
  summary: SummaryStatistics;
  dailyTrend: DailyTrendItem[];
  defectDistribution: DefectDistributionItem[];
  resultDistribution: ResultDistributionItem[];
  reviewStatusDistribution: ReviewStatusDistributionItem[];
  partQualityRanking: PartQualityItem[];
  deviceQualityRanking: DeviceQualityItem[];
  keyFindings: string[];
  sampleGallery: StatisticsSampleGallery;
  generatedAt: string;
}

export interface StatisticsAIAnalysisResponse {
  status: string;
  answer: string;
  providerHint: string | null;
  generatedAt: string;
}

export interface PartModel {
  id: number;
  partCode: string;
  name: string;
  category: string | null;
  description: string | null;
  isActive: boolean;
  recordCount: number;
  imageCount: number;
  deviceCount: number;
  latestSourceDevice: {
    id: number;
    deviceCode: string;
    name: string;
  } | null;
  latestCapturedAt: string | null;
  latestUploadedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DeviceModel {
  id: number;
  deviceCode: string;
  name: string;
  deviceType: DeviceType;
  status: DeviceStatus;
  firmwareVersion: string | null;
  ipAddress: string | null;
  lastSeenAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface FileObjectModel {
  id: number;
  fileKind: FileKind;
  storageProvider: StorageProvider;
  objectKey: string;
  bucketName: string;
  region: string;
  contentType: string | null;
  sizeBytes: number | null;
  previewUrl: string | null;
  uploadedAt: string | null;
  storageLastModified: string | null;
}

export interface AIContextFile {
  id: number;
  fileKind: FileKind;
  bucketName: string;
  region: string;
  objectKey: string;
  uploadedAt: string | null;
  previewUrl: string | null;
}

export interface AIRecordContext {
  recordId: number;
  recordNo: string;
  partName: string;
  partCode: string;
  deviceName: string;
  deviceCode: string;
  result: DetectionResult;
  effectiveResult: DetectionResult;
  reviewStatus: ReviewStatus;
  defectType: string | null;
  defectDesc: string | null;
  confidenceScore: number | null;
  visionContext: StructuredContextBlock | null;
  sensorContext: StructuredContextBlock | null;
  decisionContext: StructuredContextBlock | null;
  deviceContext: StructuredContextBlock | null;
  capturedAt: string;
  detectedAt: string | null;
  uploadedAt: string | null;
  storageLastModified: string | null;
  fileCount: number;
  reviewCount: number;
  availableFileKinds: FileKind[];
  latestReviewDecision: DetectionResult | null;
  latestReviewComment: string | null;
  latestReviewedAt: string | null;
}

export interface AIChatResponse {
  status: string;
  answer: string;
  recordId: number;
  providerHint: string | null;
  context: AIRecordContext;
  referencedFiles: AIContextFile[];
  suggestedQuestions: string[];
}

export interface AIChatMessage {
  /**
   * 前端本地消息唯一标识。
   * 流式更新时只能靠它精确命中当前占位消息，不能再依赖可能重复的时间戳。
   */
  localId: string;
  role: AIChatRole;
  content: string;
  createdAt: string;
}

export interface AIModelProfile {
  id: number;
  gatewayId: number;
  displayName: string;
  upstreamVendor: AIModelVendor;
  protocolType: AIProtocolType;
  authMode: AIAuthMode;
  baseUrlOverride: string | null;
  userAgent: string | null;
  modelIdentifier: string;
  supportsVision: boolean;
  supportsStream: boolean;
  isEnabled: boolean;
  note: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface AIGatewayModel {
  id: number;
  name: string;
  vendor: AIGatewayVendor;
  officialUrl: string | null;
  baseUrl: string;
  note: string | null;
  isEnabled: boolean;
  isCustom: boolean;
  hasApiKey: boolean;
  apiKeyMask: string | null;
  createdAt: string;
  updatedAt: string;
  models: AIModelProfile[];
}

export interface AIRuntimeModelOption {
  id: number;
  displayName: string;
  upstreamVendor: AIModelVendor;
  protocolType: AIProtocolType;
  userAgent: string | null;
  modelIdentifier: string;
  supportsVision: boolean;
  supportsStream: boolean;
  gatewayId: number;
  gatewayName: string;
  gatewayVendor: AIGatewayVendor;
  baseUrl: string;
}

export interface AIDiscoveredModelCandidate {
  modelIdentifier: string;
  displayName: string;
  upstreamVendor: AIModelVendor;
  protocolType: AIProtocolType;
  authMode: AIAuthMode;
  baseUrl: string;
  userAgent: string | null;
  supportsVision: boolean;
  supportsStream: boolean;
  sourceLabel: string;
}

export interface ReviewRecordModel {
  id: number;
  reviewerDisplayName: string | null;
  reviewSource: ReviewSource;
  decision: DetectionResult;
  defectType: string | null;
  comment: string | null;
  reviewedAt: string;
}

export interface DetectionRecordModel {
  id: number;
  recordNo: string;
  result: DetectionResult;
  effectiveResult: DetectionResult;
  reviewStatus: ReviewStatus;
  surfaceResult: DetectionResult | null;
  backlightResult: DetectionResult | null;
  eddyResult: DetectionResult | null;
  defectType: string | null;
  defectDesc: string | null;
  confidenceScore: number | null;
  visionContext: StructuredContextBlock | null;
  sensorContext: StructuredContextBlock | null;
  decisionContext: StructuredContextBlock | null;
  deviceContext: StructuredContextBlock | null;
  capturedAt: string;
  detectedAt: string | null;
  uploadedAt: string | null;
  storageLastModified: string | null;
  createdAt: string;
  updatedAt: string;
  part: {
    id: number;
    partCode: string;
    name: string;
    category: string | null;
  };
  device: {
    id: number;
    deviceCode: string;
    name: string;
  };
  files?: FileObjectModel[];
  reviews?: ReviewRecordModel[];
}
