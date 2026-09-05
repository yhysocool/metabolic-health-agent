"""可解释的基础代谢健康计算，不承担医学诊断。"""

from statistics import fmean

from app.schemas.health import HealthLabel


class MetabolicService:
    """封装稳定、可单元测试的基础计算函数。"""

    @staticmethod
    def calculate_bmi(weight_kg: float, height_cm: float) -> float:
        """按 kg/m² 计算 BMI。"""

        if weight_kg <= 0 or height_cm <= 0:
            raise ValueError("身高和体重必须大于 0")
        height_m = height_cm / 100
        return round(weight_kg / (height_m * height_m), 2)

    @staticmethod
    def calculate_homa_ir(insulin: float, glucose: float) -> float:
        """按 insulin × glucose / 22.5 计算 HOMA-IR。

        该公式假定胰岛素单位为 μU/mL、血糖单位为 mmol/L。结果仅供趋势管理参考。
        """

        if insulin < 0 or glucose < 0:
            raise ValueError("胰岛素和血糖值不能为负数")
        return round(insulin * glucose / 22.5, 2)

    @staticmethod
    def calculate_health_score(
        *,
        bmi: float,
        average_sleep_hours: float | None = None,
        average_steps: float | None = None,
    ) -> float:
        """组合可用指标生成 0–100 的非临床健康管理分数。

        缺失指标不会被虚构，而是直接不参与平均；当前权重仅是 Mock 规则，后续应由
        临床顾问和数据验证共同校准。
        """

        component_scores = [max(0.0, 100.0 - abs(bmi - 22.0) * 7.0)]
        if average_sleep_hours is not None:
            component_scores.append(
                max(0.0, 100.0 - abs(average_sleep_hours - 8.0) * 18.0)
            )
        if average_steps is not None:
            component_scores.append(min(100.0, max(0.0, average_steps / 8000 * 100)))
        return round(fmean(component_scores), 1)

    @staticmethod
    def classify_health_score(score: float) -> HealthLabel:
        """将分数映射为健康关注等级，而不是疾病等级。"""

        if score >= 80:
            return HealthLabel.NORMAL
        if score >= 60:
            return HealthLabel.ATTENTION
        return HealthLabel.HIGH_ATTENTION

