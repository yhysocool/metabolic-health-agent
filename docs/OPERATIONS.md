# 衡康项目操作与恢复手册

> 本文件只记录操作方法和路径，不记录任何真实令牌、密码或私钥。

## 1. 本地 Android 构建

当前用户环境已验证可用的构建组合：

- Java：D:\SoftWare\java
- Gradle：E:\software\gradle\gradle-8.13-bin\gradle-8.13\bin\gradle.bat
- ADB：E:\software\SDK\platform-tools\adb.exe
- Android 工程：E:\HealthEvent\metabolic-health-agent\mobile\android

PowerShell：

~~~powershell
cd E:\HealthEvent\metabolic-health-agent\mobile\android
$env:JAVA_HOME = "D:\SoftWare\java"
$env:Path = "$env:JAVA_HOME\bin;$env:Path"

& "E:\software\gradle\gradle-8.13-bin\gradle-8.13\bin\gradle.bat" --stop
& "E:\software\gradle\gradle-8.13-bin\gradle-8.13\bin\gradle.bat" assembleDebug
~~~

APK：

E:\HealthEvent\metabolic-health-agent\mobile\android\app\build\outputs\apk\debug\app-debug.apk

如果只修改了 Web/Capacitor 代码，先在 mobile 目录执行：

~~~powershell
cd E:\HealthEvent\metabolic-health-agent\mobile
npm run android:sync
~~~

## 2. 真机安装与连接检查

~~~powershell
$adb = "E:\software\SDK\platform-tools\adb.exe"
$apk = "E:\HealthEvent\metabolic-health-agent\mobile\android\app\build\outputs\apk\debug\app-debug.apk"

& $adb devices
& $adb install -r $apk
~~~

必须看到设备状态为 device。如果是 unauthorized，先在手机上允许 USB 调试；如果没有设备，先检查数据线、USB 模式和开发者选项。

## 3. 自动同步验证

正式用户流程使用一次性设备绑定，不再要求用户输入服务器全局令牌：

1. 管理员使用 `MHA_VIVO_ENROLLMENT_ADMIN_TOKEN` 生成一次性绑定载荷。
2. 将载荷生成二维码，用户用手机系统相机扫描。
3. App 自动生成 Android Keystore 设备密钥并完成绑定。
4. App 自动启用后台采集、JobScheduler 和自动上传。
5. 用户以后无需再次输入同步令牌。

旧版兼容流程仍可在迁移期使用全局 Bearer 令牌，但真实令牌不得写入源码、截图、Git、文档或 APK。

检查 JobScheduler：

~~~powershell
& $adb shell dumpsys jobscheduler | Select-String "com.healthevent.mobile"
~~~

检查 App 日志时只过滤状态和计数，不输出完整请求头：

~~~powershell
& $adb logcat -d -s HealthEvent:V VivoAutoSync:V "*:S"
~~~

如果设备系统没有对应日志标签，以 App 页面显示的“最后尝试、最后成功、最近新增/更新/不变”作为主要证据。

## 4. 服务器健康检查

SSH：

~~~powershell
ssh newserver
~~~

服务器上：

~~~bash
systemctl status healthevent-api.service --no-pager
ss -lntp | grep -E ':(80|443|18080|5432)\b'
curl -fsS https://121.41.48.196/healthz
~~~

预期：

- 公开只使用 80/443。
- FastAPI 只监听 127.0.0.1:18080。
- PostgreSQL 只允许本机访问。
- /healthz 返回正常状态。

服务器项目路径：

~~~text
/opt/healthevent/current
/opt/healthevent/releases/<release>
/opt/healthevent/config/healthevent.env
/srv/healthevent/data/raw
/srv/healthevent/data/normalized
/srv/healthevent/data/reports
/srv/healthevent/logs
~~~

服务器令牌只存在于：

/opt/healthevent/config/healthevent.env

不要执行会把该文件内容输出到聊天或日志的命令。

## 5. 当前接口

~~~text
GET  /healthz
POST /api/integrations/vivo/enrollment-codes
POST /api/integrations/vivo/devices/enroll
DELETE /api/integrations/vivo/devices/{device_id}
POST /api/integrations/vivo/sync
GET  /api/integrations/vivo/status/{user_id}
~~~

绑定码生成和设备撤销需要管理员凭据；设备绑定接口只接受一次性绑定码和 Android Keystore 签名。同步和状态接口接受设备级凭据，迁移期也兼容旧版 Bearer 令牌：

~~~text
Authorization: Bearer <服务器令牌>
~~~

手机使用内置的 HTTPS 根地址，不填写 `/api/...` 路径，不填写 `http://`，不填写 SSH 地址。

## 6. 常见故障定位

| 现象 | 优先检查 |
|---|---|
| App 显示无法连接服务器 | 地址是否为 HTTPS 根地址、证书、443 安全组、Nginx |
| HTTP 401 | 令牌不匹配或令牌被截断 |
| HTTP 403 | 请求方法、Nginx 限制或 CORS 预检配置 |
| HTTP 422 | 记录字段、时间戳、单位或指标枚举不符合契约 |
| HTTP 404 | 路径或服务器版本不对 |
| 同步成功但数量不增加 | 可能是幂等重复，查看 created/updated/unchanged |
| SpO₂ 数量少 | 先检查 Provider 实际返回行数和原始时间戳，不要用快照数代替 SpO₂ 点数 |
| 自动同步不运行 | 检查设备绑定、Keystore 配置、JobScheduler、网络条件和最近错误 |
| App 重装后不能同步 | 重新生成一次性绑定码并绑定；Keystore/应用数据可能已经变化 |

## 7. 部署原则

- 每次服务器发布使用新的 release 目录。
- 不直接修改正在运行的 release。
- 发布前运行测试、导入检查、迁移检查和 Nginx 配置检查。
- 发布后先检查 /healthz，再检查受保护同步/状态接口。
- 不开放 18080、5432、数据库端口或内部调试端口到公网。
- 安全组 80/443 是公网 API 入口；SSH 22 应限制为管理来源，不能长期对全网开放。
