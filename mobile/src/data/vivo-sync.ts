import type {
  HealthMetric,
  VivoSyncRecord,
  VivoSyncRequest,
} from "../domain/contracts";
import type {
  VivoHealthObservation,
  VivoHealthSnapshot,
  VivoStoredObservation,
} from "../native/health-provider";

const DEVICE_ID_KEY = "mha.mobile.deviceId";
const DAILY_ACTIVITY = new Set<HealthMetric>(["steps", "distance", "calories"]);
const SLEEP_METRICS = new Set<HealthMetric>([
  "sleep",
  "sleep_total_duration",
  "sleep_night_duration",
  "sleep_nap_duration",
  "sleep_light_duration",
  "sleep_deep_duration",
  "sleep_rem_duration",
  "sleep_awake_duration",
  "sleep_score",
  "sleep_deep_continuity",
  "sleep_awake_episode_count",
  "sleep_awake_episode_duration",
]);
const SUPPORTED_METRICS = new Set<HealthMetric>([
  ...DAILY_ACTIVITY,
  ...SLEEP_METRICS,
  "heart_rate",
  "heart_rate_resting",
  "spo2",
  "stress",
  "exercise",
]);

export interface VivoPairingPayload {
  code: string;
  userId?: string;
}

/** Parses the QR deep-link payload, while allowing an administrator to paste only the code. */
export function parseVivoPairingPayload(rawValue: string): VivoPairingPayload {
  const value = rawValue.trim();
  if (!value) throw new Error("绑定二维码内容不能为空");

  if (value.startsWith("healthevent://")) {
    const url = new URL(value);
    if (url.protocol !== "healthevent:" || url.hostname !== "pair") {
      throw new Error("不是衡康设备绑定二维码");
    }
    const code = url.searchParams.get("code")?.trim() ?? "";
    if (!code) throw new Error("绑定二维码缺少绑定码");
    return { code, userId: url.searchParams.get("user_id")?.trim() || undefined };
  }

  if (value.startsWith("{")) {
    let payload: { code?: unknown; user_id?: unknown; userId?: unknown };
    try {
      payload = JSON.parse(value) as { code?: unknown; user_id?: unknown; userId?: unknown };
    } catch {
      throw new Error("绑定二维码内容格式不正确");
    }
    const code = typeof payload.code === "string" ? payload.code.trim() : "";
    if (!code) throw new Error("绑定载荷缺少绑定码");
    const userId = typeof payload.user_id === "string"
      ? payload.user_id.trim()
      : typeof payload.userId === "string" ? payload.userId.trim() : undefined;
    return { code, userId: userId || undefined };
  }

  return { code: value };
}

export interface StoredVivoSnapshot {
  id: number;
  readAt: number;
  status: string;
  payload: VivoHealthSnapshot;
  syncedAt: number;
}

