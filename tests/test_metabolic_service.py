"""基础代谢计算的确定性单元测试。"""

import pytest

from app.schemas.health import HealthLabel
from app.services.metabolic_service import MetabolicService


def test_calculate_bmi() -> None:
    assert MetabolicService.calculate_bmi(70, 175) == 22.86


def test_calculate_homa_ir() -> None:
    assert MetabolicService.calculate_homa_ir(insulin=10, glucose=5.5) == 2.44


def test_calculate_bmi_rejects_invalid_input() -> None:
    with pytest.raises(ValueError):
        MetabolicService.calculate_bmi(70, 0)


def test_score_classification_is_non_diagnostic_label() -> None:
    assert MetabolicService.classify_health_score(85) == HealthLabel.NORMAL
    assert MetabolicService.classify_health_score(70) == HealthLabel.ATTENTION
    assert MetabolicService.classify_health_score(50) == HealthLabel.HIGH_ATTENTION

