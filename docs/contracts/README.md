# API 契约基线

契约文件按 FastAPI 应用版本命名。`openapi-v0.1.0.json` 是 Mock 示例 APP 开始
开发前的历史基线；当前版本由契约回归测试自动选择。

重新生成：

```powershell
cd E:\HealthEvent\metabolic-health-agent
.\.venv\Scripts\python.exe scripts\export_openapi.py
pytest tests\test_openapi_contract.py -p no:cacheprovider
```

更新规则：

1. 只有经过审查的 API 变更才可以重新导出基线。
2. 变更时必须同步更新后端测试、前端契约类型和版本说明。
3. 不允许为了绕过失败而直接删除契约测试。
