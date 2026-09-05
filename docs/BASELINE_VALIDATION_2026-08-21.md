# 后端基线冻结与验证报告

验证日期：2026-08-21（Asia/Shanghai）

结论：**阶段 0 已通过，可以进入 Mock 示例 APP 的接口补齐阶段。**

## 冻结范围

本次冻结覆盖以下公开接口和基础设施边界：

- FastAPI 路由与 Pydantic 响应契约。
- Mock 用户、Mock 健康事件和内存仓储。
- 代谢计算与趋势分析。
- LangGraph 工作流。
- Mock FAISS Retriever。
- Mock Local/DeepSeek/Qwen Provider 接口。
- SafetyRuleEngine。
- SQLAlchemy 模型和 Alembic 首版迁移。
- Docker Compose 配置。

## 验证结果

| 检查项 | 结果 | 证据 |
|---|---|---|
| Python 运行时 | 通过 | Python 3.11.4 |
| 依赖完整性 | 通过 | `pip check` 返回 `No broken requirements found` |
| 自动化测试 | 通过 | 15 passed |
| OpenAPI 契约测试 | 通过 | 当前 schema 与冻结 JSON 完全一致 |
| Alembic 离线迁移 | 通过 | revision `20260821_0001` 成功生成 PostgreSQL SQL 并提交事务 |
| Docker Compose 解析 | 通过 | `docker compose config --quiet` 退出码为 0 |
| 数据仓储模式 | 通过 | `repository_backend=memory` |
| Mock 数据初始化 | 通过 | `seed_mock_data=True` |
| LLM 模式 | 通过 | `llm_provider=local`，当前实现返回 Mock 响应 |
| DeepSeek API Key | 未配置 | `False` |
| Qwen API Key | 未配置 | `False` |

## OpenAPI 契约

基线文件：[`contracts/openapi-v0.1.0.json`](contracts/openapi-v0.1.0.json)

SHA-256：

```text
139f8b425cc3d3f47302f22a7e7cb921cacf17dacc324a119b576be7067015af
```

导出脚本固定使用 UTF-8 和 LF 字节输出，因此 Windows、Linux 和 Docker 环境可以得到一致摘要。

更新契约：

```powershell
.\.venv\Scripts\python.exe scripts\export_openapi.py
pytest tests\test_openapi_contract.py -p no:cacheprovider
```

只有经过审查的接口变更才允许重新导出基线。

## 本地 Mock 环境

项目根目录已创建被 Git 忽略的 `.env`，关键配置如下：

```text
MHA_ENVIRONMENT=development
MHA_REPOSITORY_BACKEND=memory
MHA_SEED_MOCK_DATA=true
MHA_LLM_PROVIDER=local
```

DeepSeek 和 Qwen Key 均为空。该文件不包含真实账号、真实健康数据或密钥。

## 已知非阻塞项

测试输出包含一条来自 FastAPI/Starlette 第三方 `TestClient` 的弃用提示。当前测试正常通过，该提示不影响 API 行为；后续依赖维护阶段应迁移到第三方推荐的新测试客户端。

Docker 命令提示无法读取用户目录中的 Docker 客户端配置文件，但 Compose 文件本身解析成功。此次基线只验证配置，没有启动 PostgreSQL 容器或下载镜像。

## 基线保护规则

1. 新增或修改路由后，契约测试应先失败。
2. 审查 OpenAPI 差异并同步前端类型后，才能重新生成基线。
3. 不允许删除安全测试、工作流测试或契约测试来规避失败。
4. 示例 APP 阶段始终使用 Mock 数据和 Mock Provider。
5. 申请到真实 API 后暂不写入本项目；应先完成独立的密钥管理和 Provider 接入评审。

## 基线后的 Provider 选择

用户已选择后续接入 **Qwen**。本地 `.env` 已将 `MHA_LLM_PROVIDER` 设置为 `qwen`，但
`MHA_QWEN_API_KEY` 仍为空，`QwenProvider` 仍为 Mock 实现，不会发起任何外部请求。
该配置选择不改变已冻结的 OpenAPI 契约。
