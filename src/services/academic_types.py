from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SchoolInput:
    name: str
    code: str | None = None
    region: str | None = None


@dataclass(frozen=True)
class MajorCatalogInput:
    major_name: str
    major_code: str | None = None
    discipline_code: str | None = None
    discipline_name: str | None = None
    class_code: str | None = None
    class_name: str | None = None
    category: str | None = None


@dataclass(frozen=True)
class SchoolMajorMappingInput:
    school_name: str
    major_name: str
    major_code: str | None = None
    school_code: str | None = None
    college_name: str | None = None
    category: str | None = None
    discipline_code: str | None = None
    discipline_name: str | None = None
