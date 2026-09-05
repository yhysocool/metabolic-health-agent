# 手机本地健康数据手动同步

## 当前能力

衡康 Android App 可以读取最近 1000 个本地健康快照，将其中状态为 PASS
且包含真实数值的观测转换为稳定记录 ID，并手动上传到
POST /api/integrations/vivo/sync。

同一天的步数、距离和活动卡路里使用稳定日记录 ID；相同来源时间的心率、
SpO2 和压力也使用稳定记录 ID。重复上传由服务器计入 unchanged，不会产生
重复健康事件。NO_DATA、DENIED、UNSUPPORTED 和 ERROR 不会被伪装成数值
记录。

## 本地联调

后端默认关闭 vivo 同步入口。联调时通过环境变量启用，并使用长度至少 32
字符的临时测试令牌：

    $env:MHA_VIVO_SYNC_ENABLED = "true"
    $env:MHA_VIVO_SYNC_TOKEN = "替换为至少32字符的临时测试令牌"
    uvicorn app.main:app --host 0.0.0.0 --port 8000

真机与电脑处于同一受信任 WLAN 时，在 App 的“同步与 AI”中填写电脑局域网
地址。同步令牌只保留在当前 App 运行内存中，关闭 App 后需要重新输入。

## 公网限制

App 会拒绝向公网 HTTP 地址上传健康数据。阿里云服务器必须完成 HTTPS 或
受控 VPN 配置后才能接收真实健康数据。公网只开放 443；FastAPI 监听
127.0.0.1:18080，PostgreSQL 监听 127.0.0.1:5432。

## 当前边界

本阶段提供手动同步和服务器幂等回执。持久化待同步队列、WorkManager 后台
重试、分析任务领取以及报告回传属于后续阶段。服务器尚未部署数据库和 HTTPS
入口时，不要向 121.41.48.196 发送真实健康数据。
