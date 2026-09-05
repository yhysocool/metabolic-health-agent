import type { HealthEvent, HealthMetric, TrendDirection } from "./contracts";

export function averageMetric(events: HealthEvent[], metric: HealthMetric): number | null {
  const values = events.filter((event) => event.metric === metric).map((event) => event.value);
  if (values.length === 0) return null;
  return values.reduce((total, value) => total + value, 0) / values.length;
}

export function recentMetricSeries(
  events: HealthEvent[],
  metric: HealthMetric,
  limit = 14,
): number[] {
  return events
    .filter((event) => event.metric === metric)
    .sort((left, right) => left.timestamp.localeCompare(right.timestamp))
    .slice(-limit)
    .map((event) => event.value);
}

export function normalizedBars(values: number[]): number[] {
  if (values.length === 0) return [];
  const maximum = Math.max(...values);
  const minimum = Math.min(...values);
  const spread = maximum - minimum || 1;
  return values.map((value) => 34 + ((value - minimum) / spread) * 62);
}

export function trendText(direction: TrendDirection | undefined): string {
  if (direction === "increase") return "上升趋势";
  if (direction === "decrease") return "下降趋势";
  return "保持稳定";
}

