"""Agent 可调用的领域工具；每个工具只承担一个明确职责。"""

from datetime import datetime, timedelta, timezone

from app.rag.retriever import BaseRetriever, RetrievedDocument
from app.repositories.base import HealthRepository
from app.safety.rules import SafetyRuleEngine
from app.schemas.health import HealthEvent, HealthStatus, TrendDirection
from app.schemas.plan import HealthPlanDraft, SafetyValidation
from app.schemas.user import UserProfile
from app.services.health_service import HealthService
from app.services.trend_service import TrendService


async def get_user_profile(
    repository: HealthRepository, user_id: str
) -> UserProfile:
    """读取用户档案，不存在时终止工作流。"""

    profile = await repository.get_user(user_id)
    if profile is None:
        raise LookupError(f"用户 {user_id} 不存在")
    return profile


async def get_recent_health_data(
    repository: HealthRepository, user_id: str, days: int = 30
) -> list[HealthEvent]:
    """读取指定回看窗口内的标准健康事件。"""

    since = datetime.now(timezone.utc) - timedelta(days=days)
    return await repository.get_events(user_id, since)


def calculate_metabolic_status(
    repository: HealthRepository,
    profile: UserProfile,
    events: list[HealthEvent],
) -> HealthStatus:
    """调用纯业务服务生成非诊断性健康状态。"""

    return HealthService(repository).assess_health(profile, events)


def analyze_health_trend(events: list[HealthEvent]) -> dict[str, TrendDirection]:
    """生成睡眠、活动和体重三个稳定趋势键。"""

    service = TrendService()
    return {
        "sleep": service.analyze_sleep(events),
        "activity": service.analyze_activity(events),
        "weight": service.analyze_weight(events),
    }


def retrieve_guideline(
    retriever: BaseRetriever, query: str, top_k: int = 3
) -> list[RetrievedDocument]:
    """通过可替换 Retriever 获取健康管理参考资料。"""

    return retriever.retrieve(query, top_k)


def validate_health_plan(
    safety_engine: SafetyRuleEngine, plan: HealthPlanDraft
) -> SafetyValidation:
    """在持久化前执行确定性安全门禁。"""

    return safety_engine.validate_plan(plan)

