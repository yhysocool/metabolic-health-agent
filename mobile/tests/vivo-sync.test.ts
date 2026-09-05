import assert from "node:assert/strict";
import test from "node:test";

import {
  buildVivoSyncRequest,
  parseVivoPairingPayload,
  type StoredVivoSnapshot,
} from "../src/data/vivo-sync.ts";
import type {
  VivoHealthObservation,
  VivoHealthSnapshot,
  VivoStoredObservation,
} from "../src/native/health-provider.ts";

function storedSnapshot(
  id: number,
  readAt: number,
  steps: number,
  spo2Status: "PASS" | "NO_DATA" = "PASS",
): StoredVivoSnapshot {
  const observations: VivoHealthObservation[] = [
    {
      metricType: "steps",
      source: "vivo_assistant_step_provider",
      sourceDevice: "vivo_health_provider",
      measuredAt: readAt,
      startTime: readAt,
      value: steps,
      unit: "step",
      status: "PASS",
      rawSource: "step",
      syncedAt: readAt,
    },
    {
      metricType: "spo2",
      source: "vivo_private_health_provider",
      sourceDevice: "vivo_health_provider",
      measuredAt: 1_788_454_800_000,
      startTime: 1_788_454_800_000,
      value: 94,
      unit: "%",
      status: spo2Status,
      rawSource: "saO2Value",
      syncedAt: readAt,
    },
  ];
  const payload = {
    readAtEpochMs: readAt,
    activity: { day: "2026-09-04" },
    privateHealth: { sleep: {} },
    observations,
  } as unknown as VivoHealthSnapshot;
  return { id, readAt, status: "PASS", payload, syncedAt: readAt };
}

function storedObservation(id: number, measuredAt: number, value: number): VivoStoredObservation {
  return {
    id,
    sessionId: "session-" + id,
    metricType: "spo2",
    source: "vivo_local_health_provider",
    sourceDevice: "vivo_health_provider",
    measuredAt,
    startTime: measuredAt,
    endTime: measuredAt,
    value,
    unit: "%",
    status: "PASS",
    rawSource: "saO2Value",
    syncedAt: measuredAt + 1_000,
    uploadedAt: null,
  };
}

test("同一天活动和相同来源时间的生命体征生成稳定记录 ID", async () => {
  const request = await buildVivoSyncRequest(
    [
      storedSnapshot(1, 1_788_455_000_000, 100),
      storedSnapshot(2, 1_788_455_060_000, 120),
    ],
    "demo-user",
    "device-id",
  );

  assert.equal(request.records.length, 2);
  assert.equal(request.records.find((item) => item.metric === "steps")?.value, 120);
  assert.equal(request.records.find((item) => item.metric === "spo2")?.value, 94);
  assert.ok(request.records.every((item) => item.record_id.startsWith("vivo-")));
});

test("非 PASS 观测不会伪装成可上传数值", async () => {
  const request = await buildVivoSyncRequest(
    [storedSnapshot(1, 1_788_455_000_000, 100, "NO_DATA")],
    "demo-user",
    "device-id",
  );

  assert.deepEqual(request.records.map((item) => item.metric), ["steps"]);
});

test("本地观察记录会并入上传批次并保留每个测量时间点", async () => {
  const request = await buildVivoSyncRequest(
    [storedSnapshot(1, 1_788_455_000_000, 100, "NO_DATA")],
    "demo-user",
    "device-id",
    [
      storedObservation(11, 1_788_454_800_000, 94),
      storedObservation(12, 1_788_454_860_000, 95),
    ],
  );

  assert.equal(request.records.length, 3);
  assert.deepEqual(
    request.records.filter((item) => item.metric === "spo2").map((item) => item.value),
    [94, 95],
  );
});

test("设备绑定二维码载荷只解析一次性绑定码", () => {
  const parsed = parseVivoPairingPayload(
    "healthevent://pair?code=one-time-code&user_id=demo-user",
  );

  assert.deepEqual(parsed, { code: "one-time-code", userId: "demo-user" });
  assert.deepEqual(parseVivoPairingPayload("plain-code"), { code: "plain-code" });
});
