# 证书管理程序系统设计

## 1. 项目概览
- **目标**：提供一套集荣誉证书录入、查询、统计、备份于一体的桌面应用，确保数据及附件集中管理，降低人工整理成本。
- **运行环境**：Windows 11（优先）、Python 3.13.3、PySide6 GUI。
- **入口**：`main.py`（可通过 `python main.py` 或批处理脚本 `main.bat` 启动）。
- **核心能力**：荣誉数据 CRUD、成员/标签管理、统计分析、附件归档、自动/手动备份、导入导出、自定义设置、日志追踪。

## 2. 技术栈与总体结构
| 层级 | 主要技术 | 说明 |
| --- | --- | --- |
| UI 层 | PySide6 Widgets、Qt Charts | 使用堆栈式页面容器切换 Home/Dashboard/Entry/Statistics/Management/Settings。|
| 应用层 | 自定义控制器、服务类 | `AttachmentManager`、`BackupManager`、`ImportExportService` 等负责协调 UI 与数据。|
| 数据层 | SQLite (`data/awards.db`)、`sqlite3`/`SQLAlchemy` | 统一的数据访问和迁移；提供 DAO/Repository。|
| 系统服务 | `logging`、计划任务 | 记录日志、定时备份、配置初始化。|

组件划分：
1. `AppContext`：加载设置、初始化数据库连接、注册服务，注入到各页面。
2. `NavigationController`：管理侧边栏/顶部快捷入口，协调页面切换。
3. 页面模块：`HomePage`, `DashboardPage`（含统计分析）、`EntryPage`, `ManagementPage`, `SettingsPanel`。
4. 服务模块：`AttachmentManager`, `BackupManager`, `ImportExportService`, `SettingsService`, `AuditLogger`。

## 3. UI 信息架构
- **HomePage**：仪表卡片（总荣誉、国家级、省级、一等奖等）、最近录入表格（双击打开附件目录）、快捷按钮（录入/统计/成员/备份）。
- **DashboardPage**：以卡片+图表形式呈现关键指标、最近记录、按级别/等级分布等综合统计，双击最近列表可打开附件目录。
- **EntryPage**：
  - 表单字段：比赛名称、获奖日期、赛事级别、奖项等级、证书编号、备注，并含输入校验（必填、日期范围、去重提醒）。
  - 成员/标签列表：复选、批量选择/导入（弹窗勾选已有项）与即时新增。
  - 附件上传：多文件选择，复制到附件根目录 `attachments/<award-id>/`，命名“比赛名-附件NN”，并提供清空表单、一键重置。
- **ManagementPage**：左右双列表维护成员、标签；支持新增、删除、重命名、排序（名称 A-Z/Z-A、拼音、手动拖拽），搜索过滤，批量导入/导出。
- **SettingsPanel**：配置附件根目录、备份目录、自动备份频率（手动/启动/每日/每周）、是否包含附件、是否包含日志；提供“保存设置”“立即备份”“打开附件目录”“打开备份目录”。
- 备份策略默认保留近 5 次记录，可通过 `backup_retention` 设置调整。
- **附件回收站视图**：展示被标记删除的附件，可恢复或彻底删除。

### 3.1 视觉与主题策略
- **框架选择**：整体 UI 采用 Qt Quick / QML 搭配 Fluent Design 视觉（可基于 qfluentwidgets 2.x 或 Qt Quick Controls 2 Fluent 风格），确保现代动画与统一主题；统计图可嵌 Qt Charts 或 ECharts for Qt。
- **主题管理**：SettingsPanel 提供主题颜色与明暗模式切换，通过 qfluentwidgets `ThemeColor` / `setTheme` 或 QML `QtQuick.Controls.Material` API 实现；同时支持自定义品牌色。
- **控件风格**：主页 KPI 卡片、快捷按钮使用 Fluent 卡片样式（玻璃质感 + 阴影 + 渐层背景），导航栏使用 Fluent NavigationView，列表/表格统一采用 Fluent 表格与 InfoBar 提示。
- **动画与动效**：页面切换、数据刷新、导入/上传等关键操作配合 `QPropertyAnimation` 或 QML 动画曲线，遵循 Fluent Motion（加速-减速）规范；附件上传进度与备份状态提供视觉反馈。
- **资源统一**：字体使用 Segoe UI Variable，图标统一采用 Fluent System Icons (SVG)；配合 icon font 生成工具包保障 DPI/缩放一致性。

