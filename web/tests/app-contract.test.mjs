import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const projectRoot = new URL("../", import.meta.url);

async function source(path) {
  return readFile(new URL(path, projectRoot), "utf8");
}

test("dashboard keeps the synthetic-data boundary visible", async () => {
  const [dashboard, client, layout] = await Promise.all([
    source("app/Dashboard.tsx"),
    source("app/api-client.ts"),
    source("app/layout.tsx"),
  ]);

  assert.match(layout, /衡康 · 本地健康管理体验版/);
  assert.match(layout, /summary_large_image/);
  assert.match(layout, /\/og\.png/);
  assert.match(dashboard, /本地演示模式/);
  assert.match(dashboard, /没有连接 vivo 手表/);
  assert.match(dashboard, /生成演示健康计划/);
  assert.match(dashboard, /不构成医疗诊断或治疗建议/);
  assert.match(dashboard, /Memory · 演示/);
  assert.match(dashboard, /NHANES 2015–2018/);
  assert.match(dashboard, /步数与心率/);
  assert.match(dashboard, /Qwen · Mock/);
  assert.match(client, /window\.location\.hostname/);
  assert.match(client, /\/api\/health\/events\/\$\{DEMO_USER_ID\}\?days=30/);
  assert.match(client, /\/api\/agent\/plan\/\$\{DEMO_USER_ID\}/);
});

test("LAN preview has an explicit development command", async () => {
  const packageJson = JSON.parse(await source("package.json"));
  assert.equal(packageJson.scripts["dev:lan"], "vinext dev --hostname 0.0.0.0");
});

test("starter preview is fully removed", async () => {
  const packageJson = JSON.parse(await source("package.json"));

  assert.equal(packageJson.name, "metabolic-health-agent-web");
  assert.equal(packageJson.dependencies["react-loading-skeleton"], undefined);
  assert.equal(packageJson.dependencies["drizzle-orm"], undefined);
  await assert.rejects(
    access(new URL("app/_sites-preview/SkeletonPreview.tsx", projectRoot)),
  );
  await assert.rejects(
    access(new URL("app/_sites-preview/preview.css", projectRoot)),
  );
});

test("production bundle is generated", async () => {
  await access(new URL("dist/client", projectRoot));
  await access(new URL("dist/server", projectRoot));
  await access(new URL("public/og.png", projectRoot));
});
