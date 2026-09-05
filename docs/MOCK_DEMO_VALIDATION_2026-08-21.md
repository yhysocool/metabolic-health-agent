# Mock 示例 APP 验收记录（2026-08-21）

## 结论

Mock 示例 APP 的核心链路已完成并通过验收：固定虚构用户、30 天健康事件、健康状态、四类趋势和 Agent 安全计划可以在单页 Dashboard 中展示。系统未调用真实数据源、真实 RAG 或真实 Qwen 服务。

执行计划阶段 0–6 已完成。Docker Desktop Linux Engine 于 2026-08-26 恢复后，API 与 Web 镜像已在本机实际构建并启动，两个容器均通过健康检查和端到端 HTTP 验收。

## 验证范围

- 后端：FastAPI、内存 Mock 仓储、Mock Adapter、LangGraph、Mock RAG、Mock Qwen、安全规则。
- 前端：React、TypeScript、Vite/vinext、原生 fetch、CSS 趋势图。
- 数据：固定 Mock 用户与 30 天 × 4 指标，共 120 条虚构事件。
- 浏览器：桌面布局、390 × 844 窄屏、Agent 按钮、后端离线提示、重连恢复。
- 容器：API/Web Dockerfile、独立 Mock Compose、服务健康检查和配置解析。

## 自动化结果

### 后端

```text
python -m pip check
No broken requirements found.

pytest -p no:cacheprovider
17 passed, 1 third-party deprecation warning
```

新增的安全回归测试会注入包含“连续禁食”的 Mock LLM 文本，并证明安全门禁在仓储保存之前中断工作流，保存次数为 0。

### 前端

```text
npm run typecheck  PASS
npm run lint       PASS
npm run build      PASS
node --test        5 passed
```

前端测试覆盖：

- Mock 横幅、免责声明、固定 API 契约和 Qwen Mock 标记。
- 空事件数组返回安全的空展示值，不引发趋势计算异常。
- 事件按时间排序、限制窗口并归一化为展示趋势。
- Starter 预览组件和依赖已移除。
- 已配置不含真实数据的 Open Graph / X 分享预览图。
- 生产构建包含 client 与 server 产物。

## API 冒烟结果

```text
GET /healthz                                            200 / ok / mock
GET /api/user/profile/{mock_user_id}                    200
GET /api/health/events/{mock_user_id}?days=30           200 / 120 items / source=mock
GET /api/health/status/{mock_user_id}                    200 / score=87.4
GET /api/agent/plan/{mock_user_id}                       200 / 3 plan sections
Origin: http://localhost:3000                            Access-Control-Allow-Origin matched
```

## 浏览器验收结果

- 页面显示“Mock 验证模式 · API 已连接”。
- 显示固定 35 岁虚构用户、身高、体重、BMI 和代谢健康管理目标。
- 显示 API、Memory Repository、Mock Qwen 与 Mock RAG 状态。
- 显示睡眠、步数、心率、运动时间的 30 天摘要与趋势。
- 健康管理分数为 87.4，标签为 `normal`；无血糖与胰岛素时不伪造 HOMA-IR。
- 点击按钮后显示运动、饮食、睡眠计划、生成理由、`[MOCK:qwen]` 和非医疗诊断声明。
- 关闭后端并刷新时出现可理解的错误与“重新连接”按钮；后端恢复后可重连。
- 390 px 宽度无横向溢出，核心卡片和计划区仍可访问。
- 浏览器控制台无未处理错误。

## 安全与密钥检查

- 前端只读取 `VITE_API_BASE_URL`，不读取任何模型 Key。
- Docker Mock 编排不传入模型 Key。
- 根 `.dockerignore` 排除 `.env`、虚拟环境和前端依赖，避免密钥或本地文件进入 API 镜像上下文。
- 本地 `.env` 处于忽略范围；当前 Qwen Provider 仍为 Mock，不会发起网络请求。
- 页面、测试数据、日志与文档中没有真实姓名或健康隐私数据。

## Docker 实际验收（2026-08-26）

Docker Desktop 4.87.0、Linux Engine 29.7.2 下执行：

```powershell
docker compose -f docker-compose.demo.yml config --quiet
docker compose -f docker-compose.demo.yml up -d --build
docker compose -f docker-compose.demo.yml ps
```

实际结果：

- `api`：`healthy`，映射 `localhost:8000`。
- `web`：`healthy`，映射 `localhost:3000`。
- `GET /healthz`：200，`environment=development`，`data_mode=mock`。
- 30 天健康事件：200，共 120 条。
- 健康状态：200，分数 87.4。
- Agent 计划：200。
- Web 首页：200，响应体 16285 字节。
- API 与 Web 容器日志无启动错误。

首次拉取 `node:24-alpine` 时 Docker Hub IPv6 鉴权连接短暂超时；单独重试镜像拉取后成功，未修改项目代码或系统 DNS。

`npm ci` 在包含开发工具的完整依赖树中显示审计提示；使用官方 registry 执行 `npm audit --omit=dev` 后，生产依赖漏洞结果为 0。开发依赖告警应在后续依赖升级任务中单独评审，不使用 `npm audit fix --force` 自动改动主版本。