function randomUuid(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function getOrCreateDeviceId(): string {
  const existing = window.localStorage.getItem(DEVICE_ID_KEY);
  if (existing) return existing;
  const created = randomUuid();
  window.localStorage.setItem(DEVICE_ID_KEY, created);
  return created;
}

function toEpoch(value: number | null | undefined, fallback: number): number {
  return value && Number.isFinite(value) && value > 0 ? value : fallback;
}

function startOfLocalDay(epochMs: number): number {
  const date = new Date(epochMs);
  date.setHours(0, 0, 0, 0);
  return date.getTime();
}

function activityDayEpoch(snapshot: VivoHealthSnapshot, fallback: number): number {
  const day = snapshot.activity.day;
  if (/^\d{4}-\d{2}-\d{2}$/.test(day)) {
    const parsed = new Date(`${day}T00:00:00`);
    if (Number.isFinite(parsed.getTime())) return parsed.getTime();
  }
  return startOfLocalDay(fallback);
}

function recordTimes(
  metric: HealthMetric,
  observation: VivoHealthObservation,
  snapshot: VivoHealthSnapshot,
): { identity: string; measuredAt: number; startTime: number; endTime: number | null } {
  const fallback = toEpoch(snapshot.readAtEpochMs, Date.now());
  if (DAILY_ACTIVITY.has(metric)) {
    const start = activityDayEpoch(snapshot, fallback);
    return { identity: snapshot.activity.day || String(start), measuredAt: start, startTime: start, endTime: null };
  }
  if (SLEEP_METRICS.has(metric)) {
    const sleep = snapshot.privateHealth.sleep;
    const start = toEpoch(observation.startTime ?? sleep.sleepStartEpochMs, fallback);
    const end = observation.endTime ?? sleep.sleepEndEpochMs ?? null;
    return {
      identity: sleep.sourceDay || String(start),
      measuredAt: toEpoch(observation.measuredAt, start),
      startTime: start,
      endTime: end && end > 0 ? end : null,
    };
  }
  const measuredAt = toEpoch(
    observation.measuredAt ?? observation.startTime ?? observation.endTime,
    fallback,
  );
  return {
    identity: String(measuredAt),
    measuredAt,
    startTime: toEpoch(observation.startTime, measuredAt),
    endTime: observation.endTime && observation.endTime > 0 ? observation.endTime : null,
  };
}

async function sha256(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (item) => item.toString(16).padStart(2, "0")).join("");
}

async function toSyncRecord(
  observation: VivoHealthObservation,
  snapshot: VivoHealthSnapshot,
): Promise<VivoSyncRecord | null> {
  if (observation.status !== "PASS" || !SUPPORTED_METRICS.has(observation.metricType as HealthMetric)) {
    return null;
  }
  const value = typeof observation.value === "number"
    ? observation.value
    : Number(observation.value);
  if (!Number.isFinite(value)) return null;

  const metric = observation.metricType as HealthMetric;
  const times = recordTimes(metric, observation, snapshot);
  const source = observation.source.slice(0, 128);
  const sourceDevice = observation.sourceDevice.slice(0, 128);
  const recordKey = [source, sourceDevice, metric, times.identity].join("|");
  const syncedAt = toEpoch(observation.syncedAt, snapshot.readAtEpochMs);

  return {
    record_id: "vivo-" + await sha256(recordKey),
    metric,
    value,
    unit: observation.unit.slice(0, 32),
    source,
    source_device: sourceDevice,
    measured_at: new Date(times.measuredAt).toISOString(),
    start_time: new Date(times.startTime).toISOString(),
    end_time: times.endTime === null ? null : new Date(times.endTime).toISOString(),
    status: "PASS",
    raw_source: observation.rawSource.slice(0, 256),
    synced_at: new Date(syncedAt).toISOString(),
  };
}

export async function buildVivoSyncRequest(
  snapshots: StoredVivoSnapshot[],
  userId: string,
  deviceId: string,
  observations: VivoStoredObservation[] = [],
): Promise<VivoSyncRequest> {
  const records = new Map<string, VivoSyncRecord>();
  let latestReadAt = 0;
  const ordered = [...snapshots].sort((left, right) => left.readAt - right.readAt);

  for (const stored of ordered) {
    latestReadAt = Math.max(latestReadAt, stored.readAt);
    for (const observation of stored.payload.observations ?? []) {
      const record = await toSyncRecord(observation, stored.payload);
      if (record) records.set(record.record_id, record);
    }
  }

  for (const observation of observations) {
    const localSnapshot = {
      readAtEpochMs: observation.measuredAt ?? observation.syncedAt,
      activity: { day: "" },
      privateHealth: { sleep: {} },
    } as unknown as VivoHealthSnapshot;
    const record = await toSyncRecord(observation, localSnapshot);
    if (record) records.set(record.record_id, record);
  }

  return {
    batch_id: randomUuid(),
    user_id: userId,
    device_id: deviceId,
    cursor: latestReadAt > 0 ? String(latestReadAt) : null,
    records: [...records.values()].slice(-1000),
  };
}
