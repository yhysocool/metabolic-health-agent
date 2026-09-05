"""聚合档案、健康事件和基础分析结果的应用服务。"""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from statistics import fmean

from app.config import get_settings
from app.repositories.base import HealthRepository
from app.schemas.health import HealthEvent, HealthEventCreate, HealthMetric, HealthStatus
from app.schemas.user import UserProfile
from app.services.metabolic_service import MetabolicService
from app.services.trend_service import TrendService


class HealthService:
    """协调仓储和纯计算服务，不包含 HTTP 或 ORM 细节。"""

    def __init__(
        self,
        repository: HealthRepository,
        metabolic: MetabolicService | None = None,
        trends: TrendService | None = None,
    ) -> None:
        self.repository = repository
        self.metabolic = metabolic or MetabolicService()
        self.trends = trends or TrendService()

    async def create_event(self, event: HealthEventCreate) -> HealthEvent:
        """校验用户存在后保存标准事件。"""

        if await self.repository.get_user(event.user_id) is None:
            raise LookupError(f"用户 {event.user_id} 不存在")
        return await self.repository.add_event(event)

    async def get_status(self, user_id: str) -> HealthStatus:
        """加载最近事件并返回健康管理状态。"""

        profile = await self._require_user(user_id)
        events = await self.get_recent_events(
            user_id, days=get_settings().health_lookback_days
        )
        return self.assess_health(profile, events)

    async def get_recent_events(self, user_id: str, days: int) -> list[HealthEvent]:
        """按时间升序返回指定窗口内的标准健康事件。"""

        await self._require_user(user_id)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        return await self.repository.get_events(user_id, since)

    async def _require_user(self, user_id: str) -> UserProfile:
        """集中处理用户存在性校验，保持 API 错误语义一致。"""

        profile = await self.repository.get_user(user_id)
        if profile is None:
            raise LookupError(f"用户 {user_id} 不存在")
        return profile

    def assess_health(
        self, profile: UserProfile, events: Sequence[HealthEvent]
    ) -> HealthStatus:
        """基于已提供数据生成可解释结果，不推断缺失医学指标。"""

        metric_values: dict[HealthMetric, list[float]] = {}
        for event in events:
            metric_values.setdefault(event.metric, []).append(event.value)

        sleep = metric_values.get(HealthMetric.SLEEP, [])
        steps = metric_values.get(HealthMetric.STEPS, [])
        average_sleep = fmean(sleep) if sleep else None
        average_steps = fmean(steps) if steps else None
        bmi = self.metabolic.calculate_bmi(profile.weight, profile.height)
        score = self.metabolic.calculate_health_score(
            bmi=bmi,
            average_sleep_hours=average_sleep,
            average_steps=average_steps,
        )

        glucose = metric_values.get(HealthMetric.BLOOD_GLUCOSE, [])
        insulin = metric_values.get(HealthMetric.INSULIN, [])
        homa_ir = None
        if glucose and insulin:
            homa_ir = self.metabolic.calculate_homa_ir(insulin[-1], glucose[-1])

        observations: list[str] = []
        if average_sleep is None:
            observations.append("缺少睡眠数据，本次评分未包含睡眠维度。")
        else:
            observations.append(f"最近数据中的平均睡眠时长约为 {average_sleep:.1f} 小时。")
        if average_steps is None:
            observations.append("缺少步数数据，本次评分未包含活动维度。")
        else:
            observations.append(f"最近数据中的平均每日步数约为 {average_steps:.0f} 步。")
        if homa_ir is None:
            observations.append("未同时取得血糖和胰岛素数据，因此未计算 HOMA-IR。")

        trends = {
            "sleep": self.trends.analyze_sleep(events),
            "activity": self.trends.analyze_activity(events),
            "weight": self.trends.analyze_weight(events),
        }
        if events and all(event.source.value == "synthetic" for event in events):
            data_notice = "本结果完全由本地合成演示数据生成，没有连接真人或穿戴设备数据。"
        elif any(event.source.value == "synthetic" for event in events):
            data_notice = "本结果包含合成演示数据，请结合每条事件的来源说明理解。"
        else:
            data_notice = "本结果基于当前已提供的数据生成，请核对各事件来源和完整性。"
        return HealthStatus(
            user_id=profile.id,
            score=score,
            label=self.metabolic.classify_health_score(score),
            bmi=bmi,
            homa_ir=homa_ir,
            trends=trends,
            observations=observations,
            data_notice=data_notice,
        )
