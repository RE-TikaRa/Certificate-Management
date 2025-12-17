# Certificate Management System – AI Agent Guide

欢迎来到荣誉证书管理系统的开发助手指南。本文件面向自动化/AI 代理，提供项目快速事实、代码规范、命令和常见改动提示，保持简洁可操作。

## 快速概要
- 应用：荣誉证书管理桌面端（PySide6 + QFluentWidgets）
- 语言/平台：Python 3.14+，SQLite + SQLAlchemy 2.x
- 入口：`uv run python -m src.main`（Windows 可用 `main.bat`）；调试加 `--debug`
- AI：内置“AI 证书识别”（OpenAI 兼容 API），支持多 Provider 与 API Key 轮换；配置入口在设置页
- 数据目录：`data/`（awards.db），`attachments/`，`backups/`，`logs/`，`temp/` 均已被 `.gitignore` 忽略（含 SQLite 辅助文件 *.db-wal / *.db-shm）

## 常用命令
- 安装依赖：`uv sync`
- 运行：`uv run python -m src.main`
- 调试：`uv run python -m src.main --debug`
- MCP（默认只读）：`uv run certificate-mcp`（默认 stdio；可切 SSE，本地）
- MCP Web（可选）：`uv sync --group mcp-web` 后 `uv run certificate-mcp-web`
- MCP 账号：设置页 → MCP 服务，可修改/随机用户名、重置/复制密码，改后重启 MCP Web 生效
- 语法检查：`python -m py_compile src/`
- Lint：`uv run ruff check .`
- 格式化：`uv run ruff format .`
- 类型检查：`uv run python -m pyright`
- 入口脚本：`certificate-management = src.main:main` / `certificate-mcp = src.mcp.server:main` / `certificate-mcp-web = src.mcp.web:main`

## AI 证书识别（本地）
- **入口**：荣誉录入页顶部“AI 识别证书”（`src/ui/pages/entry_page.py`）
- **配置**：设置页 → AI 证书识别（`ai_enabled` / `ai_active_provider_id`；提供商与 Key 存在 `ai_providers` 表）
- **支持文件**：`.pdf` `.png` `.jpg` `.jpeg` `.webp`
- **PDF 处理**：OpenAI 官方 `api.openai.com` 走 `responses`（PDF 直接上传）；兼容服务走 `/v1/chat/completions`（按 `pdf_pages` 渲染前 N 页图片）
- **Key 轮换**：每次请求轮换（识别/测试/刷新模型都会消耗一次）；当前不做“失败自动重试下一个 Key”
- **相关代码**：`src/services/ai_certificate_service.py`、`src/services/ai_provider_service.py`、`src/ui/pages/settings_page.py`

## MCP 接入（本地）
- **stdio（推荐）**：由 MCP 客户端拉起本地进程：`uv run certificate-mcp`
- **SSE（本地 URL）**：`http://127.0.0.1:8000/sse`
  - 推荐启动方式：应用设置页 → MCP 服务 → 开启“随软件启动 MCP”
  - 手动启动：设置 `CERT_MCP_TRANSPORT=sse` 后运行 `uv run certificate-mcp`
- **仅允许本地绑定**：当 transport 不是 `stdio` 时，`CERT_MCP_HOST` 只能是 `127.0.0.1/localhost/::1`
- **Web 控制台（可选）**：安装 `mcp-web` 依赖后 `uv run certificate-mcp-web`（默认 `127.0.0.1:7860`，用户名/密码来自设置页）
- **默认只读 + 脱敏**：写入开关与 PII 脱敏开关均可在设置页配置（仅本地使用，避免对外暴露端口）
- **日志位置**：`logs/mcp_sse.log`、`logs/mcp_web.log`、`logs/mcp_web_install.log`
- **主要设置键（settings 表）**：`mcp_auto_start`、`mcp_port`、`mcp_allow_write`、`mcp_redact_pii`、`mcp_max_bytes`、`mcp_web_auto_start`、`mcp_web_host`、`mcp_web_port`、`mcp_web_username`、`mcp_web_token`（密码）
- **Web 环境变量**：Web 进程实际读取 `CERT_MCP_WEB_USERNAME` / `CERT_MCP_WEB_PASSWORD`（由运行时把 `mcp_web_token` 注入为 password）

