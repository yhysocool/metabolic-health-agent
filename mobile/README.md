# 衡康 Android 体验框架

这是独立于 `web/` 的 React + Vite + Capacitor 8 Android 客户端。它只消费
FastAPI 的 `v0.4.0` 契约，不复制后端健康计算规则。

## 当前边界

- 只读取本地合成演示数据。
- 不申请 vivo Health Kit、蓝牙、位置、运动或健康权限。
- API 地址保存在设备本地，只用于连接同一局域网电脑。
- `com.healthevent.mobile` 是开发阶段应用 ID；首次对外发布前需最终确认。
- Android 的明文 HTTP 放行仅存在于 Debug 清单，Release 版本必须使用 HTTPS。

## Web 层验证

```powershell
cd E:\HealthEvent\metabolic-health-agent\mobile
npm ci
npm test
npm run build
```

`npm test` 会执行 TypeScript、ESLint 和单元测试。生产 Web 资源构建完成后，
把它同步到 Android 工程：

```powershell
npm run android:sync
```

## 构建 Debug APK

当前已验证的本机工具链：

- Android Studio 2026.1
- Android SDK：`E:\HealthEvent\android-sdk`
- Android API 36，Build Tools 35.0.0/36.0.0
- Gradle 8.14.3
- JDK：`D:\SoftWare\java`

在 PowerShell 中执行：

```powershell
cd E:\HealthEvent\metabolic-health-agent\mobile
.\scripts\build-android-debug.ps1 `
  -JavaHome D:\SoftWare\java `
  -AndroidHome E:\HealthEvent\android-sdk
```

构建产物：

```text
android\app\build\outputs\apk\debug\app-debug.apk
```

构建脚本显式指定 JDK 和 Android SDK，因此不依赖本机可能过期的系统
`JAVA_HOME`。也可以通过 Android Studio 打开 `mobile/android` 后构建。

## 安装到 Android 手机

1. 手机开启“开发者选项”和“USB 调试”，通过 USB 连接电脑并允许调试授权。
2. 检查连接并安装：

```powershell
E:\HealthEvent\android-sdk\platform-tools\adb.exe devices -l
E:\HealthEvent\android-sdk\platform-tools\adb.exe install -r `
  E:\HealthEvent\metabolic-health-agent\mobile\android\app\build\outputs\apk\debug\app-debug.apk
```

3. 电脑启动 API 并监听局域网：

```powershell
cd E:\HealthEvent\metabolic-health-agent
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

4. 手机和电脑连接同一个可信 Wi-Fi。在 APP 的“API 设置”中填写电脑 WLAN
   地址，例如 `http://192.168.1.20:8000`。Android 模拟器访问电脑时使用
   `http://10.0.2.2:8000`。

如果 Windows 防火墙询问，只允许专用网络。完整验收清单见
[`../docs/ANDROID_LOCAL_DEBUG_EXECUTION.md`](../docs/ANDROID_LOCAL_DEBUG_EXECUTION.md)。

### vivo 私有健康授权发布门禁

当前 Android 包名是 `com.healthevent.mobile`，不是旧项目的
`dev.akari.pulse.bridge`。每次安装或更新 APK 后，必须先运行授权门禁；门禁
失败时不要发布 APK。

只检查当前状态：

```powershell
cd E:\HealthEvent\metabolic-health-agent\mobile
.\scripts\verify-vivo-private-health.ps1 `
  -AndroidHome E:\HealthEvent\android-sdk
```

在本人真机上更新 APK、必要时自动补授权并验证：

```powershell
cd E:\HealthEvent\metabolic-health-agent\mobile
.\scripts\verify-vivo-private-health.ps1 `
  -AndroidHome E:\HealthEvent\android-sdk `
  -ApkPath E:\HealthEvent\metabolic-health-agent\mobile\android\app\build\outputs\apk\debug\app-debug.apk `
  -RepairPermission
```

只有输出 `VIVO_PERMISSION_GATE_PASS` 才允许进入后续发布流程。脚本使用
`adb install -r` 覆盖安装，不会在发布流程中主动卸载 APP；如果包名、签名、
Provider 或主用户授权不符合要求，会以非零状态退出。