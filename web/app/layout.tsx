import type { Metadata } from "next";
import "./globals.css";

const siteUrl = process.env.SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "衡康 · 本地健康管理体验版",
  description: "使用明确标识的合成数据验证健康分析与 Agent 计划链路。",
  openGraph: {
    type: "website",
    locale: "zh_CN",
    title: "衡康 · 本地健康管理体验版",
    description: "使用明确标识的合成数据验证健康分析与 Agent 计划链路。",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "衡康本地健康管理体验版" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "衡康 · 本地健康管理体验版",
    description: "使用明确标识的合成数据验证健康分析与 Agent 计划链路。",
    images: ["/og.png"],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
