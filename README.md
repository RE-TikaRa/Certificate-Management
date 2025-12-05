# 荣誉证书管理系统

![Python](https://img.shields.io/badge/Python-3.14+-blue)
![PySide6](https://img.shields.io/badge/PySide6-latest-green)
![License](https://img.shields.io/badge/License-MIT-orange)

一款功能完整、界面精美的荣誉证书管理桌面应用。基于 **PySide6** + **qfluentwidgets** 框架开发，采用现代化 Fluent Design 设计风格。支持荣誉证书的全生命周期管理：从录入、统计分析、成员管理到附件管理，一应俱全。

[查看Demo](#快速开始) · [报告Bug](https://github.com/RE-TikaRa/Certificate-Management/issues) · [提出新特性](https://github.com/RE-TikaRa/Certificate-Management/issues)

---

## ✨ 核心功能

### 📊 仪表盘与数据统计
- **实时指标卡片**：8 个关键指标卡片，采用彩色梯度设计
  - 综合统计：总荣誉数、国家级、省级、校级
  - 等级统计：一等奖、二等奖、三等奖、优秀奖
- **可视化分析**：
  - 饼图：荣誉级别分布
  - 柱状图：奖项等级分布
  - 汇总表：按级别和等级的数量统计
- **最近录入**：展示最新 10 条荣誉记录，快速查看最新数据

### 📝 荣誉录入与编辑
- **完整信息录入**：
  - 基本信息：比赛名称、获奖日期
  - 赛事级别：国家级、省级、校级
  - 奖项等级：一等奖、二等奖、三等奖、优秀奖
  - 其他信息：证书编号、备注说明
- **成员管理**：支持添加多名参与成员，实时编辑和删除
  - 基本信息：姓名、性别
  - 身份信息：身份证号
  - 联系方式：手机号、邮箱
  - 学生信息：学号、专业、班级、学院
- **专业智能搜索**：
  - 66个专业数据库，支持中文和拼音模糊搜索
  - 下拉列表自动完成，最多显示8个结果
  - 点击选择即可自动填充
  - 支持从 Excel 导入专业列表
- **动态卡片界面**：成员以卡片形式展示，支持二列布局，响应式设计

### 🎯 荣誉总览与快速编辑
- **完整荣誉列表**:展示所有荣誉及其关键信息
- **强大筛选功能**:
  - 等级筛选:国家级/省级/校级
  - 奖项筛选:一等奖/二等奖/三等奖/优秀奖
  - 日期范围:自定义开始和结束日期
  - 关键词搜索:搜索竞赛名称或证书编号
- **灵活排序**:8种排序方式
  - 日期排序:升序/降序
  - 等级排序:升序/降序
  - 奖项排序:升序/降序
  - 名称排序:A-Z/Z-A
- **对话框编辑**:在专用编辑窗口中修改荣誉信息
- **成员在线编辑**:直接在对话框中添加、修改或删除成员
- **快速删除**:确认后删除荣誉记录及所有关联数据

### 👥 成员管理与历史追踪
- **成员列表视图**：显示所有成员及其详细信息
- **参与荣誉查看**：每个成员对应的所有荣誉记录
- **信息编辑**：支持修改成员的各类信息
- **完整字段支持**：9 个信息字段（姓名、性别、身份证号、手机号、学号、邮箱、专业、班级、学院）
- **自动数据刷新**：修改成员信息后自动更新所有关联视图

### 📁 附件管理与回收站
- **灵活的附件上传**：为每条荣誉记录上传相关证明文件
- **回收站管理**：删除的附件可恢复或彻底删除
- **快速访问**：直接打开附件所在文件夹，方便查看和整理

### 💾 数据管理与备份
- **自动备份机制**：支持设置自动备份频率，保障数据安全
- **批量导入导出**：支持 CSV 格式的数据导入和导出
- **本地数据库**：SQLite 数据库，数据完全本地化存储
- **事务支持**：基于 SQLAlchemy ORM，支持事务回滚

### ⚙️ 系统设置
- **主题切换**：支持浅色和深色两种主题，自动适配系统设置
  - 实时主题切换：无需重启，所有页面立即响应
  - 动态样式更新：包括滚动区域、卡片、输入框等所有组件
- **日志管理**：可配置的日志记录策略，便于问题追踪
- **数据目录设置**：灵活设置数据存储位置
- **备份频率配置**：自定义自动备份时间间隔

### 📜 关于页面
- **系统信息**：展示应用名称、版本号、开发者信息
- **功能特性**：展示核心功能列表和技术栈
- **项目链接**：GitHub 仓库、问题反馈链接
- **版权声明**：许可证和版权信息

---

## 🚀 快速开始

### 系统要求
- **操作系统**：Windows / macOS / Linux
- **Python 版本**：3.14 或更高版本
- **内存**：建议 4GB 以上
- **磁盘**：至少 200MB 可用空间

### 安装步骤

1. **克隆仓库**
```bash
git clone https://github.com/RE-TikaRa/Certificate-Management.git
cd Certificate-Management
```

2. **安装依赖**
```bash
# 若未安装 uv（可选）
# pip install uv

# 创建/同步虚拟环境（默认包含 dev 依赖与 Ruff）
uv sync

# 仅安装运行时依赖（不含 dev）
# uv sync --no-dev
```

3. **运行应用**

Windows 系统（推荐）：
```bash
main.bat
```

或使用 Python 命令：
```bash
python -m src.main
# 或使用 uv 运行（使用 uv 创建的虚拟环境）
uv run python -m src.main
```

调试模式（输出详细日志）：
```bash
python -m src.main --debug
```

---

## 📂 文件目录说明

```
Certificate-Management/
├── README.md                    # 本文件
├── pyproject.toml               # 依赖与构建配置
├── uv.lock                      # uv 生成的锁定文件
├── main.bat                     # Windows 启动脚本
├── .gitignore                   # Git 忽略规则
│
├── src/                         # 源代码目录
│   ├── __init__.py
│   ├── main.py                  # 应用入口
│   ├── app_context.py           # 应用上下文，初始化和引导
│   ├── config.py                # 配置管理
│   ├── logger.py                # 日志系统配置
│   │
│   ├── data/                    # 数据层（ORM 模型和数据库操作）
│   │   ├── __init__.py
│   │   ├── models.py            # SQLAlchemy 数据模型
│   │   ├── database.py          # 数据库连接和会话管理
│   │   └── __pycache__/
│   │
│   ├── services/                # 业务层（业务逻辑和数据服务）
│   │   ├── __init__.py
│   │   ├── award_service.py     # 荣誉相关服务
│   │   ├── statistics_service.py # 统计分析服务
│   │   ├── import_export.py     # 数据导入导出服务
│   │   ├── backup_manager.py    # 备份管理服务
│   │   ├── attachment_manager.py # 附件管理服务
│   │   ├── settings_service.py  # 设置管理服务
│   │   ├── major_service.py     # 专业搜索服务
│   │   └── __pycache__/
│   │
│   ├── ui/                      # 表现层（用户界面）
│   │   ├── __init__.py
│   │   ├── main_window.py       # 主窗口框架
│   │   ├── theme.py             # UI 主题工具函数
│   │   ├── styled_theme.py      # 主题管理和样式应用
│   │   ├── __pycache__/
│   │   │
│   │   ├── widgets/             # 自定义组件
│   │   │   └── major_search.py  # 专业搜索组件
│   │   │
│   │   └── pages/               # 页面模块
│   │       ├── __init__.py
│   │       ├── base_page.py     # 页面基类
│   │       ├── home_page.py     # 首页
│   │       ├── dashboard_page.py # 仪表盘页面
│   │       ├── entry_page.py    # 荣誉录入页面
│   │       ├── overview_page.py # 荣誉总览页面
│   │       ├── management_page.py # 成员管理页面
│   │       ├── recycle_page.py  # 附件回收站页面
│   │       ├── about_page.py    # 关于页面
│   │       ├── settings_page.py # 系统设置页面
│   │       └── __pycache__/
│   │
│   └── resources/               # 资源文件
│       ├── styles/              # QSS 样式文件
│       │   ├── styled_light.qss  # 浅色主题样式
│       │   └── styled_dark.qss   # 深色主题样式
│       └── templates/           # 数据导入模板
│           └── awards_template.csv
│
├── tools/                       # 工具脚本
│   ├── import_majors.py         # 专业数据导入脚本
│   └── index.xlsx               # 专业列表模板
│
├── data/                        # 本地数据存储（由应用自动创建）
│   └── awards.db                # SQLite 数据库文件
│
├── attachments/                 # 附件存储目录
├── backups/                     # 自动备份目录
├── logs/                        # 应用日志目录
├── docs/                        # 文档目录
│   └── system_design.md         # 系统设计文档
└── temp/                        # 临时文件目录
```

---

## 🏗️ 项目架构

本项目采用经典的 **分层架构模式**：

```
┌─────────────────────────────────────┐
│       表现层（Presentation）         │
│  PySide6 + QFluentWidgets           │
│  (UI Pages, Windows, Dialogs)       │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│       业务层（Business Logic）       │
│  Services                           │
│  (Award, Statistics, Backup, etc)   │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│       数据层（Data Access）          │
│  SQLAlchemy ORM + SQLite            │
│  (Models, Database Operations)      │
└─────────────────────────────────────┘
```

### 核心特性

- **ORM 数据访问**：使用 SQLAlchemy 实现数据模型和数据库操作，代码整洁
- **事务管理**：采用 session_scope() 会话管理，支持事务回滚
- **主题系统**：通过 QSS (Qt StyleSheet) 实现深色和浅色主题动态切换
- **响应式设计**：页面自适应布局，支持不同窗口大小
- **异步加载**：后台加载页面，避免启动时界面卡顿
- **数据验证**：每个操作都有数据完整性检查

---

## 🗄️ 数据模型

### Award（荣誉记录）
| 字段 | 类型 | 说明 |
|-----|-----|------|
| `id` | Integer | 主键，自增 |
| `competition_name` | String | 比赛名称 |
| `award_date` | Date | 获奖日期 |
| `level` | String | 赛事级别（国家级/省级/校级） |
| `rank` | String | 奖项等级（一等奖/二等奖/三等奖/优秀奖） |
| `certificate_code` | String | 证书编号 |
| `remarks` | Text | 备注说明 |
| `members` | Relationship | 参与成员（多对多关系） |
| `tags` | Relationship | 标签分类（多对多关系） |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |

### TeamMember（参与成员）
| 字段 | 类型 | 说明 |
|-----|-----|------|
| `id` | Integer | 主键，自增 |
| `name` | String | 姓名 |
| `gender` | String | 性别 |
| `id_card` | String | 身份证号 |
| `phone` | String | 手机号 |
| `student_id` | String | 学号 |
| `email` | String | 邮箱地址 |
| `major` | String | 专业 |
| `class_name` | String | 班级 |
| `college` | String | 学院 |
| `awards` | Relationship | 参与的荣誉（多对多关系） |

### Major（专业信息）
| 字段 | 类型 | 说明 |
|-----|-----|------|
| `id` | Integer | 主键，自增 |
| `name` | String | 专业名称（唯一） |
| `pinyin` | String | 拼音（用于搜索） |
| `category` | String | 专业分类 |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |

---

## 🎨 主题系统

应用支持 **浅色和深色两种主题**，自动适配系统设置。主题样式通过 QSS（Qt StyleSheet）定义。

### 指标卡片色彩方案

| 指标 | 颜色方案 | 使用场景 |
|-----|--------|--------|
| 总荣誉数 | 紫色 (#a071ff → #7b6cff) | 总体统计 |
| 国家级 | 蓝色 (#5a80f3 → #4ac6ff) | 国家级荣誉 |
| 省级 | 金色 (#ffb347 → #ffcc33) | 省级荣誉 |
| 校级 | 绿色 (#3ec8a0 → #45dd8e) | 校级荣誉 |
| 一等奖 | 青色 (#00b4d8 → #48cae4) | 一等奖 |
| 二等奖 | 紫粉色 (#b54cb8 → #d896ff) | 二等奖 |
| 三等奖 | 红色 (#ff6b6b → #ff8787) | 三等奖 |
| 优秀奖 | 蓝色 (#5a80f3 → #4ac6ff) | 优秀奖 |

主题切换通过设置页面完成，用户偏好自动保存。

---

## 🔧 开发指南

### 添加新功能的步骤

1. **定义数据模型**（`src/data/models.py`）
   - 继承 Base 类
   - 定义数据库字段和关系

2. **编写服务逻辑**（`src/services/`）
   - 创建 Service 类处理业务逻辑
   - 实现 CRUD 操作

3. **创建 UI 页面**（`src/ui/pages/`）
   - 继承 BasePage 基类
   - 实现页面布局和交互

4. **在主窗口注册**（`src/ui/main_window.py`）
   - 在导航栏添加新页面
   - 配置路由和图标

### 代码规范

- 使用 PEP 8 编码规范
- 为所有函数添加文档字符串
- 使用类型提示（Type Hints）
- 日志记录使用 logger，避免 print()

### 运行测试与验证

使用 Ruff 进行检查与格式化：
```bash
uv run ruff check .
uv run ruff format .
```

---

## 📦 依赖列表

主要依赖通过 `pyproject.toml` 管理，安装时会自动获取最新的兼容版本：

| 包名 | 说明 |
|------|------|
| PySide6 | Qt 6 Python 绑定，GUI 框架 |
| PySide6-Fluent-Widgets | Fluent Design 风格组件库 |
| SQLAlchemy | ORM 框架，数据库抽象 |
| pandas | 数据处理和分析 |
| openpyxl | Excel 文件读写 |
| APScheduler | 定时任务调度 |
| loguru | 日志记录库 |
| alembic | 数据库迁移工具 |
| python-dateutil | 日期时间处理 |
| pypinyin | 拼音转换工具，用于专业搜索 |

完整依赖与版本策略请见 `pyproject.toml`，精确解析版本记录在 `uv.lock`（如需保持一致可运行 `uv sync --locked`）。

---

## 🛡️ 数据安全与隐私

- ✅ **本地存储**：所有数据存储在本地 SQLite 数据库中，不上传到云端
- ✅ **自动备份**：支持定期自动备份，防止数据丢失
- ✅ **文件隐私**：敏感数据文件（数据库、备份等）配置在 `.gitignore` 中
- ✅ **回收站**：删除操作可在回收站中恢复

### .gitignore 配置

```
# 数据库和备份
*.db
*.sqlite
*.sqlite3
data/awards.db
backups/

# Python 缓存
__pycache__/
*.pyc
*.pyo
build/
dist/

# 应用数据
attachments/
logs/
temp/

# IDE 编辑器
.vscode/
.idea/
*.swp
*.swo

# 环境变量
.env
secrets.json
```

---

## 📝 使用示例

### 场景：学校管理学生荣誉

1. **录入新荣誉**
   - 点击"录入"页面
   - 填写比赛名称、日期、级别、等级
   - 添加参与成员信息
   - 点击保存

2. **查看统计分析**
   - 进入"仪表盘"
   - 查看各类荣誉数量和分布
   - 观察最近录入的荣誉

3. **管理成员信息**
   - 进入"成员管理"
   - 搜索或浏览成员
   - 编辑成员信息（如身份证号变更）
   - 查看成员参与的所有荣誉

4. **备份和导出**
   - 进入"系统设置"
   - 配置自动备份频率
   - 导出数据为 CSV 格式

---

## 🎯 后续计划

- [x] 专业智能搜索功能
- [x] 荣誉筛选和排序
- [x] 关于页面
- [ ] 数据加密存储
- [ ] 网络备份功能
- [ ] 报表生成和打印
- [ ] 用户权限管理
- [ ] 数据同步功能

---

## 🤝 如何贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

---

## 📝 版本控制

该项目使用 Git 进行版本管理。

当前版本：1.0.0（2025年12月）

查看 [Releases](https://github.com/RE-TikaRa/Certificate-Management/releases) 了解更新历史。

---

## 📄 许可证

本项目签署了 MIT 授权许可。详见 [LICENSE](https://github.com/RE-TikaRa/Certificate-Management/blob/main/LICENSE) 文件。

---

## 👨‍💻 作者

**RE-TikaRa**

- GitHub: [@RE-TikaRa](https://github.com/RE-TikaRa)
- Email: [联系方式]

---

## 🙏 致谢

感谢以下项目和工具的支持：

- [PySide6](https://wiki.qt.io/PySide6) - Qt for Python
- [QFluentWidgets](https://github.com/zhiyiYo/QFluentWidgets) - 优雅的 Fluent Design 组件库
- [SQLAlchemy](https://www.sqlalchemy.org/) - Python ORM 框架
- [Loguru](https://github.com/Delgan/loguru) - 简洁的日志库
- [GitHub](https://github.com) - 版本管理平台

---

## 📞 反馈与支持

如有问题或建议，欢迎通过以下方式联系：

- 提交 [Issue](https://github.com/RE-TikaRa/Certificate-Management/issues)
- 发起 [Discussion](https://github.com/RE-TikaRa/Certificate-Management/discussions)
- 发送邮件联系

---

<div align="center">

**⭐ 如果本项目对你有帮助，请给个 Star 吧！**

</div>
