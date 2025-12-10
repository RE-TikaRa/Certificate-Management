# Certificate Management System – AI Agent Guide

欢迎来到荣誉证书管理系统的开发助手指南。本文件面向自动化/AI 代理，提供项目快速事实、代码规范、命令和常见改动提示，保持简洁可操作。

## 快速概要
- 应用：荣誉证书管理桌面端（PySide6 + QFluentWidgets）
- 语言/平台：Python 3.14+，SQLite + SQLAlchemy 2.x
- 入口：`uv run python -m src.main`（Windows 可用 `main.bat`）；调试加 `--debug`
- 数据目录：`data/`（awards.db），`attachments/`，`backups/`，`logs/`，`temp/` 均已被 `.gitignore` 忽略（含 SQLite 辅助文件 *.db-wal / *.db-shm）

## 常用命令
- 安装依赖：`uv sync`
- 运行：`uv run python -m src.main`
- 调试：`uv run python -m src.main --debug`
- 语法检查：`python -m py_compile src/`
- Lint：`uv run ruff check .`
- 格式化：`uv run ruff format .`
- 类型检查：`uv run pyright`
- 入口脚本：`certificate-management = src.main:main`

## 目录速览
- `src/main.py` 应用入口；`app_context.py` 构建 DI 容器与服务；`logger.py` 日志配置；`config.py` 配置加载。
- 数据层 `src/data/`: `models.py`（Base + Award/TeamMember/Attachment/Setting/BackupRecord/ImportJob/Major/School/SchoolMajorMapping/AwardMember）；`database.py` 提供 `session_scope`。
- 服务层 `src/services/`: award_service、statistics_service、import_export、backup_manager、attachment_manager、settings_service、major_service 等。
- 表现层 `src/ui/`: `main_window.py`（窗口与导航，懒加载页面，窗口居中），`styled_theme.py`（ThemeManager），`theme.py`（通用 UI 工具），`widgets/major_search.py`，`pages/`（home、dashboard、overview、entry、management、recycle、settings、about、base_page）。
- 资源 `src/resources/`: `styles/styled_light.qss`、`styles/styled_dark.qss`，`templates/awards_template.csv`。
- 数据/文档 `docs/`: `china_bachelor_majors_2025.csv`（本科专业目录约 840 条）、`china_universities_2025.csv`、`GSAU_majors.xlsx` 示例映射、`personal_info_template.doc`。

## 模型与数据
- Base：统一主键、自增、时间戳。
- Award：competition_name、award_date、level、rank、certificate_code、remarks、attachment_folder、deleted/deleted_at；关系 members（m2m）与 attachments（级联删除）。
- TeamMember：姓名、性别、身份证（唯一）、手机号、学号（唯一）、邮箱、学校/学校代码、专业/专业代码、班级、学院、pinyin、active、sort_index；关系 awards（m2m）。
- Attachment：award_id、stored_name、original_name、relative_path（唯一）、file_md5、file_size、deleted 标记。
- Setting/BackupRecord/ImportJob：应用设置、备份记录、导入任务。
- Major：name/code 唯一，含学科/专业类信息与 pinyin；School、SchoolMajorMapping 存储学校与学校-专业-学院映射。
- 专业与学校数据源：`docs/china_bachelor_majors_2025.csv`（约 840 条）+ `china_universities_2025.csv`；搜索支持中文/拼音/代码，学校代码缺失时回退学校名称匹配学院。

## 主要特性（按页面）
- **MainWindow**：`_center_window()` 居中；快速加载首页，余下页面 100ms 后异步载入；route_keys 管理导航；主题变化事件转发。
- **Dashboard**：8 个梯度指标卡 + 饼/柱图 + 最近荣誉表（只读）。颜色：总紫、国家蓝、省金、校绿、一等青、二等紫粉、三等红、优秀蓝。
- **Entry**：动态成员卡两列布局；字段覆盖姓名/性别/身份证/手机号/学号/邮箱/学校/学校代码/专业/专业代码/班级/学院；集成 MajorSearchWidget（中文/拼音/代码自动完成，最多 8 条）。
- **Overview**：列表卡；FTS5 全文搜索（比赛名/证书号/成员），筛选（级别/奖项/日期范围）、8 种排序（日期/级别/奖项/名称正反），500ms 防抖；分页与重置；编辑对话框可增删成员，保存后通过父链刷新管理页。
- **Management**：成员列表与详情；核心字段含学校/学院/专业代码，支持自动刷新。
- **Recycle**：附件回收与还原/彻底删除。
- **Settings**：主题、自动备份频率、日志级别、数据目录；备份列表验证/恢复前可自动备份；索引重建按钮；导入/导出日志面板；清理工具卡片（日志/备份/数据库/一键清空，均双重确认）。
- **About**：版本/特性/技术栈/链接。

## 主题与 UI 约定
- ThemeManager（`styled_theme.py`）提供 `is_dark`、`themeChanged`、`get_window_stylesheet()`、`apply_theme_color()`。
- 有动态子组件的页面/对话框：在 `__init__` 早期连接 `themeChanged`（@Slot），调用 `_apply_theme()` 并用 `findChildren()` 更新所有输入组件样式；静态部分由 QSS 负责。
- 组件卡片多带阴影（blur 28，offset 0,8）；动画场景下可能卡顿，性能优化可考虑减弱阴影或启用 OpenGL。

## 代码风格
- Ruff 配置：行宽 120、缩进 4、目标 py314、双引号；已豁免 Qt 命名/复杂度规则。运行 `uv run ruff check .` / `uv run ruff format .`。
- Pyright 配置：basic 模式类型检查；与 ruff 分工——ruff 负责代码风格和 unused import/variable，pyright 负责类型检查。运行 `uv run pyright`。
- 采用现代类型标注（`list[str]`, `| None`），无需 `__future__`；尽量添加 docstring。
- 使用 loguru 日志，避免 `print`。
- 保持导入有序、移除未用依赖；少量必要注释，遵循现有风格。

## 开发/修改提示
- 访问服务总用 `AppContext`（ctx.awards/statistics/settings/members/attachment/backup/major），数据库操作包裹 `session_scope`，勿手写裸会话。
- 添加页面：继承 `BasePage`，实现 `_init_ui`；在 `main_window.py` 注册（导航项、_load_* 分组、route_keys），按需处理主题信号。
- 添加数据字段：同步更新模型、对应 service、UI 表单/列表、统计或刷新逻辑（管理页的 10 字段监控需保持一致）。
- 成员字段在 UI 约定为 10 项（含学校）；管理页刷新依赖该集合。
- 导入/导出：CSV 模板 `resources/templates/awards_template.csv`；专业与学校/学院映射导入来自 `docs/china_bachelor_majors_2025.csv`、`china_universities_2025.csv`、`GSAU_majors.xlsx`。
- 导入荣誉：支持 CSV/XLSX，带预检、错误行导出、进度 ETA；导入/预检记录写入 imports 表并显示在设置页日志面板。
- 学院自动填充依赖 `SchoolMajorMapping`，如导入数据缺少学校代码会自动用学校名称回退匹配；若要禁用回退需同步保证 school_code 完整。
- 运行/调试前确认运行目录为仓库根目录；避免提交 `data/`、`attachments/`、`backups/`、`logs/`、`temp/` 生成物。
