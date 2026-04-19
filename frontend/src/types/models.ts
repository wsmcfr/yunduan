import type {
  DetectionResult,
  DeviceStatus,
  DeviceType,
  FileKind,
  ReviewSource,
  ReviewStatus,
  StorageProvider,
  UserRole,
} from "@/types/api";

export interface UserProfile {
  id: number;
  username: string;
  displayName: string;
  role: UserRole;
  isActive: boolean;
  lastLoginAt: string | null;
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

export interface PartModel {
  id: number;
  partCode: string;
  name: string;
  category: string | null;
  description: string | null;
  isActive: boolean;
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
  uploadedAt: string | null;
  storageLastModified: string | null;
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
  };
  device: {
    id: number;
    deviceCode: string;
    name: string;
  };
  files?: FileObjectModel[];
  reviews?: ReviewRecordModel[];
}
