# Mock 示例 APP 执行文档

## 1. 文档目的

本文件用于指导 Metabolic Health Agent 从“后端基础架构”迭代为一个可在浏览器中验证的示例 APP。

本阶段只验证架构链路和交互，不接入任何真实用户、公开数据集、穿戴设备、医院数据、真实 LLM 或真实医学知识库。

执行原则：

1. 先验证完整链路，再增加业务功能。
2. 保留现有后端模块边界，不让前端直接依赖数据库、Adapter 或 Agent 内部状态。
3. 所有数据必须明确标识为 Mock。
4. 所有健康结论必须明确标识为健康管理参考，不构成医疗诊断或治疗建议。
5. 每个阶段都设置可停止、可验证的验收门槛；前一阶段未通过时不进入下一阶段。

## 2. 示例 APP 形态

第一版采用“单页健康管理验证台”，而不是完整商业产品。

页面包含以下区域：

1. **Mock 模式横幅**：始终显示“当前为虚构数据，仅用于系统验证”。
2. **系统状态**：显示 API、Mock 仓储、Mock LLM、Mock RAG 是否可用。
3. **用户档案卡片**：显示固定 Mock 用户的年龄、身高、体重、BMI 和管理目标。
4. **健康状态卡片**：显示健康管理分数、关注标签和免责声明。
5. **30 天趋势区域**：显示睡眠、步数、心率和运动时间趋势。
6. **健康观察区域**：展示后端返回的可解释观察，不在前端重新计算医学指标。
7. **Agent 计划区域**：点击按钮后生成运动、饮食和睡眠计划。
8. **安全说明区域**：说明禁止诊断、极端减重建议和药物调整建议。

第一版不做登录、权限、真实数据上传、多用户管理、消息对话、支付、推送和移动端原生应用。

## 3. 技术决策

### 3.1 后端

继续使用现有技术栈：

- Python 3.11
- FastAPI
- Pydantic v2
- LangGraph
- Repository Protocol
- Mock 内存仓储
- Mock FAISS 文档
- Mock LLM Provider
- pytest

后端只补充前端验证所必需的查询能力，不重构现有服务。

### 3.2 前端

建议在项目根目录增加独立 `web/`：

- React
- TypeScript
- Vite
- 原生 `fetch` 封装
- Node.js 内置测试运行器
- CSS 趋势图

第一版不引入全局状态框架和大型 UI 组件库。服务端数据由 API Client 读取，页面状态限制在单个 Dashboard 功能内。

依赖版本在实际创建 `web/` 时固定，并提交 lock 文件；本执行文档不提前猜测未验证版本。

### 3.3 前后端边界

```text
Browser
  ↓ HTTP / JSON
FastAPI Router
  ↓
Service / Agent Workflow
  ↓
Repository Protocol / Retriever / LLM / Safety
  ↓
Mock 实现
```

前端不得：

- 复制 BMI、HOMA-IR 或健康评分算法。
- 访问数据库。
- 解析 LangGraph 内部状态。
- 根据健康事件自行生成医学结论。
- 隐藏 Mock 标记或医疗免责声明。

## 4. 目标目录结构

完成示例 APP 后新增部分如下：

```text
metabolic-health-agent/
├── app/
│   ├── api/
│   ├── services/
│   └── ...
├── web/
│   ├── app/
│   │   ├── api-client.ts
│   │   ├── contracts.ts
│   │   ├── Dashboard.tsx
│   │   ├── metrics.ts
│   │   ├── page.tsx
│   │   └── globals.css
│   ├── tests/
│   ├── Dockerfile
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.ts
├── tests/
├── docs/
│   └── MOCK_DEMO_APP_EXECUTION_PLAN.md
└── docker-compose.yml
```

该结构是目标边界，不要求一次性创建所有抽象；只有出现两个以上真实使用点时才提取公共组件。

## 5. 用户验证流程

标准验证路径如下：

