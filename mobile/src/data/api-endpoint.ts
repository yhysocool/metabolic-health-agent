import { Capacitor } from "@capacitor/core";

const STORAGE_KEY = "mha.mobile.apiBaseUrl";
const EMULATOR_API_URL = "http://10.0.2.2:8000";

export function normalizeApiBaseUrl(value: string): string {
  const trimmed = value.trim().replace(/\/+$/, "");
  if (!trimmed) throw new Error("请输入 API 地址");
  const parsed = new URL(trimmed);
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error("API 地址只允许 http 或 https");
  }
  if (parsed.username || parsed.password) {
    throw new Error("API 地址不能包含用户名或密码");
  }
  return parsed.toString().replace(/\/+$/, "");
}

function isPrivateOrLoopbackHost(hostname: string): boolean {
  if (hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1") return true;
  const parts = hostname.split(".").map(Number);
  if (parts.length !== 4 || parts.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) {
    return false;
  }
  return parts[0] === 10
    || parts[0] === 127
    || (parts[0] === 192 && parts[1] === 168)
    || (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31);
}

export function assertSecureHealthUploadUrl(value: string): string {
  const normalized = normalizeApiBaseUrl(value);
  const parsed = new URL(normalized);
  if (parsed.protocol === "https:" || isPrivateOrLoopbackHost(parsed.hostname)) {
    return normalized;
  }
  throw new Error("公网健康数据上传必须使用 HTTPS；当前地址只允许测试连接");
}

function configuredApiBaseUrl(): string | null {
  const value = import.meta.env.VITE_API_BASE_URL?.trim();
  return value ? normalizeApiBaseUrl(value) : null;
}

export function defaultApiBaseUrl(): string {
  const configured = configuredApiBaseUrl();
  if (configured) return configured;
  if (Capacitor.isNativePlatform()) return EMULATOR_API_URL;
  return `${window.location.protocol}//${window.location.hostname}:8000`;
}

export function loadApiBaseUrl(): string {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored ? normalizeApiBaseUrl(stored) : defaultApiBaseUrl();
  } catch {
    return defaultApiBaseUrl();
  }
}

export function saveApiBaseUrl(value: string): string {
  const normalized = normalizeApiBaseUrl(value);
  window.localStorage.setItem(STORAGE_KEY, normalized);
  return normalized;
}
