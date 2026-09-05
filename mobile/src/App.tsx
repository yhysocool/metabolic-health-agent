import { FormEvent, useEffect, useMemo, useState } from "react";

import { FEATURES } from "./config/features";
import { ApiError, fetchDashboard, testApiConnection } from "./data/api-client";
import {
  assertSecureHealthUploadUrl,
  loadApiBaseUrl,
  normalizeApiBaseUrl,
  saveApiBaseUrl,
} from "./data/api-endpoint";
import { parseVivoPairingPayload } from "./data/vivo-sync";
import type { DashboardData, HealthMetric } from "./domain/contracts";
import { averageMetric, normalizedBars, recentMetricSeries } from "./domain/metrics";
import { deviceHealthProvider, vivoOvernightHealth, type VivoAutoSyncStatus, type VivoCaptureStatus, type VivoHealthObservation, type VivoHealthSnapshot, type VivoHealthStatus, type VivoHealthVital } from "./native/health-provider";

type LoadState = "loading" | "ready" | "error";

const metricDefinitions: Array<{
  metric: HealthMetric;
  label: string;
  unit: string;
  digits: number;
  source: string;
}> = [
  { metric: "sleep", label: "平均睡眠", unit: "小时", digits: 1, source: "NHANES 聚合校准" },
  { metric: "steps", label: "平均步数", unit: "步", digits: 0, source: "本地规则生成" },
  { metric: "heart_rate", label: "平均心率", unit: "bpm", digits: 0, source: "本地规则生成" },
  { metric: "heart_rate_resting", label: "静息心率", unit: "bpm", digits: 0, source: "vivo 本地 Provider" },
  { metric: "spo2", label: "最新血氧", unit: "%", digits: 1, source: "vivo 本地 Provider" },
  { metric: "stress", label: "压力指数", unit: "分", digits: 1, source: "vivo 本地 Provider" },
  { metric: "distance", label: "活动距离", unit: "米", digits: 1, source: "vivo 本地 Provider" },
  { metric: "calories", label: "活动卡路里", unit: "kcal", digits: 1, source: "vivo 本地 Provider" },
  { metric: "exercise", label: "运动时间", unit: "分钟", digits: 0, source: "NHANES 聚合校准" },
];

function displayMetric(value: number | null, digits: number): string {
  if (value === null) return "—";
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message.trim()) return error.message;
  if (typeof error === "object" && error !== null) {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return "载入失败，请检查 API 设置";
}

function vivoStatusLabel(status: VivoHealthStatus | string | undefined): string {
  const labels: Record<string, string> = {
    PASS: "可访问",
    NO_DATA: "暂无新数据",
    DENIED: "权限未授予",
    UNSUPPORTED: "设备不支持",
    API_MISSING: "接口缺失",
    ERROR: "读取错误",
  };
  return status ? labels[status] ?? status : "未检测";
}

function formatTime(timestamp: number | null | undefined): string {
  if (!timestamp) return "—";
  return new Date(timestamp).toLocaleString("zh-CN", { hour12: false });
}

function formatDuration(timestamp: number | undefined): string {
  if (timestamp === undefined || timestamp === null) return "—";
  const minutes = Math.round(timestamp / 60_000);
  return `${Math.floor(minutes / 60)}小时${minutes % 60}分`;
}

function formatVital(vital: VivoHealthVital | undefined): string {
  if (!vital || vital.status !== "PASS" || vital.value === undefined) return vivoStatusLabel(vital?.status);
  return `${vital.value.toLocaleString("zh-CN", { maximumFractionDigits: 1 })} ${vital.unit}`;
}

function formatVitalWithTime(vital: VivoHealthVital | undefined): string {
  const value = formatVital(vital);
  return vital?.status === "PASS" && vital.sourceEpochMs ? value + " · " + formatTime(vital.sourceEpochMs) : value;
}

const observationLabels: Record<string, string> = {
  steps: "步数",
  distance: "距离",
  calories: "活动卡路里",
  sleep_total_duration: "睡眠总时长",
  sleep_night_duration: "夜间睡眠",
  sleep_nap_duration: "午睡时长",
  sleep_light_duration: "浅睡时长",
  sleep_deep_duration: "深睡时长",
  sleep_rem_duration: "REM 时长",
  sleep_awake_duration: "清醒时长",
  sleep_score: "睡眠评分",
  sleep_deep_continuity: "深睡连续性",
  sleep_awake_episode_count: "清醒次数",
  sleep_awake_episode_duration: "清醒片段时长",
  heart_rate: "最新心率",
  spo2: "最新血氧",
  stress: "压力指数",
};

