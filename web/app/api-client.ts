import type {
  DashboardData,
  HealthEventList,
  HealthPlan,
  HealthStatus,
  SystemHealth,
  UserProfile,
} from "./contracts";

export const DEMO_USER_ID = "00000000-0000-0000-0000-000000000001";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL
  ?? (typeof window === "undefined"
    ? "http://localhost:8000"
    : `${window.location.protocol}//${window.location.hostname}:8000`)
).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    let detail = `请求失败（${response.status}）`;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail || detail;
    } catch {
      // 非 JSON 错误响应使用通用提示，避免把服务端正文展示给用户。
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

export async function fetchDashboardData(signal?: AbortSignal): Promise<DashboardData> {
  const [system, profile, events, status] = await Promise.all([
    request<SystemHealth>("/healthz", signal),
    request<UserProfile>(`/api/user/profile/${DEMO_USER_ID}`, signal),
    request<HealthEventList>(`/api/health/events/${DEMO_USER_ID}?days=30`, signal),
    request<HealthStatus>(`/api/health/status/${DEMO_USER_ID}`, signal),
  ]);
  return { system, profile, events, status };
}

export function fetchHealthPlan(signal?: AbortSignal): Promise<HealthPlan> {
  return request<HealthPlan>(`/api/agent/plan/${DEMO_USER_ID}`, signal);
}
