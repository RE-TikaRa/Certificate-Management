"""
导入专业到数据库
数据来源：index.xlsx 专业列表
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.database import Database
from src.services.major_service import MajorService


def read_majors_from_excel(excel_path: Path) -> list[str]:
    """
    从Excel文件读取专业列表

    Args:
        excel_path: Excel文件路径

    Returns:
        专业名称列表
    """
    try:
        import openpyxl
    except ImportError:
        print("❌ 缺少 openpyxl 库，正在安装...")
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
        import openpyxl

    majors = []

    # 打开Excel文件
    wb = openpyxl.load_workbook(excel_path)
    ws = wb.active

    # 读取所有行(第3列是专业名称,索引为2)
    for row in ws.iter_rows(min_row=2, values_only=True):  # 跳过表头
        if len(row) > 2 and row[2]:  # 确保第3列有值
            major_name = str(row[2]).strip()
            if major_name and major_name != "专业名称":  # 排除空值和表头
                majors.append(major_name)

    wb.close()
    return majors


def main():
    """导入专业数据"""
    # 确定Excel文件路径
    excel_path = Path(__file__).parent / "index.xlsx"

    if not excel_path.exists():
        print(f"❌ 错误: 找不到文件 {excel_path}")
        return

    print(f"📂 正在读取专业数据: {excel_path.name}")

    # 从Excel读取专业列表
    majors = read_majors_from_excel(excel_path)

    if not majors:
        print("❌ 错误: Excel文件中没有找到专业数据")
        return

    print(f"成功读取 {len(majors)} 个专业")

    # 初始化数据库
    db = Database()
    db.initialize()

    service = MajorService(db)

    # 清空并重新导入专业
    print("\n正在清空现有专业数据并重新导入...")
    count = service.replace_all_majors(majors)

    print(f"成功导入 {count} 个专业")

    # 验证
    all_majors = service.get_all_majors()
    print(f"\n数据库中共有 {len(all_majors)} 个专业")

    # 测试搜索
    print("\n测试搜索功能:")
    test_queries = ["机械", "农", "经济", "林"]
    for query in test_queries:
        results = service.search_majors(query, limit=5)
        print(f"  '{query}' -> {len(results)} 个结果: {[m.name for m in results[:3]]}")


if __name__ == "__main__":
    main()
