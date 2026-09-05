# Metabolic Health Agent

面向亚健康成年人的 AI 健康管理辅助 Agent。当前版本包含稳定的后端基础架构和一个可在浏览器验证的单页 Dashboard。健康事件来自明确标识的本地合成生成器：睡眠与活动由 NHANES 公开数据的聚合统计校准，步数与心率由本地规则生成；不包含真实用户、医院或穿戴设备数据。检索文档和 LLM 响应仍为 Mock。

本系统不是医疗诊断或疾病治疗系统，输出不能替代医生判断。

Mock 浏览器示例 APP 的分阶段实施、验证命令和验收标准见
[`docs/MOCK_DEMO_APP_EXECUTION_PLAN.md`](docs/MOCK_DEMO_APP_EXECUTION_PLAN.md)。

当前后端冻结状态与验证证据见
[`docs/BASELINE_VALIDATION_2026-08-21.md`](docs/BASELINE_VALIDATION_2026-08-21.md)。

当前 Mock 示例 APP 的完整验收结果见
[`docs/MOCK_DEMO_VALIDATION_2026-08-21.md`](docs/MOCK_DEMO_VALIDATION_2026-08-21.md)。

vivo Watch GT 2 的分阶段接入、fixture 验证与上线门禁见
[`docs/VIVO_WATCH_GT2_INTEGRATION_EXECUTION.md`](docs/VIVO_WATCH_GT2_INTEGRATION_EXECUTION.md)。

当前本地合成数据模式、局域网手机验证方法和数据边界见
[`docs/LOCAL_SYNTHETIC_DEMO_EXECUTION.md`](docs/LOCAL_SYNTHETIC_DEMO_EXECUTION.md)。

Android Debug APK 的构建、安装和真机验证步骤见
[`docs/ANDROID_LOCAL_DEBUG_EXECUTION.md`](docs/ANDROID_LOCAL_DEBUG_EXECUTION.md)。

## 当前能力

- 用 `HealthEvent` 统一睡眠、步数、心率、血糖、胰岛素、体重、BMI 和运动事件。
- 通过 Adapter 隔离 Mock、合成、手动、NHANES、vivo 和医院数据来源。
- 使用不含参与者级记录的 NHANES 聚合参考文件校准本地合成演示数据。
- 提供 BMI、HOMA-IR、基础健康管理分数和 30 天趋势计算。
- 通过 LangGraph 编排档案读取、事件读取、分析、RAG、计划生成、安全检查和保存。
- 默认使用 FAISS + Mock 文档；FAISS 不可用时仅为开发连续性回退到词项匹配。
- 通过统一 `BaseLLM` 接口预留 DeepSeek、Qwen 和 Local LLM；当前均不发起真实请求。
- 默认用内存仓储并装载 30 天合成演示数据；可通过配置切换 PostgreSQL + SQLAlchemy + Alembic。
- 提供 React + TypeScript Dashboard，展示合成档案、30 天四类趋势、来源说明、健康状态和 Agent 安全计划。
- 提供 React + TypeScript + Capacitor 8 Android 客户端，并可构建仅连接本地合成数据 API 的 Debug APK。
- 提供独立的 Mock Docker Compose，不把前端演示与 PostgreSQL 联调耦合。
- 提供默认关闭的 vivo 增量同步骨架，支持来源 ID 幂等、同步游标、设备标识摘要和 fixture 验证。

## 目录结构

```text
metabolic-health-agent/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── dependencies.py
│   ├── api/                  # HTTP 协议层
│   │   ├── health.py
│   │   ├── agent.py
│   │   └── user.py
│   ├── schemas/              # Pydantic v2 数据契约
│   ├── adapters/             # 外部数据统一入口
│   ├── services/             # 纯业务计算与应用服务
│   ├── repositories/         # 持久化协议及两种实现
│   ├── database/             # ORM、连接与 Alembic 迁移
│   │   └── migrations/
│   ├── agent/                # LangGraph 状态、工具和工作流
│   ├── rag/                  # Embedding 与 Retriever
│   ├── llm/                  # 可插拔模型 Provider
│   └── safety/               # 确定性安全门禁
├── tests/
├── web/                       # React + TypeScript 单页验证 APP
│   ├── app/                   # Dashboard、API Client、契约与样式
│   ├── tests/
│   ├── Dockerfile
│   └── package-lock.json
├── mobile/                    # React + TypeScript + Capacitor Android 客户端
│   ├── android/               # 原生 Android 工程
│   ├── scripts/               # 可复现的 Debug APK 构建脚本
│   └── src/
├── docs/                      # 执行计划、契约基线与验收记录
├── data/
│   ├── raw/
│   └── processed/
├── requirements.txt
├── requirements-dev.txt
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── docker-compose.demo.yml
└── .env.example
```

## 架构约束

依赖方向保持单向：

```text
API → Agent / Service → Repository Protocol
                         ↑
            Memory 或 SQLAlchemy 实现

外部数据 → Adapter → HealthEvent → Repository
Agent → Tool → Service / Retriever / Safety / LLM Protocol
```

关键原则：

