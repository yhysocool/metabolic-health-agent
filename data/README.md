# 数据目录

当前阶段不包含任何真实用户或设备数据。

- `raw/`：未来保存只读原始输入；禁止将隐私数据提交到版本库。
- `processed/`：未来保存可重建的标准化中间结果。
- `reference/`：只保存经过聚合的数据参考，不允许包含参与者级记录。
- 向量索引应放入未跟踪的 `data/vector_store/`，并记录语料版本与生成参数。

`reference/nhanes_adult_30_39_reference_v1.json` 是从项目 NHANES 公共数据
流水线的 11,848 条成人记录中提取的 30–39 岁聚合描述统计。它只包含样本量、
四分位数和来源摘要，不包含 SEQN、用户 ID 或其他单人记录。该文件仅用于本地
合成演示校准，不能解释为中国人群参考范围、临床阈值或设备测量。

`reference/nhanes_stratified_reference_v1.json` 是当前研究参照文件，按年龄段、
性别和指标保存聚合描述统计。主项目通过只读 `NHANESReferenceRepository` 和
`GET /api/research/nhanes/reference` 查询它，不会把 NHANES 个体记录写入
`HealthEvent`。当前结果为未加权描述统计，仅用于人群参照、规则测试和 Agent
解释输入；正式人群估计仍需使用 NHANES 对应权重、PSU 和 strata。

接入 NHANES、vivo 或医院脱敏数据前，必须先完成授权、字段字典、单位映射、质量校验和数据留存策略。