## 目录速览
- `src/main.py` 应用入口；`app_context.py` 构建 DI 容器与服务；`logger.py` 日志配置；`config.py` 配置加载；`version.py` 版本号管理。
- MCP：`src/mcp/server.py`（MCP 服务端，stdio/SSE）、`src/mcp/web.py`（本地 Web 控制台，可选）、`src/mcp/runtime.py`（MCP 进程管理与自启动）、`src/mcp/helpers.py`（配置解析辅助）。
- AI：`src/services/ai_certificate_service.py`（证书识别）、`src/services/ai_provider_service.py`（多 Provider / Key 轮换）
- 数据层 `src/data/`: `models.py`（Base + Award/TeamMember/Attachment/Setting/BackupRecord/ImportJob/Major/School/SchoolMajorMapping/AwardMember）；`database.py` 提供 `session_scope`。
- 服务层 `src/services/`: award_service、statistics_service、import_export、backup_manager、attachment_manager、flag_service、settings_service、major_service 等。
- 表现层 `src/ui/`: `main_window.py`（窗口与导航，懒加载页面，窗口居中），`styled_theme.py`（ThemeManager），`theme.py`（通用 UI 工具），`widgets/major_search.py`，`pages/`（home、dashboard、overview、entry、management、recycle、settings、about、base_page）。
- 资源 `src/resources/`: `styles/styled_light.qss`、`styles/styled_dark.qss`，`templates/awards_template.csv`。
- 数据/文档 `docs/`: `china_bachelor_majors_2025.csv`（本科专业目录约 840 条）、`china_universities_2025.csv`、`GSAU_majors.xlsx` 示例映射、`personal_info_template.doc`。

## 模型与数据
- Base：统一主键、自增、时间戳。
- Award：competition_name、award_date、level、rank、certificate_code、remarks、attachment_folder、deleted/deleted_at；关系 award_members（`AwardMember` 快照，级联删除）与 attachments（级联删除）。
- AwardMember：荣誉成员快照（award_id、member_id 可空、member_name 必填、sort_order），成员库变更不影响历史荣誉显示。
- TeamMember：姓名、性别、身份证（唯一）、手机号、学号（唯一）、邮箱、学校/学校代码、专业/专业代码、班级、学院、pinyin、active、sort_index；关系 award_associations（通过 `AwardMember` 关联荣誉）。
- Attachment：award_id、stored_name、original_name、relative_path（唯一）、file_md5、file_size、deleted 标记。
- Setting/BackupRecord/ImportJob：应用设置、备份记录、导入任务。
- AIProvider：多 AI 提供商（API 地址/模型/PDF 页数/多 Key 轮换索引）。
- CustomFlag/AwardFlagValue：自定义布尔开关定义与荣誉对应值（用于录入/导出/筛选）。
- Major：name/code 唯一，含学科/专业类信息与 pinyin；School、SchoolMajorMapping 存储学校与学校-专业-学院映射。
- 专业与学校数据源：`docs/china_bachelor_majors_2025.csv`（约 840 条）+ `china_universities_2025.csv`；搜索支持中文/拼音/代码，学校代码缺失时回退学校名称匹配学院。

