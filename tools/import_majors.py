"""
导入专业到数据库
数据来源：index.xlsx 专业列表
"""

import subprocess
import sys
from pathlib import Path

from src.data.database import Database
from src.services.major_importer import read_majors_from_excel
from src.services.major_service import MajorService


def main():
    """导入专业数据"""
    # 确定Excel文件路径
    excel_path = Path(__file__).parent / "index.xlsx"

    if not excel_path.exists():
        print(f"❌ 错误: 找不到文件 {excel_path}")
        return

    print(f"📂 正在读取专业数据: {excel_path.name}")

    # 从Excel读取专业列表
    try:
        majors = read_majors_from_excel(excel_path)
    except ModuleNotFoundError as error:
        if error.name != "openpyxl":
            raise
        print("❌ 缺少 openpyxl 库，正在安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
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
