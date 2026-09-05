export type HealthMetric =
  | "sleep"
  | "sleep_total_duration"
  | "sleep_night_duration"
  | "sleep_nap_duration"
  | "sleep_light_duration"
  | "sleep_deep_duration"
  | "sleep_rem_duration"
  | "sleep_awake_duration"
  | "sleep_score"
  | "sleep_deep_continuity"
  | "sleep_awake_episode_count"
  | "sleep_awake_episode_duration"
  | "steps"
  | "distance"
  | "calories"
  | "heart_rate"
  | "heart_rate_resting"
  | "spo2"
  | "stress"
  | "distance"
  | "calories"
  | "blood_glucose"
  | "insulin"
  | "weight"
  | "bmi"
  | "exercise";

export type TrendDirection = "increase" | "decrease" | "stable";

export interface SystemHealth {
  status: string;
  environment: string;
  data_mode: string;
}

export interface UserProfile {
  id: string;
  age: number;
  gender: "male" | "female" | "other" | "undisclosed";
  height: number;
  weight: number;
  bmi: number;
  goal: "weight_management" | "metabolic_health" | "sleep_improvement";
}

export interface HealthEventProvenance {
  display_label: string;
  is_synthetic: boolean;
  reference_dataset: string | null;
  reference_version: string | null;
  generator_version: string | null;
  note: string | null;
}

export interface HealthEvent {
  id: string;
  user_id: string;
  source: "mock" | "synthetic" | "manual" | "nhanes" | "vivo" | "hospital";
  metric: HealthMetric;
  value: number;
  unit: string;
  timestamp: string;
  provenance: HealthEventProvenance | null;
}

export interface HealthEventList {
  user_id: string;
  window_days: number;
  count: number;
  items: HealthEvent[];
}

export interface HealthStatus {
  user_id: string;
  score: number;
  label: "normal" | "attention" | "high_attention";
  bmi: number;
  homa_ir: number | null;
  trends: Record<string, TrendDirection>;
  observations: string[];
  data_notice: string;
  disclaimer: string;
}

export interface DashboardData {
  system: SystemHealth;
  profile: UserProfile;
  events: HealthEventList;
  status: HealthStatus;
}

export interface VivoSyncRecord {
  record_id: string;
  metric: HealthMetric;
  value: number;
  unit: string;
  source: string;
  source_device: string;
  measured_at: string;
  start_time: string;
  end_time: string | null;
  status: "PASS";
  raw_source: string;
  synced_at: string;
}

export interface VivoCollectionRun {
  run_id: string;
  source: string;
  read_at: string;
  status: "PASS" | "NO_DATA" | "DENIED" | "UNSUPPORTED" | "ERROR";
  provider_row_count: number;
  valid_record_count: number;
  first_measured_at?: string | null;
  last_measured_at?: string | null;
  app_version?: string | null;
  provider_schema_hash?: string | null;
}

export interface VivoSyncRequest {
  batch_id: string;
  user_id: string;
  device_id: string;
  cursor: string | null;
  collection_runs?: VivoCollectionRun[];
  records: VivoSyncRecord[];
}

export interface VivoSyncResult {
  batch_id: string;
  user_id: string;
  provider: "vivo";
  received: number;
  created: number;
  updated: number;
  unchanged: number;
  cursor: string | null;
  last_success_at: string;
  collection_runs_received?: number;
  collection_runs_created?: number;
}

export interface VivoSyncStatus {
  user_id: string;
  provider: "vivo";
  connected: boolean;
  cursor: string | null;
  last_success_at: string | null;
  last_record_count: number;
}