## 主要特性（按页面）
- **MainWindow**：`_center_window()` 居中；快速加载首页，余下页面 100ms 后异步载入；route_keys 管理导航；主题变化事件转发。
- **Dashboard**：8 个梯度指标卡 + 饼/柱图 + 最近荣誉表（只读）。颜色：总紫、国家蓝、省金、校绿、一等青、二等紫粉、三等红、优秀蓝。
- **Entry**：动态成员卡两列布局；字段覆盖姓名/性别/身份证/手机号/学号/邮箱/学校/学校代码/专业/专业代码/班级/学院；集成 MajorSearchWidget（中文/拼音/代码自动完成，最多 8 条）。
- **Overview**：列表卡；FTS5 全文搜索（比赛名/证书号/成员），筛选（级别/奖项/日期范围）、8 种排序（日期/级别/奖项/名称正反），500ms 防抖；分页与重置；编辑对话框可增删成员，保存后通过父链刷新管理页。
- **Management**：成员列表与详情；核心字段含学校/学院/专业代码，支持自动刷新。
- **Recycle**：回收站（已删除荣誉记录）与恢复/彻底删除。
- **Settings**：主题、自动备份频率、日志级别、数据目录；备份列表验证/恢复前可自动备份；索引重建按钮；导入/导出日志面板；清理工具卡片（日志/备份/数据库/一键清空，均双重确认）。
- **About**：版本/特性/技术栈/链接。

## 主题与 UI 约定
- ThemeManager（`styled_theme.py`）提供 `is_dark`、`themeChanged`、`get_window_stylesheet()`、`apply_theme_color()`。
- 有动态子组件的页面/对话框：在 `__init__` 早期连接 `themeChanged`（@Slot），调用 `_apply_theme()` 并用 `findChildren()` 更新所有输入组件样式；静态部分由 QSS 负责。
- 组件卡片多带阴影（blur 28，offset 0,8）；动画场景下可能卡顿，性能优化可考虑减弱阴影或启用 OpenGL。

## 代码风格
- Ruff 配置：行宽 120、缩进 4、目标 py314、双引号；已豁免 Qt 命名/复杂度规则。运行 `uv run ruff check .` / `uv run ruff format .`。
- Pyright 配置：standard 模式类型检查；与 ruff 分工——ruff 负责代码风格和 unused import/variable，pyright 负责类型检查。运行 `uv run pyright`。
- 采用现代类型标注（`list[str]`, `| None`），无需强制 `__future__`；尽量添加 docstring。
- 使用 loguru 日志，避免 `print`。
- 保持导入有序、移除未用依赖；少量必要注释，遵循现有风格。

## 开发/修改提示
- 访问服务总用 `AppContext`（`ctx.awards/statistics/settings/members/attachments/backup/importer/ai/ai_providers/flags/majors/schools`），数据库操作包裹 `session_scope`，勿手写裸会话。
- 添加页面：继承 `BasePage`，实现 `_init_ui`；在 `main_window.py` 注册（导航项、_load_* 分组、route_keys），按需处理主题信号。
- 添加数据字段：同步更新模型、对应 service、UI 表单/列表、统计或刷新逻辑（管理页的 10 字段监控需保持一致）。
- 成员字段在 UI 约定为 10 项（含学校）；管理页刷新依赖该集合。
- 导入/导出：模板位于 `src/resources/templates/`（CSV 版本在仓库内；XLSX 模板会在运行时自动生成并可从设置页下载）；专业与学校/学院映射导入来自 `docs/china_bachelor_majors_2025.csv`、`china_universities_2025.csv`、`GSAU_majors.xlsx`。
- 导入荣誉：支持 CSV/XLSX，带预检（dry-run 不写入数据库/不落盘附件）、进度 ETA；正式导入会写入 imports 表并可导出错误行；若启用自定义开关，会按列名 `label (key)` 或 `label` 解析。
- 附件保存：按奖项目录 `attachments/award_{id}` 存放；去重仅在同一奖项内按 MD5/size 判断；删除会移入 `attachments/.trash` 并在数据库标记 deleted。
- 备份：基于 SQLite `backup()` 生成快照，打包为 zip（可选包含附件/日志）；恢复会覆盖数据库并按选项恢复附件/日志。
- 数据库 reset：`Database.reset()` 通过 DROP 所有对象后重建空库（避免 Windows 删除文件失败），设置页有入口且带双重确认。
- 学院自动填充依赖 `SchoolMajorMapping`，如导入数据缺少学校代码会自动用学校名称回退匹配；若要禁用回退需同步保证 school_code 完整。
- 运行/调试前确认运行目录为仓库根目录；避免提交 `data/`、`attachments/`、`backups/`、`logs/`、`temp/` 生成物。