```text
启动后端
  ↓
自动载入固定 Mock 用户和 30 天事件
  ↓
启动前端并打开 Dashboard
  ↓
读取用户档案、事件与健康状态
  ↓
展示趋势和可解释观察
  ↓
用户点击“生成健康计划”
  ↓
LangGraph 执行分析、Mock RAG、Mock LLM、安全检查和保存
  ↓
前端展示计划与免责声明
```

固定 Mock 用户：

```text
00000000-0000-0000-0000-000000000001
```

## 6. 需要补充的后端契约

现有接口已经支持档案、状态和计划。为了绘制 30 天趋势，需要新增一个只读接口。

### 6.1 新增健康事件查询

```http
GET /api/health/events/{user_id}?days=30
```

建议响应：

```json
{
  "user_id": "00000000-0000-0000-0000-000000000001",
  "window_days": 30,
  "count": 120,
  "items": [
    {
      "id": "mock-event-id",
      "user_id": "00000000-0000-0000-0000-000000000001",
      "source": "mock",
      "metric": "sleep",
      "value": 7.4,
      "unit": "hour",
      "timestamp": "2026-08-01T12:00:00Z"
    }
  ]
}
```

实现位置：

- `app/schemas/health.py`：增加分页前的最小列表响应模型。
- `app/services/health_service.py`：增加最近事件查询方法。
- `app/api/health.py`：增加只读路由。
- `tests/test_api.py`：验证 30 天窗口、数量、排序和不存在用户。

### 6.2 开发环境 CORS

只允许配置中的开发地址，例如 `http://localhost:5173`。生产环境不能使用通配符来源。

实现位置：

- `app/config.py`：增加可配置的 CORS 来源列表。
- `app/main.py`：仅按配置安装 CORS Middleware。
- `.env.example`：添加示例地址。

### 6.3 Agent 计划接口说明

当前接口 `GET /api/agent/plan/{user_id}` 会生成并保存计划，符合原始任务约定，但具有写入副作用。

Mock 示例阶段可以继续使用该接口，避免扩大本次改动。进入正式产品阶段前，应新增语义正确的 `POST` 版本，并为旧 `GET` 接口设置兼容和弃用计划。

## 7. Mock 数据策略

### 7.1 数据来源

只允许以下 Mock 来源：

- `MockHealthAdapter` 生成的 30 天睡眠、步数、心率和运动事件。
- 固定 Mock 用户档案。
- `FaissRetriever` 中标识为 `mock://` 的文档。
- 返回 `[MOCK:*]` 标记的 LLM Provider。

### 7.2 确定性

- 固定随机种子。
- 固定 Mock 用户 ID。
- 每次启动生成 30 天 × 4 个指标，共 120 条事件。
- 同一版本计算规则应得到一致的分数和趋势方向。
- 时间戳可以相对当前日期滚动，但前后顺序和时间窗口必须稳定。

### 7.3 禁止事项

- 不允许上传个人体检报告。
- 不允许填写真实姓名、手机号、身份证号或设备账号。
- 不允许把真实 DeepSeek/Qwen API Key 写入前端、日志、Docker 镜像或版本化文件；本地忽略的 `.env` 可以预先保存后续阶段配置，但本阶段不得使用它发起外部调用。
- 不允许下载 NHANES 数据。
- 不允许连接 vivo 或医院接口。
- 不允许把 Mock 输出描述为医学结论。

## 8. 分阶段执行计划

### 阶段 0：冻结当前基线

目标：确保开始开发 UI 前，现有后端始终可回归。

任务：

- [x] 执行 `pytest`，确认当前 15 项测试通过（含新增契约回归测试）。
- [x] 执行 Alembic 离线 SQL 检查。
- [x] 执行 `docker compose config`。
- [x] 保存当前 API OpenAPI JSON 作为契约基线。
- [x] 确认 `.env` 使用 `MHA_REPOSITORY_BACKEND=memory`。

通过条件：基础架构测试全部通过，没有真实外部调用。

完成记录见 [`BASELINE_VALIDATION_2026-08-21.md`](BASELINE_VALIDATION_2026-08-21.md)。

