# 衡康项目当前状态

> 更新日期：2026-09-04
> 当前主线：验证重复同步去重、持续自动上传、服务器健康分析、报告返回 App。

## 1. 当前结论

vivo 本地 Provider 真机读取已经验证成功，数据可以进入衡康 App；服务器 HTTPS 同步链路已经验证成功。当前仍缺少两项闭环：

1. 最新 Android 自动上传代码还没有完成用户环境中的完整 Gradle APK 构建和 JobScheduler 真机验证。
2. 服务器数据质量/趋势报告接口以及 App 报告展示尚未完成。

## 2. 已完成并验证

### vivo 真机读取

- 已在本人控制的 vivo 测试手机上验证本地 Provider。
- 已读取到步数、距离、卡路里。
- 私有 Provider 授权后已读取到睡眠、心率、SpO₂ 和压力的部分数据。
- Android App 已有健康快照、历史快照和夜间采集界面。
- 夜间 SpO₂ 仍然受 vivo Provider 实际返回粒度限制，快照数量不等于有效 SpO₂ 点数，不能宣称已获得完整连续序列。

### 同步接口与设备绑定

- 服务端版本基线为 0.6.0。
- HTTPS 公网入口使用 Nginx 80/443。
- 内部 FastAPI 只监听 127.0.0.1:18080。
- 已有接口：
  - GET /healthz
  - POST /api/integrations/vivo/enrollment-codes
  - POST /api/integrations/vivo/devices/enroll
  - DELETE /api/integrations/vivo/devices/{device_id}
  - POST /api/integrations/vivo/sync
  - GET /api/integrations/vivo/status/{user_id}
- 新 App 通过一次性绑定码注册 Android Keystore P-256 公钥，获得仅属于绑定设备的同步凭据。
- 同步接口和状态接口接受设备级凭据；迁移期兼容旧版全局 Bearer 令牌。
- 管理员绑定凭据只保存在服务器环境中，普通用户不接触全局令牌。
- Nginx CORS 预检已修复；无令牌或错误令牌不能写入数据。

### 去重

此前真机同步验证结果：

- 第一次同步：新增 38 条。
- 第二次同步：新增 0 条，更新 3 条，不变 35 条。
- 数据库总记录保持 38 条。
- record_id 重复分组为 0。
- 空来源记录 ID 为 0。

3 条更新代表活动值等当前日数据变化，不是重复记录。

## 3. 已写入源码但待完整验证

以下 Android 模块已经写入主工程：

- mobile/android/app/src/main/java/com/healthevent/mobile/vivo/VivoAutoSyncStore.java
- mobile/android/app/src/main/java/com/healthevent/mobile/vivo/VivoSyncPayloadBuilder.java
- mobile/android/app/src/main/java/com/healthevent/mobile/vivo/VivoAutoSyncClient.java
- mobile/android/app/src/main/java/com/healthevent/mobile/vivo/VivoAutoSyncJobService.java

相关改动：

- 使用 Android Keystore 加密保存同步令牌。
- 只接受 HTTPS 根地址。
- 默认最小自动同步间隔为 15 分钟。
- 使用同步游标和稳定 record_id。
- 网络不可用时由 JobScheduler 等待网络并按系统策略重试。
- 不在日志或状态接口返回令牌。
- 设备绑定码默认 10 分钟有效且只能使用一次；设备凭据可由管理员单独撤销。

已完成的中间验证：

- TypeScript 类型检查、Lint、单元测试和 Vite 构建通过。
- npm run android:sync 通过。
- 新增 Java 类已完成直接编译检查。

尚未完成：

- 将服务端迁移和新版 release 部署到阿里云。
- 在真机上用实际管理员绑定载荷完成一次绑定验收。
- 断网、重启、重装、设备撤销和凭据失效场景验证。

## 4. 当前未完成

### 服务器分析报告

当前服务器已有同步和状态接口，但还没有正式的报告接口。下一步应新增受令牌保护的报告接口，先做确定性数据质量报告：

- 数据时间范围。
- 各指标记录数、最新时间、最早时间、最晚时间。
- 步数、距离、卡路里、睡眠、心率、SpO₂、压力的覆盖情况。
- SpO₂ 是否只有少量点、是否只有一个夜晚。
- 缺失、权限不足、Provider 不支持等限制。
- 明确“数据不足以作医疗判断”的说明。

报告初期不生成疾病概率、诊断结论或未经验证的风险分数。

### App 报告返回

报告接口完成后，再在 Android App 中：

1. 手动同步成功后请求报告。
2. 显示服务器最后分析时间和覆盖摘要。
3. 将报告失败与本地 Provider 失败分开显示。
4. 没有报告时显示明确状态，不显示空白或虚构结果。

## 5. 当前已知问题

- vivo Provider 公开展示数据和私有 Provider 返回数据的时间粒度可能不同。
- readAt 是桥接读取时间，不能冒充 Provider 原始测量时间。
- SpO₂ 可能只返回最新单点或少量稳定行，不能通过手机轮询强行制造不存在的历史测量。
- 睡眠跨午夜，必须同时保存 start_time 和 end_time。
- App 卸载、清除数据或 Android Keystore 变化可能导致本地自动同步令牌丢失。
- APK 构建必须使用用户本机实际可用的 JDK/Gradle，不以 Codex 沙箱内的 Gradle 失败结果作为源码失败依据。
- 当前项目资料和旧部署记录仍有部分位于 C 盘工作区；主代码事实以 E 盘工程为准。

## 6. 下一步执行顺序

1. 在阿里云执行数据库迁移并设置独立设备绑定管理员凭据。
2. 用户安装最新 Debug/Release APK，扫描一次绑定二维码。
3. 确认本地 Provider 读取仍然 PASS，绑定后 JobScheduler 和自动采集启动。
4. 在服务器查看同步状态和数据库数量，确认重复同步不增长。
5. 验证撤销设备、断网、重启、重装和凭据失效场景。
6. 实现并测试服务器报告接口。
7. 将报告接口接入 App。