function formatObservation(observation: VivoHealthObservation): string {
  if (observation.status !== "PASS" || observation.value === undefined) {
    return vivoStatusLabel(observation.status);
  }
  const numericValue = typeof observation.value === "number" ? observation.value : Number(observation.value);
  if (observation.unit === "ms" && Number.isFinite(numericValue)) {
    return formatDuration(numericValue);
  }
  if (typeof observation.value === "number") {
    return `${observation.value.toLocaleString("zh-CN", { maximumFractionDigits: 1 })} ${observation.unit}`;
  }
  return `${observation.value} ${observation.unit}`.trim();
}

export default function App() {
  const [apiBaseUrl, setApiBaseUrl] = useState(loadApiBaseUrl);
  const [draftUrl, setDraftUrl] = useState(apiBaseUrl);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [message, setMessage] = useState("正在连接电脑上的健康服务…");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [refreshSequence, setRefreshSequence] = useState(0);
  const [vivoCapture, setVivoCapture] = useState<VivoCaptureStatus | null>(null);
  const [vivoSnapshot, setVivoSnapshot] = useState<VivoHealthSnapshot | null>(null);
  const [vivoMessage, setVivoMessage] = useState(() => deviceHealthProvider.enabled
    ? "正在检查本地 Provider…"
    : "浏览器预览不调用设备 Provider，请在 Android APK 中验证。");
  const [vivoBusy, setVivoBusy] = useState(false);
  const [snapshotBusy, setSnapshotBusy] = useState(false);
  const [syncBusy, setSyncBusy] = useState(false);
  const [pairingPayload, setPairingPayload] = useState("");
  const [autoSyncRequested, setAutoSyncRequested] = useState(true);
  const [autoSyncStatus, setAutoSyncStatus] = useState<VivoAutoSyncStatus | null>(null);

  useEffect(() => {
    let active = true;
    if (deviceHealthProvider.enabled) {
      void testApiConnection(apiBaseUrl)
        .then((health) => {
          if (!active) return;
          setData(null);
          setLoadState("ready");
          setMessage(`服务器连接成功（${health.environment} / ${health.data_mode}）`);
        })
        .catch((error: unknown) => {
          if (!active) return;
          setData(null);
          setLoadState("error");
          setMessage(`同步服务未连接，本地设备数据仍可用：${errorMessage(error)}`);
        });
      return () => {
        active = false;
      };
    }
    void fetchDashboard(apiBaseUrl)
      .then((dashboard) => {
        if (!active) return;
        setData(dashboard);
        setLoadState("ready");
        setMessage("已连接本地合成数据服务");
      })
      .catch((error: unknown) => {
        if (!active) return;
        setData(null);
        setLoadState("error");
        setMessage(`同步服务未连接，本地设备数据仍可用：${errorMessage(error)}`);
      });
    return () => {
      active = false;
    };
  }, [apiBaseUrl, refreshSequence]);

  useEffect(() => {
    if (!deviceHealthProvider.enabled) {
      return;
    }
    let active = true;
    let firstSnapshot = true;
    let lastSnapshotReadAt = 0;
    async function refreshVivoStatus() {
      try {
        const [availability, capture] = await Promise.all([
          deviceHealthProvider.availability(),
          vivoOvernightHealth.getStatus(),
        ]);
        if (!active) return;
        setVivoCapture(capture);
        setVivoMessage(availability.reason);
        if (firstSnapshot || Date.now() - lastSnapshotReadAt >= 60_000) {
          const snapshot = await vivoOvernightHealth.readSnapshot();
          if (!active) return;
          firstSnapshot = false;
          lastSnapshotReadAt = Date.now();
          setVivoSnapshot(snapshot);
          setVivoMessage(snapshot.privateHealth.message);
        }
      } catch {
        if (!active) return;
        setVivoMessage("无法读取 vivo 本地 Provider 状态。");
      }
    }
    void refreshVivoStatus();
    const timer = window.setInterval(() => void refreshVivoStatus(), 5000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!deviceHealthProvider.enabled) return;
      void vivoOvernightHealth.getAutoSyncStatus()
      .then((status) => {
        setAutoSyncStatus(status);
        setAutoSyncRequested(status.configured ? status.enabled : true);
      })
      .catch(() => setAutoSyncStatus(null));
  }, []);

  useEffect(() => {
    if (!deviceHealthProvider.enabled || !settingsOpen) return;
    const refreshPendingPairing = () => {
      void vivoOvernightHealth.getPendingPairing()
        .then((pending) => {
          if (pending.available && pending.payload) setPairingPayload(pending.payload);
        })
        .catch(() => undefined);
    };
    refreshPendingPairing();
    const timer = window.setInterval(refreshPendingPairing, 2000);
    return () => window.clearInterval(timer);
  }, [settingsOpen]);

  const metrics = useMemo(() => {
    const events = data?.events.items ?? [];
    const localValues: Partial<Record<HealthMetric, number | null>> = {
      sleep: vivoSnapshot?.privateHealth.sleep.status === "PASS" && vivoSnapshot.privateHealth.sleep.totalDurationMs !== undefined
        ? vivoSnapshot.privateHealth.sleep.totalDurationMs / 3_600_000
        : null,
      steps: vivoSnapshot?.activity.status === "PASS" ? vivoSnapshot.activity.steps ?? null : null,
      distance: vivoSnapshot?.activity.status === "PASS" ? vivoSnapshot.activity.distanceMeters ?? null : null,
      calories: vivoSnapshot?.activity.status === "PASS" ? vivoSnapshot.activity.caloriesKilocalories ?? null : null,
      heart_rate: vivoSnapshot?.privateHealth.vitals.heartRate.status === "PASS"
        ? vivoSnapshot.privateHealth.vitals.heartRate.value ?? null
        : null,
      heart_rate_resting: null,
      spo2: vivoSnapshot?.privateHealth.vitals.spo2.status === "PASS"
        ? vivoSnapshot.privateHealth.vitals.spo2.value ?? null
        : null,
      stress: vivoSnapshot?.privateHealth.vitals.stress.status === "PASS"
        ? vivoSnapshot.privateHealth.vitals.stress.value ?? null
        : null,
    };
    const hasNativeSnapshot = vivoSnapshot !== null;
    return metricDefinitions.map((definition) => ({
      ...definition,
      value: displayMetric(
        hasNativeSnapshot ? localValues[definition.metric] ?? null : averageMetric(events, definition.metric),
        definition.digits,
      ),
      bars: hasNativeSnapshot ? [] : normalizedBars(recentMetricSeries(events, definition.metric)),
      source: hasNativeSnapshot
        ? localValues[definition.metric] !== undefined && localValues[definition.metric] !== null
          ? "vivo 本地 Provider"
          : "vivo Provider 暂无可用数据"
        : definition.source,
    }));
  }, [data, vivoSnapshot]);

  async function saveEndpoint(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const normalized = normalizeApiBaseUrl(draftUrl);
      setMessage("正在测试 API 地址…");
      const health = await testApiConnection(normalized);
      if (health.status !== "ok") {
        throw new ApiError("目标服务器健康检查未通过");
      }
      saveApiBaseUrl(normalized);
      setLoadState("ready");
      setMessage(`服务器连接成功（${health.environment} / ${health.data_mode}）`);
      setApiBaseUrl(normalized);
      setRefreshSequence((sequence) => sequence + 1);
    } catch (error) {
      setMessage(errorMessage(error));
      setLoadState("error");
    }
  }

  async function bindVivoDevice() {
    if (!deviceHealthProvider.enabled) {
      setMessage("设备绑定只在 Android APK 中可用");
      return;
    }
    setSyncBusy(true);
    setMessage("正在验证一次性绑定码并绑定本机…");
    try {
      const pairing = parseVivoPairingPayload(pairingPayload);
      const secureBaseUrl = assertSecureHealthUploadUrl(apiBaseUrl);
      const configured = await vivoOvernightHealth.enrollDevice({
        baseUrl: secureBaseUrl,
        enrollmentCode: pairing.code,
      });
      await vivoOvernightHealth.clearPendingPairing();
      setPairingPayload("");
      setAutoSyncStatus(configured);
      setAutoSyncRequested(true);
      setMessage("设备绑定成功；同步凭据已安全保存，之后无需再次输入。正在启动自动采集…");
      try {
        const capture = await vivoOvernightHealth.startSession({ intervalSeconds: 60 });
        if ("captureStatus" in capture) {
          setVivoCapture(capture);
          setMessage("设备绑定成功；自动采集和自动上传已启动。");
        } else if (capture.status === "DENIED") {
          setMessage("设备绑定成功；请允许通知权限后启动自动采集。");
        }
      } catch {
        setMessage("设备绑定成功；后台上传已启用，请稍后手动启动自动采集。");
      }
    } catch (error) {
      setMessage("设备绑定失败：" + errorMessage(error));
      setLoadState("error");
    } finally {
      setSyncBusy(false);
    }
  }

  async function syncLocalHealthData() {
    if (!deviceHealthProvider.enabled) {
      setMessage("手动同步只在 Android APK 中可用");
      return;
    }
    if (!autoSyncStatus?.configured) {
      setMessage("请先扫描一次设备绑定二维码，绑定成功后即可自动同步");
      return;
    }

    setSyncBusy(true);
    setMessage("正在使用本机设备凭据同步本地健康记录…");
    try {
      const nativeResult = await vivoOvernightHealth.syncConfiguredNow();
      setAutoSyncStatus(nativeResult);
      if (nativeResult.lastStatus === "ERROR") throw new ApiError(nativeResult.lastMessage);
      setMessage(nativeResult.lastMessage);
      setLoadState("ready");
    } catch (error) {
      setMessage("同步失败：" + errorMessage(error));
      setLoadState("error");
    } finally {
      setSyncBusy(false);
    }
  }

  async function changeAutoSync(enabled: boolean) {
    setAutoSyncRequested(enabled);
    if (enabled || !autoSyncStatus?.enabled) return;
    setSyncBusy(true);
    try {
      const cleared = await vivoOvernightHealth.clearAutoSync();
      setAutoSyncStatus(cleared);
      setMessage("后台自动同步已关闭，设备中保存的同步令牌已清除");
    } catch {
      setMessage("关闭后台自动同步失败，请稍后重试");
      setAutoSyncRequested(true);
    } finally {
      setSyncBusy(false);
    }
  }

  async function startOvernightCapture() {
    setVivoBusy(true);
    try {
      const result = await vivoOvernightHealth.startSession({ intervalSeconds: 60 });
      if ("captureStatus" in result) {
        setVivoCapture(result);
        setVivoMessage("已启动前台采集；应用会保存新血氧点和发生变化的完整健康快照。");
      } else {
        setVivoMessage(`${vivoStatusLabel(result.status)}：${result.message}`);
      }
    } catch {
      setVivoMessage("启动失败，请确认已安装 APK 并完成 vivo 私有 Provider 授权。");
    } finally {
      setVivoBusy(false);
    }
  }

  async function stopOvernightCapture() {
    setVivoBusy(true);
    try {
      const result = await vivoOvernightHealth.stopSession();
      setVivoCapture(result);
      setVivoMessage("已停止采集，本次数据仍保存在手机本地。");
    } catch {
      setVivoMessage("停止采集失败，请稍后重试。");
    } finally {
      setVivoBusy(false);
    }
  }

  async function checkVivoAccess() {
    setSnapshotBusy(true);
    try {
      const snapshot = await vivoOvernightHealth.readSnapshot();
      setVivoSnapshot(snapshot);
      const capability = snapshot.privateHealth.capability;
      setVivoMessage(capability === "GRANTED"
        ? "vivo 私有健康 Provider 已授权，真实数据已刷新。"
        : `${capability}：${snapshot.privateHealth.message}`);
    } catch {
      setVivoMessage("检查失败，请确认 APK 已安装并查看 Provider 授权状态。");
    } finally {
      setSnapshotBusy(false);
    }
  }

  const privateCapability = vivoSnapshot?.privateHealth.capability;
  const privateHealthGranted = privateCapability === "GRANTED";

  return (
    <main className="mobile-app">
      <header className="app-header">
        <div className="brand"><span>衡</span><div><strong>衡康</strong><small>Android 体验框架</small></div></div>
        <button className="settings-button" type="button" onClick={() => setSettingsOpen((open) => !open)}>
          同步与 AI
        </button>
      </header>

      <section className="demo-notice" aria-label="数据模式说明">
        <strong>本地设备验证模式</strong>
        <span>首页优先显示 vivo 本地设备数据；同步与 AI 分析服务为可选功能。</span>
      </section>

      {settingsOpen && (
        <section className="settings-card" aria-label="同步与 AI 分析服务设置">
          <h2>同步与 AI 分析服务</h2>
          <p>首次只需扫描管理员提供的设备绑定二维码；真实健康数据只能通过安全连接上传。绑定完成后，服务器凭据会保存在本机安全区域，之后不需要用户再次输入。</p>
          <form onSubmit={(event) => void saveEndpoint(event)}>
            <label htmlFor="api-url">服务地址</label>
            <input id="api-url" value={draftUrl} onChange={(event) => setDraftUrl(event.target.value)} inputMode="url" autoCapitalize="none" autoCorrect="off" />
            <button type="submit">测试并保存</button>
          </form>
          {!autoSyncStatus?.configured && (
            <>
              <label htmlFor="pairing-payload">设备绑定二维码</label>
              <input
                id="pairing-payload"
                value={pairingPayload}
                onChange={(event) => setPairingPayload(event.target.value)}
                autoCapitalize="none"
                autoCorrect="off"
                autoComplete="off"
                placeholder="用系统相机扫描后自动唤起；也可粘贴二维码内容"
              />
              <small className="boundary-action-note">二维码只包含一次性绑定码，不包含服务器长期同步令牌。</small>
              <button type="button" onClick={() => void bindVivoDevice()} disabled={syncBusy || vivoBusy || snapshotBusy}>绑定设备并开启自动同步</button>
            </>
          )}
          <div className="auto-sync-toggle">
            <input
              id="auto-sync-enabled"
              type="checkbox"
              checked={autoSyncRequested}
              onChange={(event) => void changeAutoSync(event.target.checked)}
              disabled={syncBusy || !deviceHealthProvider.enabled}
            />
            <div><label htmlFor="auto-sync-enabled">自动采集并上传</label><small>设备凭据使用 Android Keystore 保存；有网络时自动补传本地记录。</small></div>
          </div>
          <button
            type="button"
            onClick={() => void syncLocalHealthData()}
            disabled={syncBusy || vivoBusy || !deviceHealthProvider.enabled}
          >
            {syncBusy ? "正在同步…" : "立即同步本地数据"}
          </button>
          <small className="boundary-action-note">
            {autoSyncStatus?.configured
              ? `自动同步已配置；最近成功：${formatTime(autoSyncStatus.lastSuccessAt)}`
              : autoSyncRequested
                ? "扫描一次绑定二维码后，将自动启用后台采集和上传。"
                : "未启用自动同步。"}
          </small>
          <section className={`connection ${loadState}`} role="status">
            <span aria-hidden="true" />
            <div><small>{apiBaseUrl}</small><strong>{message}</strong></div>
          </section>
        </section>
      )}

      <section className="hero">
        <p>{vivoSnapshot ? "本地设备健康概览" : data ? "30 天健康概览" : "健康数据概览"}</p>
        <h1>{vivoSnapshot ? "vivo 设备数据" : data ? `${data.profile.age} 岁演示档案` : "等待本地设备数据"}</h1>
        <span>{vivoSnapshot ? "已读取 vivo 手机本地健康 Provider；分析服务连接后可生成趋势与风险提示。" : data?.status.data_notice ?? "数据仅用于本地工程验证，不构成医疗诊断。"}</span>
      </section>

      <section className="score-card" aria-busy={loadState === "loading"}>
        <div className="score"><strong>{data?.status.score.toFixed(1) ?? "—"}</strong><span>{data ? "/100" : "本地"}</span></div>
        <div><small>健康管理状态</small><h2>{data ? "演示分析已完成" : vivoSnapshot ? "本地数据已接入" : "等待设备数据"}</h2><p>{data?.status.observations[0] ?? (vivoSnapshot ? "设备数据已读取；连接同步与 AI 分析服务后生成综合分析。" : message)}</p></div>
      </section>

      <section className="metrics-grid" aria-label="核心健康指标">
        {metrics.map((metric) => (
          <article key={metric.metric}>
            <p>{metric.label}</p>
            <div className="metric-value"><strong>{metric.value}</strong><span>{metric.unit}</span></div>
            <div className="spark" aria-label={`${metric.label}最近七次趋势`}>
              {(metric.bars.length ? metric.bars : Array.from({ length: 7 }, () => 34)).map((height, index) => (
                <i key={index} style={{ height: `${height}%` }} />
              ))}
            </div>
            <small>{metric.source}</small>
          </article>
        ))}
      </section>

      <section className="boundary-card">
        <p>设备接入边界</p>
        <h2>{!FEATURES.vivoHealth ? "vivo 本地采集框架未启用" : privateCapability === "GRANTED" ? "vivo 私有健康数据已授权" : privateCapability === "NOT_GRANTED" ? "vivo 私有健康数据未授权" : privateCapability === "UNSUPPORTED" ? "设备不支持 vivo 私有 Provider" : "正在检查 vivo Provider"}</h2>
        <span>{deviceHealthProvider.enabled ? vivoMessage : "浏览器预览不会申请设备权限，请使用 Android APK。"}</span>
        {deviceHealthProvider.enabled && privateCapability === "NOT_GRANTED" && (
          <small className="boundary-action-note">需要在电脑上执行本人设备的 ADB 授权脚本；App 内按钮只能检查，不能自行授予签名权限。</small>
        )}
      </section>

      <section className="vivo-snapshot-card" aria-label="Akari Pulse vivo 数据">
        <div className="snapshot-heading">
          <div><p>Akari Pulse 能力集成</p><h2>vivo 本地健康数据</h2></div>
          <small>{vivoSnapshot ? formatTime(vivoSnapshot.readAtEpochMs) : "尚未读取"}</small>
        </div>
        {vivoSnapshot ? (
          <>
            <div className="snapshot-group">
              <strong>今日活动</strong>
              <div className="snapshot-grid">
                <div><small>步数</small><b>{vivoSnapshot.activity.steps ?? vivoStatusLabel(vivoSnapshot.activity.status)}</b></div>
                <div><small>距离</small><b>{vivoSnapshot.activity.distanceMeters === undefined ? vivoStatusLabel(vivoSnapshot.activity.status) : `${vivoSnapshot.activity.distanceMeters.toFixed(1)} m`}</b></div>
                <div><small>活动卡路里</small><b>{vivoSnapshot.activity.caloriesKilocalories === undefined ? vivoStatusLabel(vivoSnapshot.activity.status) : `${vivoSnapshot.activity.caloriesKilocalories.toFixed(1)} kcal`}</b></div>
                <div><small>数据状态</small><b>{vivoStatusLabel(vivoSnapshot.activity.status)}</b></div>
              </div>
            </div>
            <div className="snapshot-group">
              <strong>睡眠摘要</strong>
              <div className="snapshot-grid">
                <div><small>睡眠总时长</small><b>{formatDuration(vivoSnapshot.privateHealth.sleep.totalDurationMs)}</b></div>
                <div><small>深 / 浅 / REM</small><b>{formatDuration(vivoSnapshot.privateHealth.sleep.deepSleepDurationMs)} / {formatDuration(vivoSnapshot.privateHealth.sleep.lightSleepDurationMs)} / {formatDuration(vivoSnapshot.privateHealth.sleep.remSleepDurationMs)}</b></div>
                <div><small>睡眠评分</small><b>{vivoSnapshot.privateHealth.sleep.score ?? "—"}</b></div>
                <div><small>中途醒来</small><b>{vivoSnapshot.privateHealth.sleep.awakeEpisodeCount ?? "—"}</b></div>
              </div>
            </div>
            <div className="snapshot-group">
              <strong>最新生命体征</strong>
              <div className="snapshot-grid">
                <div><small>心率（来源时间）</small><b>{formatVitalWithTime(vivoSnapshot.privateHealth.vitals.heartRate)}</b></div>
                <div><small>血氧（来源时间）</small><b>{formatVitalWithTime(vivoSnapshot.privateHealth.vitals.spo2)}</b></div>
                <div><small>压力</small><b>{formatVital(vivoSnapshot.privateHealth.vitals.stress)}</b></div>
                <div><small>本次血氧记录</small><b>{vivoSnapshot.privateHealth.vitals.spo2History?.length ?? 0} 条</b></div>
              </div>
            </div>
            <div className="snapshot-group">
              <strong>统一采集观测（{vivoSnapshot.observations?.length ?? 0} 项）</strong>
              {vivoSnapshot.observations?.length ? (
                <div className="observation-grid">
                  {vivoSnapshot.observations.map((observation, index) => (
                    <div key={`${observation.metricType}-${index}`}>
                      <small>{observationLabels[observation.metricType] ?? observation.metricType}</small>
                      <b>{formatObservation(observation)}</b>
                      <em>{vivoStatusLabel(observation.status)}</em>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="snapshot-empty">当前版本未返回统一观测列表，请重新安装最新 APK。</p>
              )}
             <small className="raw-field-note">
               原始字段已保留：活动 {vivoSnapshot.activity.providerKeys?.length ?? 0} 个；睡眠 {vivoSnapshot.privateHealth.sleep.providerColumns?.length ?? 0} 个；生命体征 {vivoSnapshot.privateHealth.vitals.providerColumns?.length ?? 0} 个。
                Provider 本次返回 {vivoSnapshot.privateHealth.vitals.careRowCount ?? 0} 行，识别血氧 {vivoSnapshot.privateHealth.vitals.spo2HistoryCount ?? 0} 条。{vivoSnapshot.privateHealth.vitals.spo2CoverageMessage ?? ""}
             </small>
            </div>
          </>
        ) : (
          <p className="snapshot-empty">点击下方“立即读取一次”，读取 Akari Pulse 已验证的活动、睡眠和最新生命体征能力。</p>
        )}
        <div className="snapshot-actions">
          <button
            type="button"
            onClick={() => void checkVivoAccess()}
            disabled={snapshotBusy || vivoBusy || !deviceHealthProvider.enabled}
          >
            {snapshotBusy ? "读取中…" : "检查并读取一次"}
          </button>
        </div>
        <small className="snapshot-footnote">私有健康状态：{vivoSnapshot ? vivoStatusLabel(vivoSnapshot.privateHealth.status) : "未检测"}；只展示真实 Provider 返回值。</small>
      </section>

      <section className="overnight-card" aria-label="夜间血氧采集">
        <div className="overnight-heading">
          <div><p>夜间血氧实验</p><h2>连续采集验证</h2></div>
          <span className={`capture-dot ${vivoCapture?.captureStatus === "RUNNING" ? "active" : ""}`} />
        </div>
        <p className="overnight-note">每 60 秒查询一次 vivo Provider；若 Provider 返回多行，将按 saO2TimeStamp 保存全部真实血氧点。若 Provider 只暴露最新一条，轮询次数不会被伪装成测量次数。</p>
        <div className="overnight-stats">
          <div><small>采集状态</small><strong>{vivoCapture?.captureStatus === "RUNNING" ? "运行中" : "已停止"}</strong></div>
          <div><small>已保存点数</small><strong>{vivoCapture?.sampleCount ?? 0}</strong></div>
          <div><small>最近 Provider 时间</small><strong>{formatTime(vivoCapture?.lastMeasuredAt)}</strong></div>
          <div><small>最近结果</small><strong>{vivoStatusLabel(vivoCapture?.lastStatus)}</strong></div>
          <div><small>完整快照数</small><strong>{vivoCapture?.snapshotCount ?? 0}</strong></div>
          <div><small>最近快照时间</small><strong>{formatTime(vivoCapture?.lastSnapshotAt)}</strong></div>
        </div>
        <div className="overnight-actions">
          {vivoCapture?.captureStatus === "RUNNING" ? (
            <button type="button" onClick={() => void stopOvernightCapture()} disabled={vivoBusy}>停止夜间采集</button>
          ) : (
            <button type="button" onClick={() => void startOvernightCapture()} disabled={vivoBusy || snapshotBusy || !deviceHealthProvider.enabled || !privateHealthGranted}>开始夜间采集</button>
          )}
        </div>
        <small className="overnight-footnote">数据状态：{vivoStatusLabel(vivoCapture?.lastStatus)} · 最近轮询：{formatTime(vivoCapture?.lastPollAt)}</small>
      </section>

      <footer>{data?.status.disclaimer ?? "仅供系统验证，不替代专业医疗意见"}</footer>
    </main>
  );
}
