# vivo Watch GT 2 接入执行文档

## 当前结论

推荐链路是：

```text
vivo Watch GT 2
  → vivo 健康 APP
  → vivo Health Kit（用户逐项授权）
  → Android 桥接 APP
  → HTTPS 增量同步 API
  → VivoAdapter
  → HealthEvent / 同步状态
  → Dashboard 与 Agent
```

当前已经完成后端可验证骨架，不读取真实手表数据，也未引用未经确认的 SDK 类名。进入真实接入前，必须取得 vivo Health Kit 的 SDK、接口文档、应用包名与签名要求，并完成用户授权页面。

官方资料：

- [vivo Health Kit 产品页](https://developers.vivo.com/product/d/healthKit)
- [vivo Watch GT 2 参数页](https://www.vivo.com.cn/vivo/param/vivowatchgt2)
- [vivo 健康隐私政策](https://health-h5.vivo.com.cn/doc/v3.0/privacy.html)
- 官方合作咨询邮箱：`iotpartners@vivo.com`

## 已完成：阶段 1（无真实数据验证）

后端现已具备：

1. 项目自有的 `VivoBridgeRecord` 中间契约，与厂商 SDK DTO 解耦。
2. 步数、心率、睡眠时长和运动时长的单位归一化。
3. `(user_id, source, source_record_id)` 唯一约束和幂等更新。
4. 事件写入与同步游标在同一仓储事务中提交。
5. 设备原始标识只做 SHA-256 摘要后保存。
6. 同步接口默认关闭；启用后仍要求至少 32 字符的 Bearer 验证令牌。
7. Mock/fixture 测试覆盖首次写入、重复回放、记录变更、状态查询和接口保护。

当前支持的桥接指标只有：

- `steps`：统一为 `step`
- `heart_rate`：统一为 `bpm`
- `sleep`：统一为 `hour`
- `exercise`：统一为 `minute`

血氧必须在统一模型新增独立的 `blood_oxygen` 指标后再接入，不能映射为 `blood_glucose`。

## 本地 fixture 验证

不要把真实设备 ID、真实健康数据或生产令牌用于本阶段。

在一个 PowerShell 会话中生成临时令牌，并以隐藏子进程启动 API：

```powershell
cd E:\HealthEvent\metabolic-health-agent
$fixtureToken = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
$env:MHA_VIVO_SYNC_ENABLED = "true"
$env:MHA_VIVO_SYNC_TOKEN = $fixtureToken
.\.venv\Scripts\Activate.ps1
$apiProcess = Start-Process `
  -FilePath .\.venv\Scripts\python.exe `
  -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "8000" `
  -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 2
```

继续在同一 PowerShell 会话构造虚构请求：

```powershell
$headers = @{ Authorization = "Bearer $fixtureToken" }
$body = @{
  user_id = "00000000-0000-0000-0000-000000000001"
  device_id = "fixture-watch-001"
  cursor = "fixture-cursor-001"
  records = @(
    @{
      record_id = "fixture-steps-20260824"
      metric = "steps"
      value = 8200
      unit = "count"
      start_time = "2026-08-24T08:00:00+08:00"
    },
    @{
      record_id = "fixture-sleep-20260824"
      metric = "sleep"
      value = 450
      unit = "minute"
      start_time = "2026-08-23T23:00:00+08:00"
      end_time = "2026-08-24T06:30:00+08:00"
    }
  )
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/integrations/vivo/sync `
  -Headers $headers -ContentType "application/json" -Body $body

Invoke-RestMethod `
  -Uri http://localhost:8000/api/integrations/vivo/status/00000000-0000-0000-0000-000000000001 `
  -Headers $headers
```

把同一请求重复发送一次，预期首次响应 `created=2`，第二次响应 `unchanged=2`，事件总数不增加。把同一个 `record_id` 的值修改后再次提交，预期 `updated=1`。

验证结束后停止子进程并清理当前会话变量：

```powershell
Stop-Process -Id $apiProcess.Id
Remove-Item Env:MHA_VIVO_SYNC_ENABLED, Env:MHA_VIVO_SYNC_TOKEN
$fixtureToken = $null
```

不要把生成的令牌写入 `.env.example`、Git、前端代码或 Android 安装包。

## 阶段 2：申请并确认 vivo 接入材料

需要用户完成：

1. 在 vivo 开发者平台申请 Health Kit 能力。
2. 明确 Android 应用包名、签名证书指纹和测试账号。
3. 获取与当前 SDK 版本匹配的接入文档、依赖坐标和数据类型清单。
4. 确认 Watch GT 2 数据是由 vivo 健康 APP 汇聚后授权读取，而不是由后端直连手表。
5. 确认读取权限、授权撤销、历史回看窗口、增量标识、频率限制和数据删除要求。

若平台需要商务开通，可通过官方产品页提供的 `iotpartners@vivo.com` 联系。申请材料到位前，不应猜测 SDK 方法或提交 Android 生产代码。

## 阶段 3：Android 桥接 APP

材料确认后再建立独立 Android 模块，职责只包括：

1. 展示数据用途、最小权限范围和撤销入口。
2. 调用官方 Health Kit 授权与读取接口。
3. 将官方对象映射为本项目的 `VivoBridgeRecord`。
4. 使用来源稳定 ID；如果官方无记录 ID，按经评审的字段组合生成确定性 ID。
5. 在设备本地保存官方增量标识，分批上传，成功后才推进本地游标。
6. 使用用户登录后的短期访问令牌，不使用当前 fixture 共享令牌。
7. 遇到撤权、离线、部分失败和限流时可恢复，不静默丢数据。

## 阶段 4：联调与上线门禁

至少完成以下验收后才可启用真实数据：

- 单位、时区、跨午夜睡眠和夏令时契约测试。
- 重复、迟到、修订、删除记录的同步测试。
- 用户撤权后停止拉取并支持服务端删除。
- HTTPS、用户鉴权、令牌轮换、限流和审计日志。
- 日志不包含健康值、原始设备 ID、授权令牌和 SDK 原始响应。
- 数据最小化、留存期限、隐私说明和用户导出/删除流程通过评审。
- Dashboard 明确区分 Mock 与 vivo 来源。
- Agent 输出继续经过非诊断声明和确定性安全门禁。

## 暂不执行的事项

- 不连接真实 vivo 账号或手表。
- 不上传真实健康记录。
- 不把 Qwen Key 用于设备同步鉴权。
- 不实现血氧、压力或其他尚未进入统一指标模型的数据。
- 不把共享 fixture 令牌作为移动端生产身份方案。
