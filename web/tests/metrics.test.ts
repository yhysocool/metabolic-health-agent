import assert from "node:assert/strict";
import test from "node:test";

import { averageMetric, normalizedBars, recentMetricSeries } from "../app/metrics.ts";
import type { HealthEvent } from "../app/contracts.ts";

function event(value: number, day: number): HealthEvent {
  return {
    id: `event-${day}`,
    user_id: "mock-user",
    source: "mock",
    metric: "steps",
    value,
    unit: "step",
    timestamp: `2026-08-${String(day).padStart(2, "0")}T00:00:00Z`,
    provenance: null,
  };
}

test("empty events stay presentation-safe", () => {
  assert.equal(averageMetric([], "sleep"), null);
  assert.deepEqual(recentMetricSeries([], "steps"), []);
  assert.deepEqual(normalizedBars([]), []);
});

test("trend helpers sort, limit and normalize health events", () => {
  const events = [event(8000, 3), event(6000, 1), event(7000, 2)];

  assert.equal(averageMetric(events, "steps"), 7000);
  assert.deepEqual(recentMetricSeries(events, "steps", 2), [7000, 8000]);
  assert.deepEqual(normalizedBars([6000, 7000, 8000]), [34, 65, 96]);
});
