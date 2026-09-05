# 本地合成数据体验版执行与验证说明

## 1. 当前范围

本阶段只在开发电脑和同一局域网内的个人设备验证，不提交应用商店，不办理
APP 备案，不连接 vivo Health Kit，也不采集真人健康数据。

当前目标是验证完整链路：

```text
NHANES 聚合参考 → SyntheticHealthAdapter → HealthEvent
→ Repository → HealthService / Agent → Dashboard
```

## 2. 数据边界

- 演示人物是合成人物，不对应任何 NHANES 参与者。
- 睡眠和活动数据由 NHANES 2015–2016、2017–2018 公开数据的 30–39 岁
  聚合四分位数校准。
- 步数和静息心率不在本项目 NHANES 提取字段中，由本地规则生成。
- 所有事件的 `source` 都是 `synthetic`，并携带 `provenance.is_synthetic=true`。
- Dashboard 持续显示“没有连接 vivo 手表”。
- 当前健康分数和 Agent 计划只用于工程验证，不构成诊断或治疗建议。

聚合参考文件：
`data/reference/nhanes_adult_30_39_reference_v1.json`。

## 3. 电脑本地验证

终端 1：

```powershell
cd E:\HealthEvent\metabolic-health-agent
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

终端 2：

```powershell
cd E:\HealthEvent\metabolic-health-agent\web
npm run dev
```

访问 <http://localhost:3000>。

## 4. 同一局域网手机验证

本方式只是在手机浏览器中验证响应式 Dashboard，不是 APK，也不会读取手表。

1. 确保电脑和手机连接同一个可信 Wi-Fi。
2. 用 `ipconfig` 查看电脑无线网卡的 IPv4 地址，例如 `192.168.1.20`。
3. 后端监听局域网地址：

```powershell
cd E:\HealthEvent\metabolic-health-agent
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

4. 前端监听局域网地址：

```powershell
cd E:\HealthEvent\metabolic-health-agent\web
npm run dev:lan
```

5. 在手机浏览器访问 `http://<电脑IPv4>:3000`。

前端会自动把 API 地址解析为 `http://<电脑IPv4>:8000`。`.env.example` 中的
开发 CORS 正则只允许 localhost 和 RFC1918 私有 IPv4 网段，不应复制到公网环境。
如果 Windows 防火墙弹出提示，只允许“专用网络”，测试后可以关闭两个进程。

## 5. 验收标准

- `/healthz` 返回 `data_mode=synthetic_demo`。
- 30 天接口返回 120 条事件，来源全部为 `synthetic`。
- 睡眠和活动事件标记 `reference_dataset=NHANES`。
- 步数和心率事件不标记为 NHANES 数据。
- 页面在电脑和手机宽度下持续显示合成数据及未连接 vivo 的提示。
- Agent 计划可以生成，并继续标记 Mock Qwen 与非诊断性边界。
- 后端测试、前端类型检查、Lint 和生产构建全部通过。

## 6. Android 本地体验

当前已提供可安装的 Debug APK。它与浏览器版使用相同的合成数据 API，不读取
vivo 手表或手机健康数据。构建、安装与验收步骤见
[`ANDROID_LOCAL_DEBUG_EXECUTION.md`](ANDROID_LOCAL_DEBUG_EXECUTION.md)。

## 7. 暂不实施

- vivo、Polar 或其他设备授权与真实同步。
- 用户注册、真人手动录入和云端长期存储。
- Release APK/AAB、正式签名、应用商店资料和 APP 备案。
- 真实 Qwen 调用和面向公众的医疗健康服务。
