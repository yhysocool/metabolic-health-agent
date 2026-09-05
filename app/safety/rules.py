"""对 Agent 计划进行确定性安全校验。"""

from app.schemas.plan import HealthPlanDraft, SafetyValidation


class SafetyRuleEngine:
    """拦截极端减重、自动诊断和药物调整建议。

    规则引擎是 LLM 之外的强制门禁。真实上线前应扩充为版本化规则、结构化剂量检测、
    人工复核和审计日志；当前实现只建立不可绕过的接口位置。
    """

    forbidden_patterns: dict[str, str] = {
        "禁食": "禁止建议极端禁食",
        "断食三天": "禁止建议长时间断食",
        "每天不超过500卡": "禁止建议极低热量饮食",
        "每天不超过 500 卡": "禁止建议极低热量饮食",
        "诊断为": "系统不能自动作出医疗诊断",
        "确诊": "系统不能自动作出医疗诊断",
        "自行停药": "禁止建议用户自行停药",
        "调整药物剂量": "禁止提供药物剂量调整建议",
        "double your dose": "禁止提供药物剂量调整建议",
    }

    def validate_plan(self, plan: HealthPlanDraft) -> SafetyValidation:
        """扫描完整计划；命中任一规则即拒绝保存。"""

        text = "\n".join(
            [
                *plan.exercise_plan,
                *plan.diet_plan,
                *plan.sleep_plan,
                plan.reason,
            ]
        ).lower()
        issues = [
            reason
            for pattern, reason in self.forbidden_patterns.items()
            if pattern.lower() in text
        ]
        return SafetyValidation(safe=not issues, issues=sorted(set(issues)))

