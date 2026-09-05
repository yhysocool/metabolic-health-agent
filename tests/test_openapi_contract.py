"""确保公开 API 不会在未审查时偏离冻结的 OpenAPI 契约。"""

import json
from pathlib import Path

from app.main import app


BASELINE_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "contracts"
    / f"openapi-v{app.version}.json"
)


def test_openapi_matches_reviewed_baseline() -> None:
    """接口有意变更时，应审查差异后显式重新导出基线。"""

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    assert app.openapi() == baseline
