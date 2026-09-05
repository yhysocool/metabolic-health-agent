import { Capacitor, registerPlugin } from "@capacitor/core";

export interface DeviceHealthProvider {
  readonly id: string;
  readonly enabled: boolean;
  availability(): Promise<{ available: boolean; reason: string }>;
}

export type VivoHealthStatus = "PASS" | "NO_DATA" | "DENIED" | "UNSUPPORTED" | "API_MISSING" | "ERROR";

export interface VivoHealthObservation {
  metricType: string;
  source: string;
  sourceDevice: string;
  measuredAt?: number;
  startTime?: number;
  endTime?: number;
  value?: number | string;
  unit: string;
  status: VivoHealthStatus;
  rawSource: string;
  syncedAt: number;
}

export interface VivoStoredObservation extends VivoHealthObservation {
  id: number;
  sessionId: string;
  uploadedAt: number | null;
}

export interface VivoSnapshotPersistence {
  status: "PASS" | "ERROR";
  persisted: boolean;
  duplicate: boolean;
  snapshotId?: number;
  readAt: number;
  fingerprint: string;
  message: string;
}

export interface VivoSpO2Result {
  status: VivoHealthStatus;
  message: string;
  source: string;
  sourceDevice: string;
  metricType: "spo2";
  measuredAt: number | null;
  startTime: number | null;
  endTime: number | null;
  value: number | null;
  unit: "%";
  rawSource: string;
  syncedAt: number;
}

export interface VivoCaptureStatus {
  captureStatus: "RUNNING" | "STOPPED";
  sessionId: string | null;
  intervalSeconds: number;
  lastPollAt: number;
  lastSourceTimestamp: number;
  lastStatus: VivoHealthStatus;
  lastMessage: string;
  lastPollCreatedSample: boolean;
  sampleCount: number;
  firstMeasuredAt: number | null;
  lastMeasuredAt: number | null;
  snapshotCount?: number;
  lastSnapshotAt?: number | null;
  lastSnapshotStatus?: VivoHealthStatus;
  lastSnapshotMessage?: string;
}

export interface VivoAutoSyncStatus {
  enabled: boolean;
  configured: boolean;
  baseUrl: string;
  intervalMinutes: number;
  lastAttemptAt: number | null;
  lastSuccessAt: number | null;
  lastStatus: "PASS" | "NO_DATA" | "ERROR";
  lastMessage: string;
  lastCreated: number;
  lastUpdated: number;
  lastUnchanged: number;
  cursor: string | null;
}

export interface VivoPendingPairing {
  available: boolean;
  payload: string | null;
}

export interface VivoHealthVital {
  status: VivoHealthStatus;
  outcome: string;
  value?: number;
  unit: string;
  sourceEpochMs?: number;
  sourceTime?: string;
  abnormalFlag?: number;
  message?: string;
}

