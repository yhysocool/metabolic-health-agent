# 衡康健康数据与同步契约

> 当前契约用于 vivo 本地 Provider → Android → FastAPI。
> 它是项目自有中间格式，不冒充 vivo 官方 DTO。

## 1. 数据状态

设备读取结果必须区分：

~~~text
PASS
NO_DATA
DENIED
UNSUPPORTED
ERROR
~~~

只有 PASS 且包含真实数值的记录进入服务器健康事件表。其他状态应在手机侧快照、诊断或状态中保留，不能伪造数值上传。

规则：

- NO_DATA 不能写成 0。
- DENIED 不能使用旧值代替。
- UNSUPPORTED 不能静默切换到其他来源。
- ERROR 必须保留错误信息和时间。
- readAt 表示桥接读取时间，不等于 Provider 原始测量时间。

## 2. 手机侧观测字段

手机侧使用 camelCase：

~~~text
metricType
source
sourceDevice
measuredAt
startTime
endTime
value
unit
status
rawSource
syncedAt
~~~

快照还可以包含：

- providerDiagnostics
- providerColumns
- rawFields
- spo2History
- spo2HistoryCount
- spo2AccessMode
- spo2CoverageMessage
- persistence

原始字段只用于诊断和追溯，不得绕过统一状态和时间校验直接进入业务分析。

## 3. 当前支持的指标

第一阶段只处理当前代码已经稳定识别的指标：

### 日活动

~~~text
steps
distance
calories
~~~

### 睡眠

~~~text
sleep
sleep_total_duration
sleep_night_duration
sleep_nap_duration
sleep_light_duration
sleep_deep_duration
sleep_rem_duration
sleep_awake_duration
sleep_score
sleep_deep_continuity
sleep_awake_episode_count
sleep_awake_episode_duration
~~~

### 生命体征

~~~text
heart_rate
heart_rate_resting
spo2
stress
exercise
~~~

如果 Provider 返回未列入上述清单的字段，先保留在诊断信息中，不为追求字段数量而扩大统一业务范围。

## 4. 服务器同步字段

服务器请求使用 snake_case：

~~~json
{
  "batch_id": "uuid",
  "user_id": "user-id",
  "device_id": "device-id",
  "cursor": "read-cursor",
  "records": [
    {
      "record_id": "vivo-sha256-id",
      "metric": "spo2",
      "value": 96.0,
      "unit": "%",
      "source": "vivo_local_health_provider",
      "source_device": "vivo_health_provider",
      "measured_at": "2026-09-04T00:00:00.000Z",
      "start_time": "2026-09-04T00:00:00.000Z",
      "end_time": null,
      "status": "PASS",
      "raw_source": "vivo_bridge",
      "synced_at": "2026-09-04T00:01:00.000Z"
    }
  ]
}
~~~

说明：

- records 一批最多 1000 条。
- 所有有意义的时间戳必须包含时区。
- App 侧将 camelCase 映射为服务器 snake_case。
- 服务器只接受 PASS 记录写入健康事件表。
- device_id 进入服务器同步状态时只保存 SHA-256 摘要。

## 5. 时间规则

- 活动按设备本地日保存，但上传为带时区的 ISO 8601 时间。
- 睡眠必须保存真实 start_time 和 end_time，允许跨自然日。
- 心率、SpO₂、压力优先使用 Provider 原始测量时间。
- 没有 Provider 原始时间时，必须在诊断中标记时间来源，不得把读取时间伪装成测量时间。
- 后端统一按带时区时间处理，展示时再转换为用户时区。

## 6. 幂等和游标

当前手机侧稳定 ID 由以下信息构造：

~~~text
source | sourceDevice | metric | source-time-identity
~~~

再计算 SHA-256：

~~~text
record_id = vivo-<sha256>
~~~

时间身份规则：

- 活动：设备本地日期。
- 睡眠：来源睡眠日，缺失时使用睡眠开始时间。
- 心率、SpO₂、压力：优先使用 Provider 测量时间。

同步语义：

- cursor 表示手机本地快照读取游标。
- App 只读取游标之后的快照。
- 服务器依据 record_id 返回 created、updated、unchanged。
- 重复同步不应增加数据库记录总数。
- 当前日活动值变化可以更新同一稳定记录。

## 7. SpO₂ 特别说明

快照数、Provider 返回行数和有效 SpO₂ 点数是三个不同概念：

~~~text
快照数 ≠ Provider 行数 ≠ 有效 SpO₂ 点数
~~~

夜间采集必须记录：

- spo2HistoryCount
- 实际保存点数
- Provider 返回行数
- 最新 Provider 时间
- 最早 Provider 时间
- 采集状态
- 数据覆盖说明

如果 Provider 只返回最新单点，轮询只能证明“读取到最新值”，不能制造完整历史序列。报告中必须明确覆盖不足。

## 8. 报告边界

未来服务器报告只做：

- 覆盖率和时间范围。
- 指标数量、最新值和趋势摘要。
- 数据缺失、权限和 Provider 能力提示。
- SpO₂ 序列是否足够进行研究性分析的质量判断。

不做：

- 疾病诊断。
- 医疗风险确诊。
- 用 NHANES 聚合参照替代个人临床检查。
- 在数据不足时输出确定性结论。
