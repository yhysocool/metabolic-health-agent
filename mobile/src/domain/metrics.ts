import type { HealthEvent, HealthMetric } from "./contracts";

export function averageMetric(events: HealthEvent[], metric: HealthMetric): number | null {
  const values = events.filter((event) => event.metric === metric).map((event) => event.value);
  if (values.length === 0) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

export function recentMetricSeries(
  events: HealthEvent[],
  metric: HealthMetric,
  limit = 7,
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
  return values.map((value) => 30 + ((value - minimum) / spread) * 68);
}
