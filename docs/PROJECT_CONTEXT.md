# 衡康（HealthEvent）项目长期上下文

> 本文件用于在 Codex 长对话压缩、任务切换或重新打开项目后恢复事实背景。
> 更新日期：2026-09-04。
> 本文件不保存密码、令牌、私钥或真实健康数据。

## 1. 项目定位

衡康是一个面向亚健康成年人的健康管理辅助 App。当前重点是：

1. 从 vivo 手机本地健康 Provider 读取已经同步到手机的个人健康数据。
2. 在手机本地形成统一健康快照和增量记录。
3. 通过 HTTPS 上传到阿里云服务器。
4. 在服务器保存、整理并生成非医疗诊断性质的健康趋势和数据质量报告。
5. 后续再将报告返回 Android App，并接入现有健康分析与 LangGraph Agent。

当前项目是工程验证阶段，不得把结果表述为疾病诊断或医疗结论。

## 2. 唯一路径与工程边界

主工程：

E:\HealthEvent\metabolic-health-agent

同级参考工程：

E:\HealthEvent\akari-pulse

主工程下的 Android / Web 工程：

E:\HealthEvent\metabolic-health-agent\mobile

服务器运行目录：

/opt/healthevent

历史数据流水线在当前工作区的 data_pipeline 目录中；历史部署记录在当前工作区的 deploy 目录中。它们属于项目资料，不等同于主应用源码。

## 3. 当前技术栈

- 后端：Python、FastAPI、Pydantic v2。
- 持久化：SQLAlchemy、Alembic、PostgreSQL。
- 业务层：HealthRepository、Adapter、HealthService、TrendService。
- AI 层：LangGraph、可插拔 LLM Provider、RAG；本地演示阶段仍可使用 Mock。
- 移动端：React、TypeScript、Capacitor、Android 原生 Java。
- vivo 采集：Android 原生 VivoHealthSnapshotReader、VivoPrivateHealthReader、VivoOvernightCaptureService。
- 本地保存：Android 快照存储和夜间采集样本存储。
- 自动上传：Android VivoAutoSyncStore、VivoAutoSyncClient、VivoAutoSyncJobService。
- 设备绑定：服务端一次性绑定码、Android Keystore P-256 设备密钥和设备级同步凭据。
- 服务器入口：Nginx HTTPS → Uvicorn/FastAPI server_main → PostgreSQL。
- 服务器进程：healthevent-api.service，内部监听 127.0.0.1:18080。

## 4. 当前数据流

~~~text
vivo Watch / Band
    ↓
vivo 健康 App
    ↓
vivo 手机本地 Health Provider
    ↓
VivoHealthSnapshotReader / VivoPrivateHealthReader
    ↓
Android 快照与夜间采集存储
    ↓
统一 PASS 健康记录与稳定 record_id
    ↓
HTTPS /api/integrations/vivo/sync
    ↓
Nginx → FastAPI server_main
    ↓
VivoSyncService → VivoAdapter → HealthRepository
    ↓
PostgreSQL
    ↓
数据质量/趋势报告
    ↓
Android App / 未来 LangGraph Agent
~~~

服务器接收服务和本地完整 AI 应用是两个边界：

- app/main.py：本地完整应用，包含演示数据、健康分析和 Agent。
- app/server_main.py：阿里云接收服务，不加载本地 AI、LangGraph 或 FAISS。

## 5. 已确认的工程原则

- 外部数据必须先经过 Adapter，再进入统一健康事件模型。
- 业务层不能直接依赖 vivo Provider 或厂商 SDK 对象。
- 每条记录保留来源、设备、指标、测量时间、区间、数值、单位、状态、原始来源和同步时间。
- 没有数据不能填 0；读取失败不能静默降级为旧数据。
- PASS、NO_DATA、DENIED、UNSUPPORTED、ERROR 必须区分。
- Provider、权限、ROM 或字段不支持时，明确返回 UNSUPPORTED。
- 设备标识在服务器只保存摘要，不保存原始设备标识。
- 全局服务器令牌不得进入源码、Git、APK 日志、项目文档或前端构建产物；普通用户通过一次性设备绑定获得设备级凭据。
- App 数据上传必须使用 HTTPS；服务器内部 API 和 PostgreSQL 不直接暴露公网。
- 任何报告都只能作为健康管理辅助信息，不是医疗诊断。

## 6. 继续工作时的读取顺序

1. 先读本文件。
2. 再读 docs/CURRENT_STATUS.md。
3. 涉及构建、部署或真机验证时读 docs/OPERATIONS.md。
4. 涉及字段、状态或接口时读 docs/DATA_CONTRACT.md。
5. 最后以当前源码和测试结果为准，不以旧聊天内容覆盖源码事实。

若文档与源码、测试或服务器实际状态冲突，应标记冲突并先核查，不得猜测。
