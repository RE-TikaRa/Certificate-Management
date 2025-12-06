"""
测试专业导入功能的脚本
"""

import sys
from pathlib import Path

# Ensure the project root is in sys.path
# tools/test_majors.py -> tools/ -> project_root
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.services.major_importer import read_majors_from_excel  # noqa: E402


def test_read_majors():
    excel_path = project_root / "docs" / "index.xlsx"
    print(f"Testing file: {excel_path}")

    if not excel_path.exists():
        print("File not found!")
        return

    try:
        majors = read_majors_from_excel(excel_path)
        print(f"Successfully read {len(majors)} majors.")
        if majors:
            print(f"First major: {majors[0]}")
            print(f"Last major: {majors[-1]}")

            # Print first 5 for verification
            print("\nFirst 5 entries:")
            for i, m in enumerate(majors[:5]):
                print(f"{i + 1}. {m}")

    except Exception as e:
        print(f"Error reading excel: {e}")


if __name__ == "__main__":
    test_read_majors()
