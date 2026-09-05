"""NHANES 聚合参照的本地只读实现。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.repositories.reference import PopulationReference


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REFERENCE_PATH = PROJECT_ROOT / "data" / "reference" / "nhanes_stratified_reference_v1.json"


class NHANESReferenceRepository:
    """只读取分层统计 JSON，不读取或写入 NHANES 个体记录。"""

    def __init__(self, reference_path: Path = DEFAULT_REFERENCE_PATH) -> None:
        self.reference_path = reference_path
        self._payload: dict[str, Any] | None = None

    def _load(self) -> dict[str, Any]:
        if self._payload is not None:
            return self._payload
        payload = json.loads(self.reference_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1:
            raise ValueError("不支持的 NHANES 聚合参照 schema_version")
        if not payload.get("reference_id") or not payload.get("strata"):
            raise ValueError("NHANES 聚合参照缺少 reference_id 或 strata")
        source = payload.get("source")
        if not isinstance(source, dict) or source.get("weighted_statistics") is not False:
            raise ValueError("NHANES 聚合参照必须明确标记为未加权描述统计")
        self._payload = payload
        return payload

    @staticmethod
    def _find_age_band(payload: dict[str, Any], age: int) -> dict[str, Any] | None:
        for band in payload.get("age_bands", []):
            if int(band["min"]) <= age <= int(band["max"]):
                return band
        return None

    def get_statistic(
        self, *, age: int, gender: str, metric_code: str
    ) -> PopulationReference | None:
        if age < 18 or age > 100:
            return None
        payload = self._load()
        gender = gender.lower()
        if gender not in payload.get("genders", []):
            return None
        metric = next(
            (item for item in payload.get("metrics", []) if item.get("metric_code") == metric_code),
            None,
        )
        if metric is None:
            return None
        band = self._find_age_band(payload, age)
        if band is None:
            return None
        stratum = next(
            (
                item
                for item in payload["strata"]
                if item.get("age_band") == band["label"]
                and item.get("gender") == gender
            ),
            None,
        )
        if stratum is None:
            return None
        statistics = stratum.get("metrics", {}).get(metric_code)
        if not isinstance(statistics, dict):
            return None
        observed = int(statistics.get("observed", 0))
        return PopulationReference(
            reference_id=str(payload["reference_id"]),
            source=str(payload["source"]["dataset"]),
            metric_code=metric_code,
            unit=str(metric["unit"]),
            age_band=str(band["label"]),
            age_min=int(band["min"]),
            age_max=int(band["max"]),
            gender=gender,
            records=int(stratum.get("records", 0)),
            statistics=statistics,
            status="PASS" if observed > 0 else "NO_DATA",
            note="NHANES 未加权描述统计，仅用于人群参照，不代表当前用户，也不构成诊断。",
        )
