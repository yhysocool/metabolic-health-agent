"use client";

import type { CSSProperties } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, fetchDashboardData, fetchHealthPlan } from "./api-client";
import type { DashboardData, HealthPlan } from "./contracts";
import { averageMetric, normalizedBars, recentMetricSeries, trendText } from "./metrics";

const goalLabels = {
  weight_management: "体重管理",
  metabolic_health: "代谢健康管理",
  sleep_improvement: "睡眠改善",
};

const statusLabels = {
  normal: "Normal · 正常关注",
  attention: "Attention · 建议关注",
  high_attention: "High attention · 重点关注",
};

function formatMetric(value: number | null, digits = 0): string {
  if (value === null) return "—";
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function dashboardErrorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "暂时无法连接健康服务，请确认本地后端已经启动。";
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [plan, setPlan] = useState<HealthPlan | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const planRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    void fetchDashboardData(controller.signal)
      .then((dashboardData) => setData(dashboardData))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setLoadError(dashboardErrorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  const retryDashboard = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setData(await fetchDashboardData());
    } catch (error) {
      setLoadError(dashboardErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, []);

  const metrics = useMemo(() => {
    const events = data?.events.items ?? [];
    const definitions = [
      { metric: "sleep" as const, label: "平均睡眠", unit: "小时", tone: "sage", digits: 1, sourceNote: "NHANES 聚合参考校准" },
      { metric: "steps" as const, label: "平均步数", unit: "步", tone: "blue", digits: 0, sourceNote: "本地规则生成" },
      { metric: "heart_rate" as const, label: "平均心率", unit: "bpm", tone: "coral", digits: 0, sourceNote: "本地规则生成" },
      { metric: "exercise" as const, label: "运动时间", unit: "分钟", tone: "amber", digits: 0, sourceNote: "NHANES 聚合参考校准" },
    ];
    return definitions.map(({ metric, digits, ...definition }) => ({
      ...definition,
      value: formatMetric(averageMetric(events, metric), digits),
      series: normalizedBars(recentMetricSeries(events, metric, 7)),
    }));
  }, [data]);

  const stepBars = useMemo(
    () => normalizedBars(recentMetricSeries(data?.events.items ?? [], "steps")),
    [data],
  );

  async function generatePlan() {
    setPlanLoading(true);
    setPlanError(null);
    try {
      const nextPlan = await fetchHealthPlan();
      setPlan(nextPlan);
      window.setTimeout(() => planRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    } catch (error) {
      setPlanError(
        error instanceof ApiError
          ? error.message
          : "计划生成失败，请稍后重试。",
      );
    } finally {
      setPlanLoading(false);
    }
  }

  const score = data?.status.score ?? 0;
  const scoreStyle = { "--score": `${score}%` } as CSSProperties;

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="衡康首页">
          <span className="brand-mark">衡</span>
          <span><strong>衡康</strong><small>Metabolic Health Agent</small></span>
        </a>
        <div className={`demo-badge ${data?.system.status === "ok" ? "connected" : ""}`}>
          <span aria-hidden="true" />
          本地演示模式{data?.system.status === "ok" ? " · API 已连接" : ""}
        </div>
      </header>

      <section className="notice" aria-label="演示说明">
        <strong>当前展示合成演示数据。</strong>
        <span>{data?.status.data_notice ?? "没有连接 vivo 手表，不代表任何真人或设备测量，不构成医疗诊断或治疗建议。"}</span>
      </section>

      <div className="dashboard" id="top">
        <section className="intro">
          <div>
            <p className="eyebrow">30 天健康概览</p>
            <h1>今天，从理解自己的节律开始。</h1>
            <p className="intro-copy">我们把睡眠、活动与身体指标整理成清晰趋势，再由 Agent 给出温和、可持续的生活建议。</p>
          </div>
          <div className="profile-chip" aria-label="当前演示用户">
            <span className="avatar">演</span>
            <span>
              <b>{data ? `${data.profile.age} 岁 · ${goalLabels[data.profile.goal]}` : "演示用户"}</b>
              <small>{data ? `${data.profile.height} cm · ${data.profile.weight} kg · BMI ${data.profile.bmi.toFixed(1)}` : "正在载入档案"}</small>
            </span>
          </div>
        </section>

        <section className="system-strip" aria-label="验证链路状态">
          <StatusItem label="FastAPI" value={data?.system.status === "ok" ? "已连接" : "等待连接"} ready={data?.system.status === "ok"} />
          <StatusItem label="Repository" value={data?.system.data_mode === "synthetic_demo" ? "Memory · 演示" : "Database"} ready={data?.system.data_mode === "synthetic_demo"} />
          <StatusItem label="LLM" value="Qwen · Mock" ready />
          <StatusItem label="RAG" value="Mock 文档" ready />
        </section>

        {loadError ? (
          <section className="error-panel" role="alert">
            <p className="eyebrow">连接提示</p>
            <h2>健康服务暂时不可用</h2>
            <p>{loadError}</p>
            <button type="button" onClick={retryDashboard}>重新连接</button>
          </section>
        ) : (
          <>
            <section className="summary-grid" aria-label="健康摘要" aria-busy={loading}>
              <article className={`score-card ${loading ? "loading" : ""}`}>
                <div className="score-ring" style={scoreStyle} role="img" aria-label={`健康管理分数 ${score} 分`}>
                  <div><strong>{loading ? "—" : score.toFixed(1)}</strong><span>/ 100</span></div>
                </div>
                <div className="score-copy">
                  <p className="eyebrow">健康管理状态</p>
                  <h2>{loading ? "正在分析合成数据" : "整体节律已完成分析"}</h2>
                  <p>{loading ? "正在读取最近 30 天的睡眠与活动事件。" : data?.status.observations[0]}</p>
                  <span className="status-pill">{data ? statusLabels[data.status.label] : "等待数据"}</span>
                </div>
              </article>

              <article className="agent-card">
                <p className="eyebrow light">健康 Agent</p>
                <h2>把数据变成今天能做的小事</h2>
                <p>基于合成演示数据、Mock Qwen 与安全规则，生成运动、饮食和睡眠三个维度的参考计划。</p>
                <button type="button" onClick={() => void generatePlan()} disabled={!data || planLoading} aria-busy={planLoading}>
                  {planLoading ? "正在生成安全计划…" : plan ? "重新生成演示计划" : "生成演示健康计划"}
                  {!planLoading && <span aria-hidden="true">→</span>}
                </button>
                {planError && <p className="inline-error" role="alert">{planError}</p>}
              </article>
            </section>

            <section className="metrics" aria-label="核心指标">
              {metrics.map((metric) => (
                <article className={`metric-card ${metric.tone} ${loading ? "loading" : ""}`} key={metric.label}>
                  <span className="metric-dot" aria-hidden="true" />
                  <p>{metric.label}</p>
                  <div><strong>{metric.value}</strong><span>{metric.unit}</span></div>
                  <div className="mini-chart" role="img" aria-label={`${metric.label}最近七次趋势`}>
                    {(metric.series.length ? metric.series : Array.from({ length: 7 }, () => 34)).map((height, index) => (
                      <i className={loading ? "placeholder" : ""} key={index} style={{ height: `${height}%` }} />
                    ))}
                  </div>
                  <small>{data ? `${metric.sourceNote} · ${data.events.window_days} 天` : "正在载入合成数据"}</small>
                </article>
              ))}
            </section>

            <section className="source-panel" aria-label="演示数据来源说明">
              <div>
                <p className="eyebrow">数据来源</p>
                <h2>公开参考与本地生成严格分开</h2>
              </div>
              <ul>
                <li><strong>人物档案</strong><span>由 NHANES 2015–2018 公开数据中 30–39 岁人群的聚合统计构建，不复制单个参与者。</span></li>
                <li><strong>睡眠与活动</strong><span>使用聚合四分位数校准后生成，仍属于合成数据。</span></li>
                <li><strong>步数与心率</strong><span>由本地规则生成；当前没有 vivo 手表数据，也不声称来自 NHANES。</span></li>
              </ul>
            </section>

            <section className="lower-grid">
              <article className="trend-card">
                <div className="section-heading">
                  <div><p className="eyebrow">活动趋势</p><h2>每日步数</h2></div>
                  <span className="trend-label">{trendText(data?.status.trends.activity)}</span>
                </div>
                <div className="bar-chart" role="img" aria-label={`最近十四天步数${trendText(data?.status.trends.activity)}`}>
                  {(stepBars.length ? stepBars : Array.from({ length: 14 }, () => 36)).map((height, index) => (
                    <span className={loading ? "placeholder" : ""} key={index} style={{ height: `${height}%` }} />
                  ))}
                </div>
                <div className="chart-axis"><span>14 天前</span><span>今天</span></div>
              </article>

              <article className="observation-card">
                <p className="eyebrow">系统观察</p>
                <h2>本周期值得留意</h2>
                <ul>
                  {(data?.status.observations ?? ["正在整理睡眠数据。", "正在整理活动数据。", "正在检查指标完整性。"]).map((observation, index) => (
                    <li key={observation}><span>{String(index + 1).padStart(2, "0")}</span><p>{observation}</p></li>
                  ))}
                </ul>
              </article>
            </section>
          </>
        )}

        {plan && (
          <section className="plan-panel" ref={planRef} aria-live="polite">
            <div className="plan-heading">
              <div><p className="eyebrow">Agent 安全计划</p><h2>适合持续执行的小行动</h2></div>
              <span>Mock Qwen · 本地演示 · {plan.date}</span>
            </div>
            <div className="plan-grid">
              <PlanColumn index="01" title="运动计划" items={plan.exercise_plan} />
              <PlanColumn index="02" title="饮食计划" items={plan.diet_plan} />
              <PlanColumn index="03" title="睡眠计划" items={plan.sleep_plan} />
            </div>
            <div className="plan-reason"><strong>生成依据</strong><p>{plan.reason}</p></div>
          </section>
        )}
      </div>

      <footer><span>Metabolic Health Agent · Local Synthetic Demo</span><span>{data?.status.disclaimer ?? "仅供系统验证，不替代专业医疗意见"}</span></footer>
    </main>
  );
}

function PlanColumn({ index, title, items }: { index: string; title: string; items: string[] }) {
  return (
    <article>
      <span>{index}</span>
      <h3>{title}</h3>
      <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
    </article>
  );
}

function StatusItem({ label, value, ready }: { label: string; value: string; ready: boolean }) {
  return (
    <article>
      <span className={ready ? "ready" : ""} aria-hidden="true" />
      <div><small>{label}</small><strong>{value}</strong></div>
    </article>
  );
}
