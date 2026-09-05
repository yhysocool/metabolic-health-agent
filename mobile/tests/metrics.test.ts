import assert from "node:assert/strict";
import test from "node:test";

import type { HealthEvent } from "../src/domain/contracts.ts";
import { averageMetric, normalizedBars, recentMetricSeries } from "../src/domain/metrics.ts";

function event(value: number, day: number): HealthEvent {
  return {
    id: `event-${day}`,
    user_id: "demo-user",
    source: "synthetic",
    metric: "steps",
    value,
    unit: "step",
    timestamp: `2026-08-${String(day).padStart(2, "0")}T00:00:00Z`,
    provenance: null,
  };
}

test("移动端指标计算保持确定性", () => {
  const events = [event(8000, 3), event(6000, 1), event(7000, 2)];
  assert.equal(averageMetric(events, "steps"), 7000);
  assert.deepEqual(recentMetricSeries(events, "steps", 2), [7000, 8000]);
  assert.deepEqual(normalizedBars([6000, 7000, 8000]), [30, 64, 98]);
});

test("空事件不生成伪指标", () => {
  assert.equal(averageMetric([], "sleep"), null);
  assert.deepEqual(recentMetricSeries([], "sleep"), []);
  assert.deepEqual(normalizedBars([]), []);
});
