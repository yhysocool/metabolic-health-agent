"""以协议隔离业务层和具体持久化技术。"""

from app.repositories.base import HealthRepository
from app.repositories.memory import InMemoryHealthRepository
from app.repositories.nhanes_reference import NHANESReferenceRepository
from app.repositories.reference import PopulationReference, PopulationReferenceRepository

__all__ = [
    "HealthRepository",
    "InMemoryHealthRepository",
    "NHANESReferenceRepository",
    "PopulationReference",
    "PopulationReferenceRepository",
]
