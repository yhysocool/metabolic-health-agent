import type {
  DashboardData,
  HealthEventList,
  HealthStatus,
  SystemHealth,
  UserProfile,
  VivoSyncRequest,
  VivoSyncResult,
  VivoSyncStatus,
} from "../domain/contracts";

export const DEMO_USER_ID = "00000000-0000-0000-0000-000000000001";

export class ApiError extends Error {
  constructor(message: string, public readonly status: number | null = null) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: "GET" | "POST";
  token?: string;
  body?: unknown;
}

async function request<T>(baseUrl: string, path: string, options: RequestOptions = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15_000);
  try {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    if (options.token) headers.Authorization = "Bearer " + options.token;
    const response = await fetch(`${baseUrl}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null) as { detail?: string } | null;
      throw new ApiError(payload?.detail ?? `API 请求失败（${response.status}）`, response.status);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("连接 API 超时，请检查服务器地址和网络");
    }
    throw new ApiError("无法连接健康分析服务器");
  } finally {
    window.clearTimeout(timeout);
  }
}

export function testApiConnection(baseUrl: string): Promise<SystemHealth> {
  return request<SystemHealth>(baseUrl, "/healthz");
}

export function uploadVivoRecords(
  baseUrl: string,
  token: string,
  payload: VivoSyncRequest,
): Promise<VivoSyncResult> {
  return request<VivoSyncResult>(baseUrl, "/api/integrations/vivo/sync", {
    method: "POST",
    token,
    body: payload,
  });
}

export function fetchVivoSyncStatus(
  baseUrl: string,
  token: string,
  userId: string,
): Promise<VivoSyncStatus> {
  return request<VivoSyncStatus>(
    baseUrl,
    `/api/integrations/vivo/status/${encodeURIComponent(userId)}`,
    { token },
  );
}

export async function fetchDashboard(baseUrl: string): Promise<DashboardData> {
  const [system, profile, events, status] = await Promise.all([
    request<SystemHealth>(baseUrl, "/healthz"),
    request<UserProfile>(baseUrl, `/api/user/profile/${DEMO_USER_ID}`),
    request<HealthEventList>(baseUrl, `/api/health/events/${DEMO_USER_ID}?days=30`),
    request<HealthStatus>(baseUrl, `/api/health/status/${DEMO_USER_ID}`),
  ]);
  return { system, profile, events, status };
}
