import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.healthevent.mobile",
  appName: "衡康",
  webDir: "dist",
  server: {
    androidScheme: "https",
  },
  android: {
    // 本地调试需要从 https://localhost WebView 调用电脑上的 HTTP API。
    // 对外发布前必须切换 HTTPS API 并删除该配置。
    allowMixedContent: true,
  },
};

export default config;