## 4. 数据流程概述
1. 用户在 EntryPage 录入 → 表单校验 → 写入 `awards`、关联表 → `AttachmentManager` 复制附件，记录到 `attachments` 表。
2. Home/Dashboard/Statistics 订阅数据库变更，刷新统计指标与图表。
3. 管理页的成员/标签更新后，重新填充 EntryPage 勾选列表。
4. SettingsPanel 更新配置 → `SettingsService` 写回 `settings` 表并通知 `AttachmentManager`、`BackupManager` 迁移目录或调整计划任务。
5. `BackupManager` 根据频率触发备份；成功后记录时间，HomePage 快捷按钮可显示最近一次备份状态。

## 5. 数据库设计
数据库文件：`data/awards.db`。建议使用迁移脚本（例如 `alembic`）管理结构变更。

### 5.1 表结构
| 表 | 主要字段 | 说明 |
| --- | --- | --- |
| `awards` | `id` PK, `competition_name`, `award_date`, `level`, `rank`, `certificate_code`, `remarks`, `attachment_folder`, `created_at`, `updated_at` | `attachment_folder` 为相对路径，例如 `2025/国家赛/award_12`。|
| `team_members` | `id`, `name`, `pinyin`, `active` | `pinyin` 便于排序。|
| `tags` | `id`, `name`, `pinyin`, `active` | 同上。|
| `award_members` | `award_id`, `member_id` | 多对多关联。|
| `award_tags` | `award_id`, `tag_id` | 多对多关联。|
| `attachments` | `id`, `award_id`, `stored_name`, `original_name`, `relative_path`, `deleted`, `deleted_at` | `deleted=1` 表示已移入回收站。|
| `settings` | `key`, `value`, `updated_at` | 采用 key-value，常用键：`attachment_root`, `backup_root`, `backup_frequency`, `include_attachments`, `include_logs`, `auto_backup_mode`。|
| `imports` (可选) | `id`, `filename`, `status`, `created_at` | 记录导入任务结果。|
| `backups` | `id`, `path`, `include_attachments`, `include_logs`, `created_at`, `status`, `message` | 追踪备份历史。|

### 5.2 索引与约束
- `awards` 对 `award_date`、`level`、`rank` 建索引以加速统计。
- `team_members`、`tags` 对 `name` 建唯一索引。
- `attachments.relative_path` 唯一，保证文件定位。
- `settings.key` 唯一，方便 UPSERT。

## 6. 附件与回收策略
- 附件统一存放于 `attachments/` 根目录，每个荣誉一个子目录，可按年份/事件细分。
- 上传流程：
  1. 生成安全文件名（移除非法字符，限制长度）。
  2. 以 `比赛名-附件01.ext` 保存，并将相对路径写入 `attachments` 表。
- 删除流程：
  - UI 操作 → 记录 `deleted=1` + `deleted_at`，物理文件移动到 `attachments/.trash/<award-id>/`。
  - 回收站页面列出软删除附件，可执行“恢复”（移回原目录，`deleted=0`）或“彻底删除”（从磁盘移除并删除记录）。
- 附件根目录变更：`AttachmentManager` 扫描旧目录，按 `attachment_folder` 迁移至新根，更新设置。

## 7. 备份策略
- 备份内容：`data/awards.db`、`attachments/`（包含回收站）、`logs/`、导入模板、导出结果等所有用户资源。
- 命名：`<prefix>-backup-YYYYMMDD-HHMM`，`prefix` 在设置中配置（默认 `awards`）。
- 频率：
  - 手动：Home 快捷按钮或 SettingsPanel 中的“立即备份”。
  - 启动时：应用启动后检查距上次备份是否超过阈值（如 24 小时），若是则自动备份。
  - 每日/每周：注册定时任务，在设定时间执行。
