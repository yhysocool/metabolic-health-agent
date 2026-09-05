export type HealthMetric =
  | "sleep"
  | "steps"
  | "heart_rate"
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

export interface HealthEvent {
  id: string;
  user_id: string;
  source: "mock" | "synthetic" | "manual" | "nhanes" | "vivo" | "hospital";
  metric: HealthMetric;
  value: number;
  unit: string;
  timestamp: string;
  provenance: {
    display_label: string;
    is_synthetic: boolean;
    reference_dataset: string | null;
    reference_version: string | null;
    generator_version: string | null;
    note: string | null;
  } | null;
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

export interface HealthPlan {
  id: string;
  user_id: string;
  date: string;
  exercise_plan: string[];
  diet_plan: string[];
  sleep_plan: string[];
  reason: string;
}

export interface DashboardData {
  system: SystemHealth;
  profile: UserProfile;
  events: HealthEventList;
  status: HealthStatus;
}