### 阶段 1：补齐 Dashboard 所需 API

目标：让前端只通过公开 API 获得所需数据。

任务：

- [x] 增加健康事件列表响应模型。
- [x] 增加最近事件查询服务。
- [x] 增加 `GET /api/health/events/{user_id}`。
- [x] 增加开发环境 CORS 白名单。
- [x] 增加 API 测试和 OpenAPI 契约检查。
- [x] 保持现有接口向后兼容。

通过条件：档案、事件、状态和计划四类数据都能通过 API 获取；pytest 全部通过。

### 阶段 2：创建最小前端壳

目标：建立独立、可构建、可测试的 `web/`。

任务：

- [x] 创建 React + TypeScript + Vite 工程。
- [x] 固定依赖版本并提交 `package-lock.json`。
- [x] 配置开发 API 地址，不在组件中硬编码端口。
- [x] 创建 API Client、错误类型和 TypeScript 契约。
- [x] 创建全局 Mock 模式横幅和医疗免责声明。
- [x] 添加加载、空数据和 API 错误状态。

通过条件：`npm run build` 和前端单元测试通过；页面能显示后端健康检查结果。

### 阶段 3：实现单页 Dashboard

目标：跑通完整读取链路，不增加真实输入入口。

任务：

- [x] 展示固定 Mock 用户档案。
- [x] 展示分数、关注标签、BMI 和观察信息。
- [x] 将 120 条事件按指标分组。
- [x] 绘制睡眠、步数、心率和运动时间趋势。
- [x] 清楚显示单位、时间窗口和 Mock 来源。
- [x] 在窄屏和桌面宽度下检查布局。

通过条件：刷新页面可以稳定重建相同 Dashboard；前端不包含健康计算公式。

### 阶段 4：接入 Agent 计划交互

目标：验证 LangGraph、RAG、LLM、安全检查和保存链路。

任务：

- [x] 增加“生成 Mock 健康计划”按钮。
- [x] 点击后显示明确的处理中状态并防止重复提交。
- [x] 展示运动、饮食、睡眠三个计划区块。
- [x] 展示生成理由、Mock 标记和医疗免责声明。
- [x] 对 404、422 和服务不可用显示可理解的错误。
- [x] 验证安全规则拒绝包含极端减重或药物调整内容的测试计划。

通过条件：正常计划可显示，危险计划不可保存，所有外部 Provider 仍为 Mock。

### 阶段 5：自动化和人工验收

目标：把示例演示变成可重复验证流程。

任务：

- [x] 后端运行完整 pytest。
- [x] 前端运行类型检查、单元测试和生产构建。
- [x] 完成最小浏览器端到端验收：打开页面 → 看到 Mock 横幅 → 加载状态 → 生成计划。
- [x] 验证后端关闭时的前端错误状态。
- [x] 验证空事件列表不会导致页面崩溃。
- [x] 验证刷新后内存 Mock 数据可以重新载入。
- [x] 检查浏览器和服务日志中没有密钥或真实个人数据。

通过条件：自动化检查全部通过，人工验收清单无阻塞项。

### 阶段 6：可选 Docker 演示封装

目标：在核心验证通过后，提供统一启动方式。

任务：

- [x] 为前端创建多阶段 Dockerfile。
- [x] 在独立 `docker-compose.demo.yml` 中增加 `web` 服务。
- [x] 通过构建参数配置浏览器可访问的 API 地址。
- [x] 增加 API 和 Web 健康检查。
- [x] 验证 `docker compose up --build` 后可访问 Dashboard。

2026-08-26：Docker Desktop Linux Engine 恢复后完成实际镜像构建；API 与 Web 容器均为 `healthy`，Dashboard、健康事件、健康状态和 Agent 计划接口均通过 HTTP 验收。详细证据见 `docs/MOCK_DEMO_VALIDATION_2026-08-21.md`。

本阶段仍使用 Mock 数据。PostgreSQL 联调属于独立验证项，不应与第一版 UI 同时排错。

## 9. 测试矩阵

