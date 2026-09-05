"""确定性健康数据质量报告服务。"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import fmean

from app.repositories.base import HealthRepository
from app.repositories.collection_runs import CollectionRunRepository
from app.schemas.report import DataQualityReport, MetricQualitySummary
from app.schemas.integration import IntegrationProvider


class DataQualityReportService:
    """只根据真实已保存事件和采集摘要生成报告，不做疾病推断。"""

    def __init__(
        self,
        health_repository: HealthRepository,
        collection_repository: CollectionRunRepository,
    ) -> None:
        self._health_repository = health_repository
        self._collection_repository = collection_repository

    async def build(self, user_id: str, days: int) -> DataQualityReport:
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=days)
        events = await self._health_repository.get_events(user_id, since)
        runs = await self._collection_repository.list_runs(user_id, since)
        state = await self._health_repository.get_integration_state(
            user_id, IntegrationProvider.VIVO
        )

        grouped: dict[tuple[str, str], list] = defaultdict(list)
        for event in events:
            grouped[(_enum_value(event.metric), event.unit)].append(event)

        metric_summaries: list[MetricQualitySummary] = []
        for (metric, unit), items in sorted(grouped.items()):
            values = [item.value for item in items]
            timestamps = [item.timestamp for item in items]
            metric_summaries.append(
                MetricQualitySummary(
                    metric=metric,
                    unit=unit,
                    records=len(items),
                    covered_days=len({item.timestamp.date() for item in items}),
                    first_at=min(timestamps),
                    last_at=max(timestamps),
                    min_value=min(values),
                    average_value=round(fmean(values), 4),
                    max_value=max(values),
                    zero_value_count=sum(1 for value in values if value == 0),
                )
            )

        event_timestamps = [event.timestamp for event in events]
        run_status_counts: dict[str, int] = defaultdict(int)
        provider_rows = 0
        valid_records = 0
        for run in runs:
            run_status_counts[_enum_value(run.status)] += 1
            provider_rows += run.provider_row_count
            valid_records += run.valid_record_count

        notices: list[str] = []
        if not events:
            notices.append("当前窗口没有可用于分析的 PASS 健康事件。")
        if len({timestamp.date() for timestamp in event_timestamps}) < 7:
            notices.append("有效数据日不足 7 天，当前只能做覆盖和描述性统计。")
        if not runs:
            notices.append("当前窗口没有采集运行诊断，无法判断 Provider 是否曾返回空数据或权限错误。")
        if any(item.zero_value_count for item in metric_summaries):
            notices.append("部分指标出现 0 值；需结合 Provider 原始字段确认其是真实值还是缺失占位。")
        if state is not None and event_timestamps:
            latest_event = max(event_timestamps)
            if state.last_success_at > latest_event + timedelta(hours=6):
                notices.append("同步成功时间晚于最新测量时间较多，需检查 Provider 更新和手机采集，而不只是检查上传接口。")

        return DataQualityReport(
            user_id=user_id,
            window_days=days,
            generated_at=now,
            event_count=len(events),
            coverage_days=len({timestamp.date() for timestamp in event_timestamps}),
            first_event_at=min(event_timestamps) if event_timestamps else None,
            last_event_at=max(event_timestamps) if event_timestamps else None,
            collection_run_count=len(runs),
            collection_status_counts=dict(sorted(run_status_counts.items())),
            provider_rows=provider_rows,
            valid_records=valid_records,
            last_sync_at=state.last_success_at if state is not None else None,
            metrics=metric_summaries,
            notices=notices,
        )


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))
