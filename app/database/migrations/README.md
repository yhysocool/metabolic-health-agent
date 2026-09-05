# 数据库迁移

该目录由 Alembic 管理。模型调整后先审查自动生成的迁移，再执行：

```bash
alembic upgrade head
```

不要在应用启动时调用 `Base.metadata.create_all()`；生产数据库结构必须通过可审计迁移演进。