export interface VivoHealthSnapshot {
  source: string;
  readAtEpochMs: number;
  readAt: string;
  timezone: string;
  activity: {
    status: VivoHealthStatus;
    outcome: string;
    message: string;
    source: string;
    day: string;
    timezone: string;
    steps?: number;
    distanceMeters?: number;
    caloriesKilocalories?: number;
    sampleEpochMs: number;
    sampledAt: string;
    sourceTimestampAvailable: boolean;
    settingsRealtimeStepsRaw?: string;
    providerKeys?: string[];
    capabilityFields?: Record<string, unknown>;
    providerFields?: Record<string, unknown>;
  };
  privateHealth: {
    capability: "GRANTED" | "NOT_GRANTED" | "UNSUPPORTED" | "ERROR";
    status: VivoHealthStatus;
    message: string;
    permissionGranted: boolean;
    providersResolved: boolean;
    readAtEpochMs: number;
    readAt: string;
    sleepHistory?: Array<{
      status: VivoHealthStatus;
      sourceDay?: string;
      sleepStartEpochMs?: number;
      sleepEndEpochMs?: number;
      totalDurationMs?: number;
      [key: string]: unknown;
    }>;
    sleep: {
      status: VivoHealthStatus;
      outcome: string;
      sourceDay?: string;
      sleepStartEpochMs?: number;
      sleepEndEpochMs?: number;
      totalDurationMs?: number;
      lightSleepDurationMs?: number;
      deepSleepDurationMs?: number;
      remSleepDurationMs?: number;
      awakeDurationMs?: number;
      awakeEpisodeCount?: number;
      awakeEpisodeDurationMs?: number;
      score?: number;
      deepSleepContinuity?: number;
      lowAccuracy?: boolean;
      recorderGeneration?: number;
      timezone?: string;
      providerColumns?: string[];
      rawFields?: Record<string, string | null>;
      message?: string;
    };
    vitals: {
      status: VivoHealthStatus;
      outcome: string;
      providerSourceFrom?: string;
      message?: string;
      heartRate: VivoHealthVital;
      spo2: VivoHealthVital;
      stress: VivoHealthVital;
      heartRateHistory?: VivoHealthVital[];
      spo2History?: VivoHealthVital[];
      stressHistory?: VivoHealthVital[];
      careRowCount?: number;
      spo2HistoryCount?: number;
      spo2AccessMode?: "PROVIDER_ROWS" | "LATEST_SINGLE_POINT";
      spo2CoverageMessage?: string;
      providerColumns?: string[];
      rawFields?: Record<string, string | null>;
      rawData?: Record<string, unknown>;
    };
  };
  observations?: VivoHealthObservation[];
  providerDiagnostics?: Record<string, unknown>;
  persistence?: VivoSnapshotPersistence;
}

export interface VivoOvernightHealthPlugin {
  probe(): Promise<VivoSpO2Result>;
  readSpO2Once(): Promise<VivoSpO2Result>;
  readSnapshot(): Promise<VivoHealthSnapshot>;
  startSession(options?: { intervalSeconds?: number; sessionId?: string }): Promise<VivoSpO2Result | VivoCaptureStatus>;
  stopSession(): Promise<VivoCaptureStatus>;
  getStatus(): Promise<VivoCaptureStatus>;
  getSessionSamples(options: { sessionId: string }): Promise<{ sessionId: string; items: VivoSpO2Result[] }>;
  getHealthHistory(options?: { limit?: number }): Promise<{
    status: "PASS" | "ERROR";
    items: Array<{ id: number; readAt: number; status: VivoHealthStatus; payload: VivoHealthSnapshot; syncedAt: number }>;
    observations: VivoStoredObservation[];
  }>;
  configureAutoSync(options: { baseUrl: string; token: string; userId: string; cursor: string | null }): Promise<VivoAutoSyncStatus>;
  enrollDevice(options: { baseUrl: string; enrollmentCode: string }): Promise<VivoAutoSyncStatus>;
  getPendingPairing(): Promise<VivoPendingPairing>;
  clearPendingPairing(): Promise<VivoPendingPairing>;
  getAutoSyncStatus(): Promise<VivoAutoSyncStatus>;
  syncConfiguredNow(): Promise<VivoAutoSyncStatus>;
  clearAutoSync(): Promise<VivoAutoSyncStatus>;
}

export const vivoOvernightHealth = registerPlugin<VivoOvernightHealthPlugin>("VivoOvernightHealth");

class DisabledDeviceHealthProvider implements DeviceHealthProvider {
  readonly id = "none";
  readonly enabled = false;

  async availability(): Promise<{ available: boolean; reason: string }> {
    return {
      available: false,
      reason: "当前版本只使用合成演示数据，未申请或调用 vivo Health Kit 权限。",
    };
  }
}

class VivoDeviceHealthProvider implements DeviceHealthProvider {
  readonly id = "vivo_local_health_provider";
  readonly enabled = true;

  async availability(): Promise<{ available: boolean; reason: string }> {
    try {
      const result = await vivoOvernightHealth.probe();
      return {
        available: result.status === "PASS",
        reason: result.message,
      };
    } catch {
      return {
        available: false,
        reason: "当前 APK 尚未连接到 vivo 本地健康 Provider。",
      };
    }
  }
}

export const deviceHealthProvider: DeviceHealthProvider = Capacitor.isNativePlatform()
  ? new VivoDeviceHealthProvider()
  : new DisabledDeviceHealthProvider();
