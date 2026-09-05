# vivo 夜间血氧采集实验

当前移动端已经加入一个独立的 `VivoOvernightHealth` Capacitor 插件。它的目标是验证：vivo 手机本地健康 Provider 是否会在夜间持续更新带时间戳的血氧观测点。

## 当前实现边界

- 用户在 App 内主动点击“开始夜间采集”后启动 Android 前台服务。
- 服务默认每 60 秒查询一次 `content://com.vivo.health.provider.care/healthCare`。
- 只读取 `MYSELF_DATA.saO2Value` 和 `MYSELF_DATA.saO2TimeStamp`。
- 只有 Provider 时间戳严格前进时才写入本地 SQLite；旧点、重复点、无时间戳点不会被填成新数据。
- 每条有效记录包含 `source`、`sourceDevice`、`metricType`、`measuredAt`、`startTime`、`endTime`、`value`、`unit`、`status`、`rawSource`、`syncedAt`。
- 权限、Provider、Schema、读取异常分别映射到 `DENIED`、`UNSUPPORTED`、`ERROR` 或 `NO_DATA`，不会静默使用合成数据替代。

## 真机验证步骤

1. 重新构建并安装主项目 Debug APK。
2. 仅在本人拥有和控制的 vivo 测试手机上，按既有授权流程授予主 App 的 `com.vivo.health.widget.permission`。
3. 打开 App，先点“立即读取一次”，确认状态和时间戳。
4. 点击“开始夜间采集”，保持前台服务通知存在，关闭系统省电限制对本 App 的影响。
5. 次日点击“停止夜间采集”，记录“已保存点数”、首个时间和最后时间。
6. 如果整晚只有一个时间戳，说明当前 Provider 只提供最新点，不能用于连续 SpO₂ 模型；此时应标记为 `UNSUPPORTED`，不能把轮询次数当成样本数。

## 与模型的关系

采集层先输出真实时间序列，模型层后接入。SomnNET 一类睡眠/血氧研究模型通常需要连续 SpO₂ 波形或高频序列、采样率和缺失标记，不能直接把 vivo 的单个最新点或睡眠摘要输入模型。

第一阶段只验证数据覆盖率：

```text
Provider 原始观测
→ 时间戳去重
→ 本地 SQLite 样本表
→ 会话覆盖率/缺失率
→ 模型适配器（后续）
```

后续接模型前必须确认：实际采样间隔、夜间样本数量、时间戳时区、缺失比例、设备型号，并用公开数据集或带标签数据做离线评估。模型输出只能作为“需要进一步关注的信号”，不能作为疾病诊断。

## 构建和权限注意事项

- 本实现使用 Android 前台服务，不是隐蔽后台抓取；系统通知应保持可见。
- Android 13+ 需要通知权限才能完整显示采集通知；拒绝通知时仍不能把采集当成成功。
- Android 13+ 第一次点击开始采集时会请求通知权限；允许后需要再次点击开始。
- Android 14+ 的健康前台服务还需要系统认可的健康/传感器前置条件；本 APK 声明高采样传感器前置条件，但实际代码不直接读取手机传感器，只读取 vivo Provider。
- App 重装可能清除 vivo 私有 Provider 授权和本地 SQLite 数据，需要重新验证。
- 本阶段没有修改 FastAPI、PostgreSQL 或 LangGraph；模型接入应通过统一 `HealthEvent`/数据源接口完成。
