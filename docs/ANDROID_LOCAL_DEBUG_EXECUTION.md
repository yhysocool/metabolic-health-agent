# Android 本地 Debug APK 执行与验收记录

## 1. 结论

Android 基础框架、资源同步和首个 Debug APK 已于 2026-08-30 完成。该 APK
只连接本项目的本地合成数据 API，不接入 vivo Health Kit，不读取真人健康数据，
也不用于应用商店发布。

产物：

```text
E:\HealthEvent\metabolic-health-agent\mobile\android\app\build\outputs\apk\debug\app-debug.apk
```

## 2. 已验证工具链

- Android Studio 2026.1
- Android SDK：`E:\HealthEvent\android-sdk`
- Android API 36
- Android Build Tools 35.0.0 和 36.0.0
- Android Platform Tools
- Gradle 8.14.3
- JDK：`D:\SoftWare\java`

Android SDK License 已全部接受。项目的 `local.properties` 仅保存在本机且被
Git 忽略，不应提交开发电脑路径。

## 3. 可复现构建

```powershell
cd E:\HealthEvent\metabolic-health-agent\mobile
npm ci
npm test
npm run build
npm run android:sync
.\scripts\build-android-debug.ps1 `
  -JavaHome D:\SoftWare\java `
  -AndroidHome E:\HealthEvent\android-sdk
```

脚本会验证 JDK 与 Android API 36，显式设置本次构建所需环境变量，并把日志
写入临时目录。这样不依赖当前系统中可能过期的 `JAVA_HOME`。

## 4. 安装到真机

1. 手机开启“开发者选项”和“USB 调试”。
2. 使用 USB 连接电脑，在手机端允许这台电脑进行调试。
3. 检查设备并安装：

```powershell
E:\HealthEvent\android-sdk\platform-tools\adb.exe devices -l
E:\HealthEvent\android-sdk\platform-tools\adb.exe install -r `
  E:\HealthEvent\metabolic-health-agent\mobile\android\app\build\outputs\apk\debug\app-debug.apk
```

当前验收电脑尚未检测到已授权的 Android 设备，因此本记录不声称已经完成
真机安装。

## 5. 连接本地合成数据 API

电脑与手机连接同一个可信 Wi-Fi，然后在电脑执行：

```powershell
cd E:\HealthEvent\metabolic-health-agent
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

通过 `ipconfig` 找到电脑 WLAN IPv4 地址。在 APP 的“API 设置”中填写例如
`http://192.168.1.20:8000`。Android 模拟器使用 `http://10.0.2.2:8000`。
Windows 防火墙如有询问，只允许专用网络。

保存 API 地址后，APP 应显示：

- “已连接本地合成数据服务”；
- 合成人物的健康分数和 30 天指标；
- “未连接 vivo 手表”和“非医疗诊断”提示。

## 6. 产物审计

- 文件大小：4,272,313 字节。
- SHA-256：`A45E6856B8D2E46A13C3A6727F5964558D6D0D2AA87E18B6CC5FBA41CE0A9789`。
- 包名：`com.healthevent.mobile`。
- 应用名：`衡康`。
- 版本：`1.0`，versionCode `1`。
- minSdk：24；targetSdk/compileSdk：36。
- 签名：Android Debug，APK Signature Scheme v2，RSA 2048。
- 权限：仅 `INTERNET` 和 Android 构建系统生成的应用内部动态接收器权限；
  未申请健康、蓝牙、位置或运动权限。
- APK 内的前端入口与最终同步产物一致：`index-FRPGhVCr.js`。

## 7. 验证结果

- 后端：23 项测试通过。
- 移动端：TypeScript、ESLint、2 项单元测试和 Vite 生产构建通过。
- Android：Gradle `assembleDebug` 成功，93 项任务完成。
- 390×844 移动视口浏览器验收通过，无横向溢出和控制台错误。
- 已修复“重复保存相同 API 地址后一直显示加载中”的状态刷新问题。

## 8. 本阶段不包含

- vivo Health Kit 或其他穿戴设备真实数据。
- Release APK/AAB、正式签名和密钥管理。
- HTTPS 公网 API、用户身份认证和生产数据存储。
- APP 备案、隐私合规评审和应用商店发布。

这些能力应在本地合成数据链路稳定后分阶段增加，不能直接复用 Debug 配置上线。