- 执行步骤：
  1. 创建临时目录，使用 SQLite backup API 复制数据库。
  2. 视设置复制附件与日志。
  3. 打包为 zip 写入备份目录。
  4. 更新 `backups` 表记录状态并在 UI 中提示最近备份时间。

## 8. 导入与导出
### 模板
- 提供 `templates/awards_template.xlsx` 与 `templates/awards_template.csv`，列包括：比赛名称、获奖日期（YYYY-MM-DD）、赛事级别、奖项等级、证书编号、备注、成员（逗号分隔）、标签（逗号分隔）、附件路径（分号分隔）。

### 导入
1. 用户下载模板填写 → 通过导入向导上传。
2. `ImportExportService` 校验必填字段、日期格式、成员/标签存在性，必要时创建新成员/标签。
3. 附件列若提供本地路径，执行复制并记录日志；失败记录输出至导入结果。
4. 完成后生成结果摘要（总数/成功/失败）并存档至 `imports` 表。

### 导出
- 根据筛选条件导出到 CSV/XLSX，命名 `export-YYYYMMDD-HHMM.ext`。
- 可选附带附件压缩包。
- 导出概览附带统计摘要（总数、按级别/等级分布）。

### 排序
- 名称（A→Z / Z→A）
- 名称拼音（A→Z / Z→A，借助 `pypinyin` 存储 `pinyin` 字段）
- 自定义手动顺序（拖拽后写入 `sort_index`）

## 9. 日志体系
- 目录：`logs/`。
- 记录器：
  - `app`：INFO 级别，`logs/app.log`，`RotatingFileHandler`（单文件 5 MB、保留 10 个）。
  - `error`：ERROR 级别，`logs/error.log`，捕获异常。
  - `debug`（可选）：DEBUG 级别，需要在设置中启用，`logs/debug.log`。
- 清理策略：
  - 启动时检查日志总大小（默认上限 200 MB），超出则删除最旧文件。
  - SettingsPanel 提供“清理日志”按钮，调用 `AuditLogger.clean()`。
- UI：设置页提供“查看日志”与“导出日志”操作，可直接打开日志目录或打包下载。

## 10. 设置管理
- `settings` 表采用 key-value 结构，`SettingsService` 暴露 `get/set/bulk_update`。
- 默认值：附件目录 `attachments/`，备份目录 `backups/`，频率 `manual`，包含附件/日志默认为 true。
- 保存流程：表单校验（目录存在/可写、频率合法）→ UPSERT → 通知相关服务。
- 设置变更会触发 `AttachmentManager` 迁移目录、`BackupManager` 重建计划任务。

## 11. 自动备份与计时任务
- 使用 `QTimer`（轻量）或 `APScheduler`（复杂计划）执行：
  - `on_startup_backup`：频率=启动时且超过阈值则执行。
  - `daily_backup`：每日固定时间。
  - `weekly_backup`：指定星期几及时间。
- 执行期间禁用“立即备份”按钮并显示进度，完成后写入日志与 UI 状态。

## 12. 开发与测试建议
- 依赖：`PySide6`, `SQLAlchemy`, `alembic`, `pandas`, `openpyxl`, `pypinyin`, `apscheduler`, `pytest`, `pytest-qt`。
- 推荐目录：
```
src/
  main.py
  app_context.py
  ui/
    main_window.py
    pages/
  services/
    attachment_manager.py
    backup_manager.py
    import_export.py
    settings_service.py
  data/
    models.py
    repositories.py
    migrations/
```
- 测试：\`pytest\` 覆盖服务层；\`pytest-qt\` 覆盖关键 UI；导入/导出与附件迁移提供集成测试。
- 打包：可使用 `PyInstaller`/`cx_Freeze` 生成分发包，结合 `Inno Setup` 制作安装程序。

## 13. 后续扩展
- 国际化（Qt Linguist）。
- 云端同步（REST API，同步多端数据）。
- OCR 自动解析证书图片。
- 联动 Web 仪表盘或移动端。
- 备份结果推送（邮件/微信）。
