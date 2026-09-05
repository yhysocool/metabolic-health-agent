"""安全规则必须独立于模型响应生效。"""

from datetime import date

from app.safety.rules import SafetyRuleEngine
from app.schemas.plan import HealthPlanDraft


def make_plan(diet_item: str) -> HealthPlanDraft:
    return HealthPlanDraft(
        user_id="test-user",
        date=date.today(),
        exercise_plan=["温和步行"],
        diet_plan=[diet_item],
        sleep_plan=["固定作息"],
        reason="用于健康习惯管理，不构成医疗建议。",
    )


def test_safe_plan_passes() -> None:
    result = SafetyRuleEngine().validate_plan(make_plan("保持规律、均衡饮食"))
    assert result.safe is True
    assert result.issues == []


def test_extreme_diet_plan_is_rejected() -> None:
    result = SafetyRuleEngine().validate_plan(make_plan("连续禁食以快速减重"))
    assert result.safe is False
    assert "禁止建议极端禁食" in result.issues

