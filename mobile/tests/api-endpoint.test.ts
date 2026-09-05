import assert from "node:assert/strict";
import test from "node:test";

import { assertSecureHealthUploadUrl } from "../src/data/api-endpoint.ts";

test("健康数据允许 HTTPS 公网地址", () => {
  assert.equal(
    assertSecureHealthUploadUrl("https://121.41.48.196/"),
    "https://121.41.48.196",
  );
});

test("健康数据允许局域网 HTTP 联调", () => {
  assert.equal(
    assertSecureHealthUploadUrl("http://192.168.1.20:8000/"),
    "http://192.168.1.20:8000",
  );
});

test("健康数据拒绝公网明文 HTTP", () => {
  assert.throws(
    () => assertSecureHealthUploadUrl("http://121.41.48.196:18080"),
    /必须使用 HTTPS/,
  );
});
