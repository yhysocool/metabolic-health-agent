from __future__ import annotations

import json
from pathlib import Path

from app.repositories.nhanes_reference import NHANESReferenceRepository


def _write_reference(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "reference_id": "test-reference",
                "source": {
                    "dataset": "NHANES public-use data",
                    "weighted_statistics": False,
                },
                "age_bands": [{"label": "30-39", "min": 30, "max": 39}],
                "genders": ["female", "male"],
                "metrics": [{"metric_code": "body.BMI_kg_m2", "unit": "kg/m²"}],
                "strata": [
                    {
                        "age_band": "30-39",
                        "gender": "female",
                        "records": 2,
                        "metrics": {
                            "body.BMI_kg_m2": {
                                "observed": 2,
                                "missing": 0,
                                "mean": 23.0,
                                "stddev": 2.0,
                                "min": 21.0,
                                "p25": 21.5,
                                "median": 23.0,
                                "p75": 24.5,
                                "max": 25.0,
                            }
                        },
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_nhanes_reference_repository_returns_exact_stratum(tmp_path: Path) -> None:
    path = tmp_path / "reference.json"
    _write_reference(path)
    reference = NHANESReferenceRepository(path).get_statistic(
        age=34,
        gender="female",
        metric_code="body.BMI_kg_m2",
    )

    assert reference is not None
    assert reference.status == "PASS"
    assert reference.age_band == "30-39"
    assert reference.statistics["median"] == 23.0


def test_nhanes_reference_repository_does_not_fallback_to_other_gender(
    tmp_path: Path,
) -> None:
    path = tmp_path / "reference.json"
    _write_reference(path)
    reference = NHANESReferenceRepository(path).get_statistic(
        age=34,
        gender="male",
        metric_code="body.BMI_kg_m2",
    )

    assert reference is None
