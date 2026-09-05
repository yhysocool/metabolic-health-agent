# vivo 设备一次性绑定方案

## 目标

普通用户不接触服务器全局同步令牌。管理员为某个用户生成一次性绑定载荷，用户只需让手机系统相机扫描二维码；App 在本机生成 Android Keystore 设备密钥，绑定成功后自动采集和上传。

## 身份边界

- `MHA_VIVO_ENROLLMENT_ADMIN_TOKEN` 只存在服务器管理员环境中，用于生成和撤销设备。
- 一次性绑定码默认 10 分钟有效且只能消费一次。
- App 在 Android Keystore 中生成 P-256 私钥，服务器只保存对应公钥。
- 服务端向设备返回随机设备级同步凭据；App 立即将其加密保存到 Android Keystore，不在界面回显。
- 同步凭据只允许对应的 `user_id` 和 `device_id` 上传，服务端保存凭据摘要，可单独撤销设备。
- 旧的 `MHA_VIVO_SYNC_TOKEN` 仅用于兼容旧版/迁移，不得写入源码、前端构建产物或 APK。

## 管理员生成绑定载荷

服务端迁移到 `20260904_0005` 后，设置同步开关和独立管理员凭据。以下命令只在管理员终端执行，不要把响应内容粘贴到聊天、日志或 Git：

~~~powershell
$headers = @{ Authorization = "Bearer " + $env:MHA_VIVO_ENROLLMENT_ADMIN_TOKEN }
$body = @{ user_id = "00000000-0000-0000-0000-000000000001"; expires_in_minutes = 10 } | ConvertTo-Json
$response = Invoke-RestMethod `
  -Method Post `
  -Uri "https://121.41.48.196/api/integrations/vivo/enrollment-codes" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
$response.payload
~~~

将命令输出的 `payload` 转成二维码并展示在管理员电脑上。二维码内容类似 `healthevent://pair?...`，只含短期绑定码，不含长期同步凭据。手机系统相机扫码后会唤起衡康；如果系统相机未自动唤起，可将二维码内容粘贴到 App 的绑定输入框。

## App 端流程

1. 打开“同步与 AI”。
2. 扫描一次性设备绑定二维码。
3. App 通过 HTTPS 调用 `/api/integrations/vivo/devices/enroll`。
4. App 生成并保留 Keystore 私钥，签名证明绑定码持有权。
5. 服务端返回设备级凭据，App 自动配置 JobScheduler 和自动采集服务。
6. 后续网络恢复、应用进程重启或手机重启时，系统任务使用本机凭据自动补传。

## 接口

~~~text
POST  /api/integrations/vivo/enrollment-codes       管理员生成一次性绑定载荷
POST  /api/integrations/vivo/devices/enroll         App 消费绑定码并注册设备
DELETE /api/integrations/vivo/devices/{device_id}   管理员撤销单台设备
POST  /api/integrations/vivo/sync                   设备级或旧版令牌上传
GET   /api/integrations/vivo/status/{user_id}       设备级或旧版令牌查询
~~~

## 部署验收

1. 执行 `alembic upgrade head`。
2. 安装 `requirements-server.txt` 中的 `cryptography`。
3. 设置 `MHA_VIVO_SYNC_ENABLED=true` 和独立的 `MHA_VIVO_ENROLLMENT_ADMIN_TOKEN`。
4. 用管理员凭据生成一次绑定载荷。
5. 真机扫码绑定，确认 App 显示“设备绑定成功”。
6. 检查同步接口能写入绑定用户，换用户或换设备 ID 会返回 403。
7. 撤销设备后，原设备凭据应返回 401。