| 层级 | 验证对象 | 最低用例 |
|---|---|---|
| 单元测试 | 代谢与趋势服务 | BMI、HOMA-IR、分数标签、趋势方向 |
| Adapter 测试 | Mock 标准化 | 30 天、4 指标、120 条、来源为 mock |
| 仓储测试 | 内存读写 | 用户、事件排序、计划保存、进程重置 |
| 安全测试 | SafetyRuleEngine | 正常建议通过；禁食、诊断、药物调整被拒绝 |
| Agent 测试 | LangGraph | 节点按顺序完成，安全检查后才保存 |
| API 测试 | FastAPI | 健康检查、档案、事件、状态、计划、404、422 |
| 前端单元测试 | Dashboard | 加载、成功、空数据、错误、按钮禁用 |
| 浏览器测试 | 完整链路 | 打开页面并生成一份 Mock 计划 |

## 10. 验证命令

### 10.1 后端

```powershell
cd E:\HealthEvent\metabolic-health-agent
.\.venv\Scripts\Activate.ps1
python -m pip check
pytest -p no:cacheprovider
python -m alembic upgrade head --sql
docker compose config
uvicorn app.main:app --reload
```

### 10.2 后端冒烟验证

```powershell
$userId = '00000000-0000-0000-0000-000000000001'
Invoke-RestMethod 'http://localhost:8000/healthz'
Invoke-RestMethod "http://localhost:8000/api/user/profile/$userId"
Invoke-RestMethod "http://localhost:8000/api/health/status/$userId"
Invoke-RestMethod "http://localhost:8000/api/agent/plan/$userId"
```

阶段 1 完成后增加：

```powershell
Invoke-RestMethod "http://localhost:8000/api/health/events/$userId?days=30"
```

### 10.3 前端

以下命令在阶段 2 创建 `web/` 后执行：

```powershell
cd E:\HealthEvent\metabolic-health-agent\web
npm ci
npm run typecheck
npm run test
npm run build
npm run dev
```

## 11. 人工验收清单

- [x] 页面顶部始终显示 Mock 数据标记。
- [x] 页面没有真实数据上传入口。
- [x] 固定 Mock 用户信息正常显示。
- [x] 30 天四类指标都有数据和正确单位。
- [x] 健康分数在 0–100 之间。
- [x] 健康标签只使用 `normal`、`attention`、`high_attention`。
- [x] 没有血糖和胰岛素时，页面不显示虚构 HOMA-IR。
- [x] 点击按钮后能生成运动、饮食、睡眠计划。
- [x] 计划包含 Mock 标记和医疗免责声明。
- [x] 页面未出现诊断、处方或药物剂量建议。
- [x] API 失败时页面提供错误提示和重试入口。
- [x] 后端、前端和浏览器控制台没有未处理异常。
- [x] 版本化文件、前端产物和日志中没有 API Key、真实姓名或健康隐私数据。

## 12. 完成定义

同时满足以下条件，才视为 Mock 示例 APP 完成：

1. 单页 Dashboard 可以在浏览器访问。
2. 数据全部来自固定 Mock 链路。
3. 用户档案、30 天事件、健康状态和 Agent 计划均可展示。
4. 危险计划由独立安全规则拒绝，不能保存。
5. 后端测试、前端测试、前端构建和最小端到端测试全部通过。
6. README 包含一键启动方式和演示步骤。
7. 页面和响应中持续保留 Mock 与非医疗诊断提示。
8. 未接入任何真实外部数据或模型服务。

## 13. 本阶段结束后的下一步

Mock 示例 APP 通过验收后，应按以下顺序继续，而不是同时接入所有来源：

1. 先切换 PostgreSQL，验证迁移、事务和数据持久化。
2. 再选择一个真实数据源建立 Adapter 契约；建议从公开且字段稳定的数据开始。
3. 建立医学语料治理后再替换 Mock RAG。
4. 完成脱敏、超时、重试、审计和安全评测后再接真实 LLM。
5. 医院数据和药物相关能力最后进入独立的安全与合规阶段。
