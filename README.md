# 荣誉证书管理系统

一款功能完整的荣誉证书管理桌面应用，基于 **PySide6** + **qfluentwidgets** 框架开发。支持荣誉证书的录入、统计分析、成员管理、附件管理等功能。

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.0+-green)
![License](https://img.shields.io/badge/License-MIT-orange)

---

## ✨ 核心功能

### 📊 仪表盘与统计
- **即时指标**：8 个关键指标卡片，支持彩色显示
  - 总荣誉数、国家级、省级、校级
  - 一等奖、二等奖、三等奖、优秀奖
- **荣誉构成与趋势**：按级别和等级分布的饼图和柱状图
- **级别汇总**：国家级、省级、校级的数量统计
- **等级汇总**：各等级奖励的数量统计
- **最近录入**：显示最新 10 条荣誉记录，支持编辑和删除

### 📝 荣誉录入
- **完整信息录入**：
  - 比赛名称、获奖日期
  - 赛事级别（国家级、省级、校级）
  - 奖项等级（一等奖、二等奖、三等奖、优秀奖）
  - 等级、排名、证书编号、备注
- **成员管理**：支持添加多名参与成员，包含详细信息
  - 基本信息：姓名、性别、年龄
  - 证件信息：身份证号
  - 联系方式：电话、邮箱
  - 学生信息：学号、专业、班级、学院
- **支持编辑和删除**：可直接从仪表盘编辑已录入的荣誉

### 👥 成员管理
- **成员列表**：显示所有成员及其详细信息
- **快速查看**：展示成员参与的所有荣誉
- **详细信息**：11 个信息字段的完整展示

### 📁 附件管理
- **上传附件**：为每条荣誉记录上传相关证明文件
- **回收站**：删除的附件可在回收站中恢复或彻底删除
- **快速访问**：直接打开附件所在文件夹

### 💾 数据管理
- **自动备份**：支持设置自动备份频率
- **导入导出**：支持 CSV 格式的批量导入导出
- **数据库**：SQLite 数据库，安全可靠

### ⚙️ 系统设置
- **主题设置**：支持浅色和深色主题切换
- **日志管理**：配置日志记录策略
- **数据目录**：设置数据存储位置
- **备份设置**：配置自动备份频率

---

## 🚀 快速开始

### 系统要求
- Python 3.9 或更高版本
- Windows / macOS / Linux

### 安装依赖
```bash
pip install -r requirements.txt
```

### 运行应用
```bash
python -m src.main
```

或在 Windows 上直接双击 `main.bat` 启动。

---

## 📁 项目结构

```
Certificate Management/
├── src/                          # 源代码目录
│   ├── main.py                  # 应用入口
│   ├── app_context.py           # 应用上下文（依赖注入）
│   ├── config.py                # 配置文件
│   ├── logger.py                # 日志配置
│   ├── data/
│   │   ├── models.py            # 数据模型（Award, TeamMember）
│   │   ├── database.py          # 数据库连接
│   │   └── __init__.py
│   ├── services/
│   │   ├── award_service.py     # 荣誉管理服务
│   │   ├── statistics_service.py # 统计服务
│   │   ├── import_export.py     # 导入导出服务
│   │   ├── backup_manager.py    # 备份管理
│   │   ├── attachment_manager.py # 附件管理
│   │   └── settings_service.py  # 设置管理
│   ├── ui/
│   │   ├── main_window.py       # 主窗口
│   │   ├── theme.py             # UI 工具函数
│   │   ├── styled_theme.py      # 主题管理
│   │   └── pages/
│   │       ├── base_page.py     # 页面基类
│   │       ├── home_page.py     # 首页
│   │       ├── dashboard_page.py # 仪表盘
│   │       ├── entry_page.py    # 录入页面
│   │       ├── management_page.py # 成员管理
│   │       ├── recycle_page.py  # 回收站
│   │       └── settings_page.py # 设置页面
│   └── resources/
│       ├── templates/
│       │   └── awards_template.csv # 导入模板
│       └── styles/
│           ├── styled_light.qss  # 浅色主题
│           └── styled_dark.qss   # 深色主题
├── data/
│   └── awards.db                # SQLite 数据库（本地）
├── attachments/                 # 附件存储目录
├── backups/                     # 备份文件目录
├── logs/                        # 日志文件目录
├── docs/
│   └── system_design.md         # 系统设计文档
├── libs/
│   └── StyledWidgets/           # Unreal Engine 样式库（参考）
├── requirements.txt             # Python 依赖
├── main.bat                     # Windows 启动脚本
├── .gitignore                   # Git 忽略规则
└── README.md                    # 本文件
```

---

## 🗄️ 数据模型

### Award（荣誉）
- `id`：主键
- `competition_name`：比赛名称
- `award_date`：获奖日期
- `level`：赛事级别（国家级/省级/校级）
- `rank`：奖项等级（一等奖/二等奖/三等奖/优秀奖）
- `certificate_code`：证书编号
- `remarks`：备注
- `members`：参与成员（多对多）
- `tags`：标签分类（多对多）
- `created_at`：创建时间
- `updated_at`：更新时间

### TeamMember（成员）
- `id`：主键
- `name`：姓名
- `gender`：性别
- `age`：年龄
- `id_card`：身份证号
- `phone`：手机号
- `student_id`：学号
- `contact_phone`：联系电话
- `email`：邮箱
- `major`：专业
- `class_name`：班级
- `college`：学院
- `awards`：参与的荣誉（多对多）

---

## 🎨 主题系统

应用支持浅色和深色两种主题，自动适配系统设置。主题样式通过 QSS（Qt StyleSheet）定义：

- **浅色主题**：`src/resources/styles/styled_light.qss`
- **深色主题**：`src/resources/styles/styled_dark.qss`

### 指标卡片配色方案

8 个指标卡片采用不同颜色梯度：

| 指标 | 颜色方案 | 使用场景 |
|-----|--------|--------|
| 总数 | 紫色 (#a071ff → #7b6cff) | 总体统计 |
| 国家级 | 蓝色 (#5a80f3 → #4ac6ff) | 国家级荣誉 |
| 省级 | 金色 (#ffb347 → #ffcc33) | 省级荣誉 |
| 校级 | 绿色 (#3ec8a0 → #45dd8e) | 校级荣誉 |
| 一等奖 | 青色 (#00b4d8 → #48cae4) | 一等奖 |
| 二等奖 | 紫色 (#b54cb8 → #d896ff) | 二等奖 |
| 三等奖 | 红色 (#ff6b6b → #ff8787) | 三等奖 |
| 优秀奖 | 蓝色 (#5a80f3 → #4ac6ff) | 优秀奖 |

主题切换通过设置页面完成，会自动保存用户偏好。

---

## 📊 统计功能

### 支持的统计维度

1. **按级别统计**
   - 国家级荣誉数
   - 省级荣誉数
   - 校级荣誉数

2. **按等级统计**
   - 一等奖数量
   - 二等奖数量
   - 三等奖数量
   - 优秀奖数量

3. **可视化展示**
   - 饼图：荣誉级别分布
   - 柱状图：等级分布
   - 数据卡片：实时指标更新

---

## 🔧 开发指南

### 项目架构

采用分层架构设计：
- **表现层（UI）**：PySide6 + qfluentwidgets
- **业务层（Services）**：业务逻辑和数据操作
- **数据层（Models & Database）**：SQLAlchemy ORM + SQLite

### 添加新功能

1. **定义数据模型**（`src/data/models.py`）
2. **编写服务逻辑**（`src/services/`）
3. **创建 UI 页面**（`src/ui/pages/`）
4. **在主窗口注册**（`src/ui/main_window.py`）

### 运行测试

验证 Python 语法：
```bash
python -m py_compile src/
```

---

## 🛡️ 安全性

- ✅ 敏感数据不会上传到 GitHub（`.gitignore` 配置）
- ✅ 数据库文件本地存储
- ✅ 备份文件定期保存
- ✅ 所有用户数据本地加密存储

### .gitignore 配置

以下文件和目录不会提交到版本控制：

```
# 数据库
*.db
*.sqlite
*.sqlite3
data/awards.db

# Python 缓存
__pycache__/
*.pyc
build/
dist/

# 应用数据
attachments/
backups/
logs/
temp/

# IDE 和编辑器
.vscode/
.idea/
*.swp

# 环境变量和密钥
.env
secrets.json
```

---

## 📦 依赖列表

主要依赖包括：
- `PySide6`：Qt 6 Python 绑定
- `qfluentwidgets`：Fluent Design 样式组件
- `SQLAlchemy`：ORM 和数据库抽象
- `matplotlib`：图表绘制
- `pandas`：数据处理

完整列表见 `requirements.txt`。

---

## 📝 许可证

MIT License - 详见 LICENSE 文件

---

## 👨‍💻 作者

RE-TikaRa

---

## 📞 反馈与支持

如有问题或建议，欢迎提交 Issue 或 Pull Request。
