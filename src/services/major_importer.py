"""
兼容旧接口的专业导入工具，内部复用 school_importer。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .academic_types import MajorCatalogInput, SchoolMajorMappingInput
from .school_importer import read_major_catalog, read_school_major_mappings

if TYPE_CHECKING:
    from .major_service import MajorService


def read_majors_from_excel(excel_path: Path) -> list[SchoolMajorMappingInput]:
    """兼容旧接口：读取学校-专业映射"""
    return read_school_major_mappings(excel_path)


def read_major_catalog_from_csv(csv_path: Path) -> list[MajorCatalogInput]:
    return read_major_catalog(csv_path)


def import_majors_from_excel(service: MajorService, excel_path: Path) -> int:
    """使用 MajorService upsert 映射数据"""
    records = read_majors_from_excel(excel_path)
    if not records:
        return 0
    inserted, updated = service.upsert_school_major_mappings(records)
    return inserted + updated
