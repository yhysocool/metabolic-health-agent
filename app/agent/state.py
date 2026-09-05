"""LangGraph 节点之间传递的显式状态。"""

from typing import TypedDict

from app.rag.retriever import RetrievedDocument
from app.schemas.health import HealthEvent, HealthStatus, TrendDirection
from app.schemas.plan import HealthPlan, HealthPlanDraft, SafetyValidation
from app.schemas.user import UserProfile


class AgentState(TypedDict, total=False):
    """Agent 工作流状态；仅 ``user_id`` 由调用方初始提供。"""

    user_id: str
    user_profile: UserProfile
    health_events: list[HealthEvent]
    health_status: HealthStatus
    trend: dict[str, TrendDirection]
    retrieved_docs: list[RetrievedDocument]
    plan_draft: HealthPlanDraft
    safety_validation: SafetyValidation
    plan: HealthPlan

