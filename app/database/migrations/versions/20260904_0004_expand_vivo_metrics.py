"""扩展统一健康事件指标以接收 vivo 本地 Provider 观测。"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260904_0004"
down_revision: str | None = "20260830_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


BASE_METRICS = (
    "sleep",
    "steps",
    "heart_rate",
    "blood_glucose",
    "insulin",
    "weight",
    "bmi",
    "exercise",
)

VIVO_METRICS = (
    "sleep_total_duration",
    "sleep_night_duration",
    "sleep_nap_duration",
    "sleep_light_duration",
    "sleep_deep_duration",
    "sleep_rem_duration",
    "sleep_awake_duration",
    "sleep_score",
    "sleep_deep_continuity",
    "sleep_awake_episode_count",
    "sleep_awake_episode_duration",
    "distance",
    "calories",
    "heart_rate_resting",
    "spo2",
    "stress",
)


def _constraint(values: tuple[str, ...]) -> str:
    return "metric IN (" + ", ".join(f"'{value}'" for value in values) + ")"


def upgrade() -> None:
    """仅放宽指标约束，不改写已有健康事件。"""

    op.drop_constraint("health_metric_enum", "health_events", type_="check")
    op.create_check_constraint(
        "health_metric_enum",
        "health_events",
        _constraint(BASE_METRICS + VIVO_METRICS),
    )


def downgrade() -> None:
    """恢复基础指标约束；执行前必须先处理扩展指标数据。"""

    op.drop_constraint("health_metric_enum", "health_events", type_="check")
    op.create_check_constraint(
        "health_metric_enum",
        "health_events",
        _constraint(BASE_METRICS),
    )
