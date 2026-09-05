# vivo 数据尽量完整采集改造

## 本次已接入

衡康 Android App 继续使用已经验证的 vivo 本地 Provider，不依赖 vivo Health Kit，也不修改 vivo 健康 App。

- 活动：步数、距离、活动卡路里，以及 Provider 返回的其他活动字段。
- 睡眠：入睡、起床、总时长、夜间睡眠、午睡、浅睡、深睡、REM、清醒时长、睡眠评分、深睡连续性、清醒次数和清醒片段时长。
- 生命体征：最新心率、血氧、压力及异常标记。
- 原始字段：睡眠 Provider 列、生命体征 `MYSELF_DATA` 全部 JSON 字段、活动 Provider 全部 Bundle 字段都会保留，避免未知字段被静默丢弃。
- 统一观测：上述已识别字段会输出 `metricType/source/sourceDevice/measuredAt/startTime/endTime/value/unit/status/rawSource/syncedAt`。

## 持久化策略

- `vivo_overnight_health.db`：继续保存带真实 Provider 时间戳的 SpO₂ 点，并按 `metric_type + source_device + measured_at` 去重。
- `vivo_health_snapshots.db`：保存完整健康快照；去除读取时间和同步时间后计算指纹，只保存数据内容发生变化的快照。
- `getHealthHistory`：原生插件新增历史快照读取接口，后续可接入 FastAPI/HealthRepository。

## 明确限制

1. Provider 只返回最新点时，App 不能凭空恢复历史序列；夜间完整序列取决于 vivo 健康 App/Provider 实际产生的数据点。
2. 当前没有公开的 vivo BlueOS SpO₂ 硬件采样频率设置接口，60 秒是查询间隔，不是手表传感器采样间隔。
3. 不采集 PPG 原始波形，不修改手表固件，不 Root，不自动化抓取 vivo 健康页面。
4. Android 后台和厂商省电策略可能中断前台服务；服务状态、Provider 时间戳和快照保存结果都会明确记录。
5. 字段缺失返回 `UNSUPPORTED`，暂时没有数据返回 `NO_DATA`，权限问题返回 `DENIED`，不会填零或使用旧数据冒充新数据。

## 真机验证

1. 在电脑执行 `npm run android:sync`。
2. 使用 Android Studio 或本机 Gradle 生成新的 Debug APK。
3. 安装后确认 vivo 私有 Provider 权限仍为真实 `granted=true`。
4. 打开衡康，点击“立即读取一次”，检查“统一采集观测”和原始字段数量。
5. 点击“开始夜间采集”，保持手表佩戴并记录至少 30 分钟；检查血氧点数、完整快照数、最近 Provider 时间。
6. 测试结束后通过 `getHealthHistory` 导出最近快照，计算各指标真实刷新间隔。