1. 外部数据不能绕过 Adapter 直接进入业务层。
2. ORM 模型不能用于健康计算或作为 API 响应。
3. Agent 负责流程编排，计算规则放在 Service，安全规则独立于 LLM。
4. 安全检查失败的计划不会保存。
5. 真实 Provider 接入前，Mock 状态必须在输出和文档中可见。

## 本地启动合成数据体验版

要求 Python 3.11，以及 Node.js 22.13 或更高版本。分别打开两个 PowerShell 终端。

终端 1：启动 API。

```powershell
cd E:\HealthEvent\metabolic-health-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

终端 2：启动 Web。

```powershell
cd E:\HealthEvent\metabolic-health-agent\web
npm ci
Copy-Item .env.example .env -ErrorAction SilentlyContinue
npm run dev
```

打开：

- Mock Dashboard：<http://localhost:3000>
- API 文档：<http://localhost:8000/docs>
- 存活检查：<http://localhost:8000/healthz>
- Mock 用户健康事件：`GET /api/health/events/00000000-0000-0000-0000-000000000001?days=30`
- Mock 用户健康状态：`GET /api/health/status/00000000-0000-0000-0000-000000000001`
- Mock 用户健康计划：`GET /api/agent/plan/00000000-0000-0000-0000-000000000001`

即使本地 `.env` 已配置 Qwen Key，当前 `QwenProvider` 仍只返回带 `[MOCK:qwen]` 标记的固定响应，不会发送外部请求。Key 不得写入前端环境变量、Docker 镜像、日志或版本化文件。

在同一局域网的手机浏览器验证时，使用 `uvicorn ... --host 0.0.0.0` 和
`npm run dev:lan`。完整命令与防火墙注意事项见本地合成数据执行文档。

## Docker Compose 启动（合成数据体验版）

```powershell
docker compose -f docker-compose.demo.yml up --build
```

该编排只启动内存合成数据 API 与 Web，不启动 PostgreSQL，也不向容器传入任何模型 Key。API 与 Web 均带健康检查。若 Docker Desktop 的 Linux 引擎不可用，可继续使用上面的双终端本地启动方式。

## Docker Compose 启动（PostgreSQL）

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Compose 会等待 PostgreSQL 健康检查通过，执行 `alembic upgrade head`，再启动 API。数据库模式不会自动创建用户；可先调用 `POST /api/user/profile` 创建虚构测试档案，再通过 `POST /api/health/event` 写入明确标记来源的测试事件。

示例档案：

```json
{
  "id": "00000000-0000-0000-0000-000000000001",
  "age": 35,
  "gender": "undisclosed",
  "height": 172,
  "weight": 72,
  "goal": "metabolic_health"
}
```

## 测试

```powershell
python -m pip install -r requirements-dev.txt
pytest

cd web
npm test

cd ..\mobile
npm test
npm run android:sync
```

后端测试覆盖基础代谢计算、趋势方向、Adapter 标准化、安全门禁、LangGraph 全链路和 FastAPI 接口；前端测试命令会依次执行 TypeScript 检查、ESLint、生产构建和 Mock/空事件契约测试。

## API

- `POST /api/user/profile`：创建或更新档案。
- `GET /api/user/profile/{user_id}`：查询档案。
- `POST /api/health/event`：上传单个标准健康事件。
- `GET /api/health/events/{user_id}?days=30`：查询指定窗口内按时间排序的健康事件。
- `GET /api/health/status/{user_id}`：返回非诊断性健康状态。
- `GET /api/agent/plan/{user_id}`：运行 Agent 并保存健康计划。
- `POST /api/integrations/vivo/sync`：提交获授权桥接记录；默认关闭且要求 Bearer 令牌。
- `GET /api/integrations/vivo/status/{user_id}`：查询不含设备原始标识的同步状态。

## 下一步接入真实数据

### NHANES

1. 固定数据发布周期与数据字典版本，不在 Adapter 内临时猜测列名。
2. 在 `NHANESAdapter` 中实现读取、单位转换、缺失值策略和字段溯源。
3. 为每个源字段到 `HealthMetric` 的映射添加契约测试。
4. 原始文件保持只读，标准化输出仍只允许 `HealthEventCreate`。

### vivo Watch GT 2

后端 fixture 同步骨架已完成。真实接入仍需按执行文档取得 vivo Health Kit 材料，建立获用户授权的 Android 桥接 APP，并把共享验证令牌替换为用户身份令牌。设备 SDK 对象不会传入后端服务或 Agent。

### 医院脱敏体检数据

1. 在编码前完成数据授权、脱敏、最小化、留存期限和审计方案评审。
2. 建立医院字段字典、检验单位和参考区间版本，不直接复用穿戴设备规则。
3. 在 `HospitalAdapter` 中保留来源批次和质量标记；异常记录进入隔离区，不直接入库。
4. 任何诊断、药物或治疗相关能力都需要独立的临床、安全与合规评审。

### 真实 RAG 与 LLM

1. 给医学语料建立来源、发布日期、适用人群、版本和失效机制。
2. 将真实 Embedding 实现注入 `FaissRetriever`，并为索引记录语料版本。
3. 在 Provider 中实现超时、重试、限流、脱敏和调用审计，密钥只从环境或密钥服务读取。
4. 上线前增加结构化输出校验、规则版本、人工复核入口和离线安全评测。
