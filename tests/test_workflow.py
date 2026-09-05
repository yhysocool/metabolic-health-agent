"""LangGraph 端到端 Mock 工作流测试。"""

import pytest

from app.adapters.mock_adapter import MockHealthAdapter
from app.agent.workflow import build_health_agent, generate_health_plan
from app.llm.base import BaseLLM, ChatMessage
from app.repositories.memory import InMemoryHealthRepository
from app.schemas.plan import HealthPlan, HealthPlanDraft
from app.schemas.user import Gender, HealthGoal, UserProfileCreate


class UnsafeMockLLM(BaseLLM):
    """仅用于证明 LLM 文本也必须经过确定性安全门禁。"""

    async def chat(self, messages: list[ChatMessage]) -> str:
        assert messages
        return "连续禁食以快速减重"


class SaveCountingRepository(InMemoryHealthRepository):
    """记录保存次数，验证危险草案不会触达持久化边界。"""

    def __init__(self) -> None:
        super().__init__()
        self.plan_save_count = 0

    async def save_plan(self, plan: HealthPlanDraft) -> HealthPlan:
        self.plan_save_count += 1
        return await super().save_plan(plan)


async def seed_user(repository: InMemoryHealthRepository, user_id: str) -> None:
    profile = UserProfileCreate(
        id=user_id,
        age=36,
        gender=Gender.UNDISCLOSED,
        height=170,
        weight=70,
        goal=HealthGoal.METABOLIC_HEALTH,
    )
    await repository.save_user(profile)
    for event in MockHealthAdapter(days=30).collect(profile.id):
        await repository.add_event(event)


@pytest.mark.asyncio
async def test_agent_generates_and_saves_safe_plan() -> None:
    repository = InMemoryHealthRepository()
    user_id = "workflow-user"
    await seed_user(repository, user_id)

    plan = await generate_health_plan(repository, user_id)

    assert plan.user_id == user_id
    assert plan.exercise_plan
    assert "不构成医疗诊断或治疗建议" in plan.reason


@pytest.mark.asyncio
async def test_agent_rejects_unsafe_llm_output_before_save() -> None:
    repository = SaveCountingRepository()
    user_id = "unsafe-workflow-user"
    await seed_user(repository, user_id)
    agent = build_health_agent(repository, llm=UnsafeMockLLM())

    with pytest.raises(ValueError, match="禁止建议极端禁食"):
        await agent.ainvoke({"user_id": user_id})

    assert repository.plan_save_count == 0
