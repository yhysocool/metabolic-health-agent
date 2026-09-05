# 项目级工作记忆

## vivo 私有健康 Provider 发布门禁

- Android 应用真实包名固定为 `com.healthevent.mobile`。不要使用旧项目包名 `dev.akari.pulse.bridge`。
- 当前私有健康权限为 `com.vivo.health.widget.permission`。
- 每次 APK 更新、重新安装或准备发布前，必须在已连接的本人 vivo 真机上运行 `mobile/scripts/verify-vivo-private-health.ps1`。
- 检查必须确认主用户的权限状态为 `granted=true`，并确认 Provider `com.vivo.health.provider` 和 `com.vivo.health.provider.care` 存在。
- 检查失败时脚本必须返回非零退出码；不得继续发布 APK。
- 个人开发测试可以使用 `-RepairPermission` 自动执行一次 ADB 授权并再次验证；授权仍失败时必须停止发布。
- APK 更新应使用覆盖安装（`adb install -r`），禁止在发布流程中先卸载应用。包名和签名必须保持稳定。
- 普通 Android APP 不能自行授予该权限；APP 内只能检查并提示修复，不得把检查结果伪装成已授权。
