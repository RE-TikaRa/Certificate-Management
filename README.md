<div align="center">
  <!-- Logo Section -->
  <img src="img/LOGO.svg" alt="Logo" width="180" />
  <img src="img/NewLogo.svg" alt="Logo" width="180" />

  <!-- Typing Effect Title -->
  <h1>荣誉证书管理系统</h1>
  <a href="https://git.io/typing-svg">
    <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&pause=1000&color=36BCF7&background=00000000&center=true&vCenter=true&width=500&lines=%E5%85%A8%E7%94%9F%E5%91%BD%E5%91%A8%E6%9C%9F%E8%8D%A3%E8%AA%89%E7%AE%A1%E7%90%86;PySide6+%2B+QFluentWidgets+%E6%89%93%E9%80%A0;%E7%B2%BE%E7%BE%8E%E7%95%8C%E9%9D%A2+%E6%9E%81%E8%87%B4%E4%BD%93%E9%AA%8C;%E6%95%B0%E6%8D%AE%E6%9C%AC%E5%9C%B0%E5%8C%96+%E8%87%AA%E5%8A%A8%E5%A4%87%E4%BB%BD" alt="Typing SVG" />
  </a>

  <p>
    一款功能完整、界面精美的荣誉证书管理桌面应用。<br/>
    支持荣誉证书的全生命周期管理：从录入、统计分析、成员管理到附件管理，一应俱全。<br/>
    <b>当前版本标识：</b> Git commit hash（运行时显示）
  </p>

  <!-- Badges -->
  <p>
    <img src="https://img.shields.io/badge/Python-3.14+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
    <img src="https://img.shields.io/badge/PySide6-Latest-41CD52?style=for-the-badge&logo=qt&logoColor=white" />
    <img src="https://img.shields.io/badge/License-MIT-orange?style=for-the-badge" />
    <img src="https://img.shields.io/badge/Platform-Win%20%7C%20Mac%20%7C%20Linux-lightgrey?style=for-the-badge&logo=linux&logoColor=black" />
  </p>

  <!-- Action Buttons -->
  <p>
    <a href="#-快速开始">
      <img src="https://img.shields.io/badge/🚀_立即运行-Start_Demo-blue?style=flat-square" alt="Start Demo" />
    </a>
    &nbsp;
    <a href="https://github.com/RE-TikaRa/Certificate-Management/issues">
      <img src="https://img.shields.io/badge/🐛_反馈问题-Report_Bug-red?style=flat-square" alt="Report Bug" />
    </a>
    &nbsp;
    <a href="#-文件目录说明">
      <img src="https://img.shields.io/badge/📚_浏览文档-Explore_Docs-green?style=flat-square" alt="Explore Docs" />
    </a>
  </p>
</div>

---

<!-- Table of Contents -->
<details>
  <summary><strong>📖 目录 (点击展开)</strong></summary>

- [✨ 核心特性](#-核心特性)
  - [🎯 功能详情](#-功能详情)
- [🛠️ 技术栈](#️-技术栈)
- [📸 界面预览](#-界面预览)
- [🚀 快速开始](#-快速开始)
  - [📥 安装步骤](#-安装步骤)
  - [🛠️ 常用命令](#️-常用命令)
  - [🧾 AI 证书识别](#-ai-证书识别)
    - [⚙️ 配置与模型](#️-配置与模型)
    - [🧾 使用流程](#-使用流程)
  - [📥 导入 / 导出（CSV/XLSX）](#-导入--导出csvxlsx)
  - [🤖 MCP 接入（本地）](#-mcp-接入本地)
    - [🔌 连接方式](#-连接方式)
    - [🛡️ 权限与安全](#️-权限与安全)
    - [🛠️ 能力概览](#️-能力概览)
    - [⚙️ 常用环境变量](#️-常用环境变量)
- [📂 文件目录说明](#-文件目录说明)
- [🏗️ 项目架构](#️-项目架构)
- [💾 数据模型](#-数据模型)
  - [🏆 荣誉记录 (Awards)](#-荣誉记录-awards)
  - [🧩 荣誉成员快照 (AwardMembers)](#-荣誉成员快照-awardmembers)
  - [👤 参与成员 (TeamMembers)](#-参与成员-teammembers)
  - [🤖 AI 提供商 (AIProviders)](#-ai-提供商-aiproviders)
  - [🏷️ 自定义开关 (CustomFlags/AwardFlagValues)](#️-自定义开关-customflagsawardflagvalues)
  - [🎓 专业与学校 (Majors/Schools)](#-专业与学校-majorsschools)
- [🔐 数据安全与备份](#-数据安全与备份)
- [🎨 主题系统](#-主题系统)
- [🛠️ 开发指南](#️-开发指南)
- [✅ 待办事项](#-待办事项)
- [🧰 故障排查](#-故障排查)
- [📝 更新日志](#-更新日志)
- [📈 Star History](#-star-history)
- [🤝 如何贡献](#-如何贡献)
- [📄 许可证](#-许可证)

</details>

---

## ✨ 核心特性

<div align="center">
  <table>
    <tr>
      <td align="center" width="25%">
        <h3>⚡ 极速检索</h3>
        <p>500ms 防抖全文检索<br/>FTS5 引擎加持</p>
      </td>
      <td align="center" width="25%">
        <h3>📊 数据可视化</h3>
        <p>8 张动态指标卡<br/>图表实时联动</p>
      </td>
      <td align="center" width="25%">
        <h3>🧭 丝滑体验</h3>
        <p>页面异步懒加载<br/>启动速度飞快</p>
      </td>
      <td align="center" width="25%">
        <h3>🛡️ 数据安全</h3>
        <p>本地 SQLite 存储<br/>自动定时备份</p>
      </td>
    </tr>
    <tr>
      <td align="center">
        <h3>🧠 智能补全</h3>
        <p>专业/学院自动匹配<br/>支持拼音/代码搜索</p>
      </td>
      <td align="center">
        <h3>🗑️ 后悔药</h3>
        <p>回收站机制<br/>双重删除确认</p>
      </td>
      <td align="center">
        <h3>🎨 炫彩主题</h3>
        <p>深色/浅色模式<br/>一键实时切换</p>
      </td>
      <td align="center">
        <h3>🛠️ 运维工具</h3>
        <p>一键清理日志/备份<br/>数据库维护工具</p>
      </td>
    </tr>
  </table>
</div>

### 🎯 功能详情

- **首页**: 快速导航与最近动态，一键直达常用功能。
- **仪表盘**: 8 个梯度指标卡 + 饼/柱图可视化 + 最近荣誉速览。
- **总览**: FTS5 全文搜索（比赛名/证书号/成员）+ 筛选排序分页，支持编辑与批量操作。
- **录入**: 卡片式表单，多成员动态管理；集成专业/学校智能搜索（中文/拼音/代码）；支持一键 AI 识别证书（图片/PDF）。
- **成员管理**: 成员库维护与详情，10 字段监控与快速修改。
- **回收站**: 已删除记录可恢复/彻底删除，双重确认。
- **系统设置**: 主题/备份/日志/索引维护与清理工具，自定义开关管理，导入模板下载；AI 与 MCP 配置入口。
- **MCP 接入**: 内置本地 MCP（stdio/SSE）与可选 Web 控制台，默认只读，支持 PII 脱敏与写入开关。

---

## 🛠️ 技术栈

<div align="center">

| **核心框架** | **数据存储** | **工具链** |
| :---: | :---: | :---: |
| ![PySide6](https://img.shields.io/badge/PySide6-41CD52?style=for-the-badge&logo=qt&logoColor=white) | ![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white) | ![UV](https://img.shields.io/badge/UV-Workflow-purple?style=for-the-badge) |
| ![QFluentWidgets](https://img.shields.io/badge/QFluentWidgets-Fluent_UI-0078D4?style=for-the-badge&logo=microsoft&logoColor=white) | ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white) | ![Ruff](https://img.shields.io/badge/Ruff-Linter-FCC21B?style=for-the-badge&logo=python&logoColor=black) |

</div>

- **AI 证书识别**：OpenAI 兼容 API（Chat Completions/Responses）+ PyMuPDF（PDF 渲染）+ Pydantic（结构化解析）
- **MCP**：`mcp`（FastMCP），支持 stdio/SSE；可选 `gradio` Web 控制台
- **日志**：`loguru`（应用日志与 MCP 进程日志输出到 `logs/`）
- **类型检查**：`pyright`（标准模式）+ `ruff`（风格/未使用项）

---

## 📸 界面预览

> 💡 **提示**: 点击图片可查看大图

<div align="center">
  <table>
    <tr>
      <td align="center">
        <img src="https://s2.loli.net/2025/12/10/KbLFB2Ta3E8rCsf.jpg" alt="Home" width="100%" />
        <br/><b>🏠 首页</b><br/>快速导航与最近动态
      </td>
      <td align="center">
        <img src="https://s2.loli.net/2025/12/10/18nQ5Mt9yos4G7j.png" alt="Dashboard" width="100%" />
        <br/><b>📊 仪表盘</b><br/>指标卡 + 统计图表
      </td>
    </tr>
    <tr>
      <td align="center">
        <img src="https://s2.loli.net/2025/12/10/dKcrQUTo3xghDNq.png" alt="Overview" width="100%" />
        <br/><b>👀 总览页</b><br/>FTS5 搜索 + 筛选排序
      </td>
      <td align="center">
        <img src="https://s2.loli.net/2025/12/10/IA1hHyCiEGlfNSx.png" alt="Entry" width="100%" />
        <br/><b>📝 录入页</b><br/>成员卡片式表单 + AI 识别
      </td>
    </tr>
    <tr>
      <td align="center">
        <img src="https://s2.loli.net/2025/12/10/whom7bQ8pHrvdiT.png" alt="Members" width="100%" />
        <br/><b>👥 成员管理</b><br/>10 字段监控与详情
      </td>
      <td align="center">
        <img src="https://s2.loli.net/2025/12/10/eC2vklNYSyF5ipo.png" alt="Settings" width="100%" />
        <br/><b>⚙️ 设置页</b><br/>主题/备份/清理/日志
      </td>
    </tr>
  </table>
</div>

---

## 🚀 快速开始

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.14+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/UV-Package_Manager-purple?style=flat-square" />
  <img src="https://img.shields.io/badge/SQLite-Database-003B57?style=flat-square&logo=sqlite&logoColor=white" />
</div>

### 📥 安装步骤

1. **克隆仓库**
   ```bash
   git clone https://github.com/RE-TikaRa/Certificate-Management.git
   cd Certificate-Management
   ```

2. **安装依赖** (推荐使用 `uv`)
   ```bash
   # 安装 uv (如果尚未安装)
   # pip install uv
   
   # 同步环境
   uv sync
   ```

3. **启动应用**
   ```bash
   # Windows 快捷启动
   ./main.bat
   
   # 或使用 uv 启动
   uv run python -m src.main
   ```

### 🛠️ 常用命令

| 操作 | 命令 | 说明 |
| :--- | :--- | :--- |
| **运行** | `uv run python -m src.main` | 启动主程序 |
| **调试** | `uv run python -m src.main --debug` | 开启调试日志 |
| **检查** | `uv run ruff check .` | 代码 Lint 检查 |
| **格式化** | `uv run ruff format .` | 代码自动格式化 |
| **类型检查** | `uv run python -m pyright` | Pyright 标准模式 |
| **语法检查** | `uv run python -m py_compile src/` | 基础语法编译检查 |
| **MCP 服务** | `uv run certificate-mcp` | 启动 MCP（默认 stdio，只读） |
| **MCP SSE** | `CERT_MCP_TRANSPORT=sse uv run certificate-mcp` | 启动 SSE（默认 `http://127.0.0.1:8000/sse`；推荐用设置页随软件启动） |
| **MCP Web** | `uv run certificate-mcp-web` | 启动本地 Web 控制台（需安装可选依赖；默认 `http://127.0.0.1:7860`） |

---

### 🧾 AI 证书识别

AI 证书识别用于“荣誉录入”页面的一键识别：从证书图片/PDF 自动抽取 **比赛名称、获奖日期、赛事级别、奖项等级、证书编号、成员姓名**，并在预览对话框中确认后再写入表单。

#### ⚙️ 配置与模型

1. 打开 **系统设置 → AI 证书识别**，勾选“启用 AI 证书识别”
2. 配置一个提供商（Provider）
   - **API 地址**：OpenAI 兼容地址（如 `https://api.openai.com` 或你的兼容中转）
   - **API Key**：支持多 Key，程序会按请求轮换（见下文）
   - **模型**：可手动填写模型 ID；若你的服务支持 `/v1/models`，可在设置页刷新/选择
   - **PDF 页数**：1~10（PDF 会渲染前 N 页作为图片参与识别）
3. 点击“测试联通”验证配置（会发起最小请求）

说明（按当前实现）：
- 支持文件：`.pdf` `.png` `.jpg` `.jpeg` `.webp`
- Key 轮换：每次调用（识别证书、刷新模型、测试联通）都会轮到下一个 Key；**当前不会在失败时自动切 Key 重试**
- OpenAI 官方 `api.openai.com`：会走 `responses` 接口；PDF 会以文件方式上传，图片会以单张图片方式上传
- 兼容服务：走 `/v1/chat/completions`；PDF 会按“PDF 页数”渲染多页图片后发送

#### 🧾 使用流程

1. 在 **荣誉录入** 页点击顶部“AI 识别证书”
2. 选择证书文件后，程序会自动将其加入附件并开始识别
3. 在“AI 识别预览”中确认/修改结果后应用到表单

---

### 📥 导入 / 导出（CSV/XLSX）

- **入口**：系统设置 → 导入/导出
- **导入**：支持 CSV/XLSX；表头需与模板一致；可选字段 **附件路径**（用 `;` 分隔多个文件的绝对路径）
- **导出**：导出文件包含 **附件数量** 与 **附件路径**；若要回导请确保附件文件在原路径可访问（跨机器需自行拷贝并修正路径）

---

### 🤖 MCP 接入（本地）

本项目内置了 MCP (Model Context Protocol) 服务，允许 AI Agent（如 Claude Desktop、Cursor 等）安全地读取本地荣誉数据与附件。

#### 🔌 连接方式

1. **stdio 模式（推荐）**
   - **适用场景**：本地客户端直接拉起进程（无需占用端口）。
   - **启动命令**：`uv run certificate-mcp`
   - **配置示例**：见下文“客户端配置示例”。

2. **SSE 模式（HTTP 服务）**
   - **适用场景**：本机调试（HTTP）。
   - **地址**：`http://127.0.0.1:8000/sse`
   - **启动方式**：
     - **自动（推荐）**：在“设置页 → MCP 服务”中开启“随软件启动 MCP”。
     - **手动**：`CERT_MCP_TRANSPORT=sse uv run certificate-mcp`
   - **日志**：`logs/mcp_sse.log`
   - **注意**：服务端强制本地绑定，`CERT_MCP_HOST` 只能是 `127.0.0.1` / `localhost` / `::1`，请勿暴露到公网。

   <details>
   <summary><strong>Windows PowerShell 手动启动命令</strong></summary>

   ```powershell
   $env:CERT_MCP_TRANSPORT = "sse"
   $env:CERT_MCP_HOST = "127.0.0.1"
   $env:CERT_MCP_PORT = "8000"
   uv run certificate-mcp
   ```
   </details>

3. **Web 控制台（调试用）**
   - **功能**：提供一个 Web 界面来测试 MCP 工具调用。
   - **安装**：`uv sync --group mcp-web`（或在设置页点击安装）。
   - **启动**：`uv run certificate-mcp-web`（默认访问 `http://127.0.0.1:7860`）。
   - **说明**：无登录，仅用于本机调试；如关闭后端口仍占用见“故障排查”。

#### 🛡️ 权限与安全

- **默认只读**：默认不允许写入数据库或修改文件。如需开启写入（仅限本地），请在设置页勾选或设置环境变量 `CERT_MCP_ALLOW_WRITE=1`。
- **隐私保护**：默认开启 PII 脱敏（`CERT_MCP_REDACT_PII=1`），自动隐藏身份证号与手机号中间位。
- **附件限额**：单次读取附件最大 1MB（可配置 `CERT_MCP_MAX_BYTES`）。
- **网络安全**：服务默认绑定 `127.0.0.1`，请勿暴露到公网。

#### 🛠️ 能力概览

- **Tools (工具)**：
  - `list_awards` / `get_award` / `search_awards`：查询荣誉记录。
  - `list_members` / `get_member`：查询成员信息。
  - `read_attachment`：读取附件内容（支持文本提取）。
  - `health`：健康检查。
- **Resources (资源)**：
  - `docs://readme` / `docs://agents`：读取项目 README/AGENTS 指南。
  - `schema://models`：查看数据库模型定义。
  - `templates://awards_csv`：获取导入模板。

#### ⚙️ 常用环境变量

| 变量名 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `CERT_MCP_TRANSPORT` | 传输模式 (`stdio`/`sse`) | `stdio` |
| `CERT_MCP_HOST` | SSE Host（仅允许本地） | `127.0.0.1` |
| `CERT_MCP_PORT` | SSE 端口 | `8000` |
| `CERT_MCP_ALLOW_WRITE` | 允许写入 (`0`/`1`) | `0` |
| `CERT_MCP_REDACT_PII` | 敏感信息脱敏 (`0`/`1`) | `1` |
| `CERT_MCP_MAX_BYTES` | 单次附件读取上限（字节） | `1048576` |
| `CERT_MCP_DEBUG` | 输出调试错误细节 (`0`/`1`) | `0` |
| `CERT_MCP_WEB_HOST` | Web 控制台 Host | `127.0.0.1` |
| `CERT_MCP_WEB_PORT` | Web 控制台端口 | `7860` |
| `CERT_MCP_WEB_INBROWSER` | 是否自动打开浏览器 (`0`/`1`) | `1` |

<details>
<summary><strong>📎 客户端配置示例 (Claude Desktop / Cursor)</strong></summary>

**stdio 模式 (推荐)**：

```json
{
  "mcpServers": {
    "certificate": {
      "command": "uv",
      "args": ["run", "certificate-mcp"],
      "env": {
        "CERT_MCP_ALLOW_WRITE": "0",
        "CERT_MCP_REDACT_PII": "1"
      }
    }
  }
}
```

**SSE 模式**：

```json
{
  "mcpServers": {
    "certificate": {
      "type": "sse",
      "url": "http://127.0.0.1:8000/sse"
    }
  }
}
```

</details>

## 📂 文件目录说明

<details>
<summary><strong>点击展开完整目录树</strong></summary>

```
Certificate-Management/
├── 📄 README.md                    # 项目文档
├── ⚙️ pyproject.toml               # 依赖配置
├── 🔒 uv.lock                      # 依赖锁定
├── 🚀 main.bat                     # Windows 启动脚本
├── 🚫 .gitignore                   # Git 忽略规则
├── 🧰 tools/                       # 开发辅助脚本（可选）
│
├── 📦 src/                         # 源代码
│   ├── 🏁 main.py                  # 入口文件
│   ├── 🌍 app_context.py           # DI 容器
│   ├── ⚙️ config.py                # 配置加载
│   ├── 📝 logger.py                # 日志配置
│   ├── 🤖 mcp/                     # MCP 模块（本地）
│   │   ├── server.py               # MCP 服务端（默认只读）
│   │   ├── web.py                  # MCP 本地 Web 控制台（可选）
│   │   ├── helpers.py              # MCP 配置/解析辅助
│   │   └── runtime.py              # MCP 进程/自启动管理（本地）
│   │
│   ├── 💾 data/                    # 数据层
│   │   ├── models.py               # SQLAlchemy 模型
│   │   └── database.py             # 数据库会话
│   │
│   ├── 🔧 services/                # 业务层
│   │   ├── award_service.py        # 荣誉逻辑
│   │   ├── statistics_service.py   # 统计分析
│   │   ├── import_export.py        # 导入导出
│   │   ├── ai_certificate_service.py # AI 证书识别（OpenAI 兼容 API）
│   │   ├── ai_provider_service.py  # AI Provider / Key 轮换
│   │   ├── attachment_manager.py   # 附件存储/去重/回收站
│   │   ├── backup_manager.py       # 备份/验证/恢复（含定时任务）
│   │   ├── flag_service.py         # 自定义布尔开关（flag）
│   │   └── ...
│   │
│   ├── 🎨 ui/                      # 表现层
│   │   ├── main_window.py          # 主窗口
│   │   ├── styled_theme.py         # 主题管理
│   │   ├── pages/                  # 各功能页面
│   │   └── widgets/                # 自定义组件
│   │
│   └── 📂 resources/               # 静态资源
│       ├── styles/                 # QSS 样式
│       └── templates/              # 导入模板
│
├── 📂 data/                        # 数据库存储 (自动生成)
├── 📂 attachments/                 # 附件存储
├── 📂 backups/                     # 自动备份
├── 📂 logs/                        # 运行日志
└── 📂 docs/                        # 文档与参考数据
```
</details>

---

## 🏗️ 项目架构

```mermaid
flowchart TD
    subgraph UI [表现层 Presentation]
        direction TB
        MainWindow[主窗口 MainWindow]
        Pages[页面 Pages]
        Widgets[组件 Widgets]
        Theme[主题 ThemeManager]
    end

    subgraph Service [业务层 Business Logic]
        direction TB
        AwardSvc[荣誉服务 AwardService]
        StatSvc[统计服务 StatisticsService]
        BackupSvc[备份服务 BackupManager]
        ImportSvc[导入服务 ImportExport]
        AttachSvc[附件服务 AttachmentManager]
        FlagSvc[开关服务 FlagService]
        AISvc[AI 证书识别 AICertificateService]
    end

    subgraph Data [数据层 Data Access]
        direction TB
        ORM[SQLAlchemy ORM]
        SQLite[(SQLite Database)]
    end

    subgraph Integration [集成 Integration]
        direction TB
        MCP[MCP Server (FastMCP)]
    end

    UI --> Service
    Service --> Data
    MCP --> Service
    
    style UI fill:#e1f5fe,stroke:#01579b
    style Service fill:#fff3e0,stroke:#ff6f00
    style Data fill:#e8f5e9,stroke:#2e7d32
    style Integration fill:#f3e5f5,stroke:#6a1b9a
```

> **架构说明**：本项目采用经典的三层架构（表现层、业务层、数据层），各层职责分明，通过依赖注入（DI）容器 `AppContext` 进行解耦。

---

## 💾 数据模型

<details>
<summary><strong>查看详细数据库表结构</strong></summary>

### 🏆 荣誉记录 (Awards)
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `id` | Integer | 主键 |
| `competition_name` | String | 比赛名称 |
| `award_date` | Date | 获奖日期 |
| `level` | String | 级别（国家/省/校等） |
| `rank` | String | 等级（一/二/三/优秀） |
| `certificate_code` | String | 证书编号 |
| `remarks` | Text | 备注 |
| `attachment_folder` | String | 附件目录相对路径 |
| `deleted` / `deleted_at` | Bool/DateTime | 软删除标记 |
| `created_at` / `updated_at` | DateTime | 时间戳 |
| `award_members` | Relation | 荣誉成员快照（`AwardMember`，级联删除） |
| `attachments` | Relation | 附件（级联删除） |

### 🧩 荣誉成员快照 (AwardMembers)
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `id` | Integer | 主键 |
| `award_id` | FK | 关联荣誉 |
| `member_id` | FK / Nullable | 关联成员库（可空；未入库则为空） |
| `member_name` | String | 当时录入的姓名快照（必填） |
| `sort_order` | Integer | 成员顺序 |

### 👤 参与成员 (TeamMembers)
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `id` | Integer | 主键 |
| `name` | String | 姓名 |
| `gender` | String | 性别 |
| `id_card` | String | 身份证号（唯一） |
| `phone` | String | 手机号 |
| `student_id` | String | 学号（唯一） |
| `email` | String | 邮箱 |
| `school` / `school_code` | String | 学校名称/标识码 |
| `major` / `major_code` | String | 专业名称/代码 |
| `class_name` | String | 班级 |
| `college` | String | 学院 |
| `pinyin` | String | 姓名拼音 |
| `active` | Bool | 启用状态 |
| `sort_index` | Integer | 排序权重 |
| `created_at` / `updated_at` | DateTime | 时间戳 |
| `award_associations` | Relation | 通过 `AwardMember` 关联荣誉（成员库可变更不影响历史快照） |

### 🤖 AI 提供商 (AIProviders)
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `id` | Integer | 主键 |
| `name` | String | 提供商名称（唯一） |
| `api_base` | String | OpenAI 兼容 API Base |
| `api_keys` | Text | 多 Key（支持 `name|key`） |
| `model` | String | 默认模型 ID |
| `pdf_pages` | Integer | PDF 渲染页数（1~10） |
| `last_key_index` | Integer | Key 轮换索引（-1 表示未开始） |

> `settings.ai_active_provider_id` 用于标记当前激活的 provider；旧版单配置（`ai_api_base/ai_api_key/ai_model`）会在首次启动时迁移到默认 provider。

### 🏷️ 自定义开关 (CustomFlags/AwardFlagValues)
| 模型 | 关键字段 | 说明 |
| :--- | :--- | :--- |
| `CustomFlag` | `key`(唯一), `label`, `enabled`, `default_value`, `sort_order` | 自定义布尔开关定义（用于录入/导出/筛选） |
| `AwardFlagValue` | `award_id`, `flag_key`, `value` | 荣誉对应的开关值（与 `award_id+flag_key` 唯一） |

### 🎓 专业与学校 (Majors/Schools)
| 模型 | 关键字段 | 说明 |
| :--- | :--- | :--- |
| `Major` | `name`(唯一), `code`(唯一), `pinyin`, `category`, `discipline_code/name`, `class_code/name`, 时间戳 | 2025 本科专业目录（约 840 条） |
| `School` | `name`(唯一), `code`(唯一), `pinyin`, `region`, 时间戳 | 全国高校列表 |
| `SchoolMajorMapping` | `school_name/code`, `major_name/code`, `college_name`, `category`, `discipline_*`, `class_*` | 学校-专业-学院映射，支持代码缺失时按名称回退 |
| `Attachment` | `award_id`, `stored_name`, `original_name`, `relative_path`(唯一), `file_md5`, `file_size`, `deleted`, 时间戳 | 附件记录 |
| `BackupRecord` / `ImportJob` | 路径/状态/消息/时间戳 | 备份与导入任务记录 |

*(更多模型细节请查阅源码 `src/data/models.py`)*
</details>

---

## 🔐 数据安全与备份

<div align="center">
  <table>
    <tr>
      <td width="50%">
        <h4>🛡️ 本地优先</h4>
        <p>数据存于 <code>data/awards.db</code>，附件在 <code>attachments/</code>，默认不上传云端。</p>
      </td>
      <td width="50%">
        <h4>🔄 自动备份</h4>
        <p>支持手动/启动时/每日/每周备份；基于 SQLite <code>backup()</code> 生成快照，并可在恢复前自动创建还原点。</p>
      </td>
    </tr>
    <tr>
      <td>
        <h4>🗑️ 回收站</h4>
        <p>删除荣誉进入回收站可恢复；附件删除会移入 <code>attachments/.trash</code>。</p>
      </td>
      <td>
        <h4>🧹 清理策略</h4>
        <p>提供日志/备份清空与数据库重建（reset）工具，均带双重确认；数据库清空会重建空库并重载默认设置。</p>
      </td>
    </tr>
  </table>
</div>

> ⚠️ **隐私提醒**：请勿将 `data/`、`backups/`、`attachments/`、`logs/`、`.env` 等敏感目录提交到版本控制系统。

---

## 🎨 主题系统

应用内置了一套精美的色彩系统，适配深色/浅色模式。

| 指标类型 | 渐变色 (Light -> Dark) | 语义 |
| :--- | :--- | :--- |
| **总荣誉** | `💜 #a071ff` → `#7b6cff` | 综合实力 |
| **国家级** | `💙 #5a80f3` → `#4ac6ff` | 最高荣誉 |
| **省级** | `💛 #ffb347` → `#ffcc33` | 中坚力量 |
| **校级** | `💚 #3ec8a0` → `#45dd8e` | 基础积累 |
| **一等奖** | `💠 #00b4d8` → `#48cae4` | 顶尖表现 |
| **二等奖** | `💜 #b54cb8` → `#d896ff` | 稳定发挥 |
| **三等奖** | `❤️ #ff6b6b` → `#ff8787` | 鼓励奖项 |
| **优秀奖** | `🤍 #999999` → `#b3b3b3` | 参与/优秀 |

---

## 🛠️ 开发指南

1. **环境准备**: 确保 Python 3.14+，推荐使用 `uv` 管理虚拟环境。
2. **新增页面**: 继承 `BasePage`，在 `main_window.py` 中注册路由。
3. **数据库变更**: 修改 `models.py`，目前使用自动建表，生产环境建议引入 Alembic。
4. **代码规范**: 提交前请运行 `ruff check` 和 `pyright`。
5. **版本与文档**: 版本号统一来自 `pyproject.toml`（运行时由 `src/version.py` 读取）；每次提交前更新版本号，并同步更新 README 顶部/更新日志与应用“关于”页文案。

---

## ✅ 待办事项

> 说明：以下为“深度待办”，给出最小可落地范围（MVP）、依赖与影响模块，便于分阶段推进。

<details>
<summary><strong>状态流转（草稿/已提交/已归档/撤回）</strong></summary>

- MVP: 新增 `status` 字段，列表筛选与批量切换状态，详情页显示状态
- 依赖/风险: 数据库结构变更；历史数据迁移策略
- 影响模块: `models.py` / `award_service.py` / `overview_page.py` / `entry_page.py`
</details>

<details>
<summary><strong>批量变更（等级/奖项/日期/自定义开关/标签）</strong></summary>

- MVP: 总览页批量操作面板，支持等级/奖项/日期/开关批量更新
- 依赖/风险: 需要服务层批量更新接口，注意事务与校验
- 影响模块: `overview_page.py` / `award_service.py`
</details>

<details>
<summary><strong>高级搜索（成员字段/备注/证书号/附件名；保存条件）</strong></summary>

- MVP: 搜索条件面板 + 可保存条件；支持成员/备注/证书号/附件名组合检索
- 依赖/风险: FTS 与普通查询合并逻辑；性能与分页兼容
- 影响模块: `overview_page.py` / `award_service.py` / `database.py`
</details>

<details>
<summary><strong>统计扩展（学院/专业/年级/赛事维度）</strong></summary>

- MVP: 新增 2-3 维度统计卡与图表，支持导出统计明细
- 依赖/风险: 维度字段完整性与历史数据缺失处理
- 影响模块: `statistics_service.py` / `dashboard_page.py` / `overview_page.py`
</details>

<details>
<summary><strong>批量识别队列（AI 识别任务队列/暂停/重试）</strong></summary>

- MVP: 识别队列表（任务/状态/重试次数）；支持暂停与失败重试
- 依赖/风险: 后台任务调度与并发控制；失败回退策略
- 影响模块: `ai_certificate_service.py` / `entry_page.py` / `settings_page.py`
</details>

<details>
<summary><strong>导出模板增强（含图片/二维码/PDF 汇总）</strong></summary>

- MVP: PDF 汇总导出（含附件缩略图与二维码）；模板字段可配置
- 依赖/风险: 文档渲染与排版稳定性；大批量导出性能
- 影响模块: `import_export.py` / `settings_page.py` / `resources/templates`
</details>

<details>
<summary><strong>MCP 工具扩展（批量导入/导出/统计查询指令）</strong></summary>

- MVP: MCP 增加批量导入/导出/统计查询工具
- 依赖/风险: 写入权限控制；PII 脱敏规则
- 影响模块: `mcp/server.py` / `mcp/helpers.py` / `services/*`
</details>

<details>
<summary><strong>权限/多用户（角色/审计）</strong></summary>

- MVP: 基础账号与角色（只读/录入/管理员）+ 操作日志
- 依赖/风险: 登录与会话管理；本地单机兼容
- 影响模块: `models.py` / `settings_page.py` / `main_window.py`
</details>

<details>
<summary><strong>备份策略（增量/云盘路径/自动轮转）</strong></summary>

- MVP: 备份轮转与保留策略；支持指定云盘目录
- 依赖/风险: 文件锁与权限；恢复流程一致性
- 影响模块: `backup_manager.py` / `settings_page.py`
</details>

<details>
<summary><strong>快捷录入（历史复用/常用成员组合）</strong></summary>

- MVP: 最近一次录入复用；常用成员组合一键填充
- 依赖/风险: 成员快照与入库逻辑一致性
- 影响模块: `entry_page.py` / `member_service.py`
</details>

<details>
<summary><strong>附件预览（PDF/图片预览与基础编辑）</strong></summary>

- MVP: 预览窗口（PDF/图片）；基础旋转/缩放
- 依赖/风险: 渲染性能；大文件内存占用
- 影响模块: `overview_page.py` / `attachment_manager.py` / `ui/widgets`
</details>

---

## 🧰 故障排查

<details>
<summary><strong>点击查看常见问题解决方案</strong></summary>

| 问题现象 | 可能原因 | 解决方案 |
| :--- | :--- | :--- |
| **启动缺少 Qt 插件** | 环境依赖不完整 | 运行 `uv sync`，若无效则删除 `.venv` 重试 |
| **界面文字乱码** | 字体缺失或编码问题 | 检查系统字体，确认未强制覆盖 `QFontDatabase` |
| **数据库被锁** | 异常退出导致锁文件残留 | 先关闭应用；仍锁时删除 `data/awards.db-shm` 和 `.db-wal`（恢复备份前程序会尝试清理这两类文件） |
| **导入无响应** | 模板格式错误 | 确认 CSV/XLSX 表头与模板一致，查看设置页日志 |
| **MCP 连接失败** | 端口未启动/URL 错误/依赖缺失 | SSE：确认 `http://127.0.0.1:8000/sse` 且设置页已启动；Web：先 `uv sync --group mcp-web`，再启动 Web 控制台并访问 `http://127.0.0.1:7860` |
| **MCP Web 关闭后端口仍占用（7860）** | 进程未退出/残留子进程 | 退出应用与相关终端后，用 `netstat -ano \| findstr :7860` 查 PID，再 `taskkill /PID <pid> /T /F` |
| **MCP SSE 启动报 host 限制** | MCP 服务仅允许本地绑定 | 将 `CERT_MCP_HOST` 设置为 `127.0.0.1` / `localhost` / `::1`（或直接用设置页启动） |
| **AI 识别提示缺少 PDF 依赖** | 未安装 PyMuPDF | 运行 `uv sync` 安装依赖（需要识别 PDF 时必须） |
| **AI 识别失败：Cloudflare 1010** | 网络/代理/风控拦截 | 更换网络/代理或更换中转；该错误通常与本机环境无关 |
| **AI 识别失败：模型输出不是有效 JSON** | 模型不按要求输出结构化结果 | 更换模型/提供商；确保模型支持图像输入，并尝试在设置页手动填写模型 ID |
| **主题不更新** | 信号未连接 | 检查 `__init__` 是否连接 `themeChanged` 信号 |
| **附件校验失败** | 文件被占用或修改 | 检查文件权限，清空回收站后重试 |

</details>

---

## 📝 更新日志

> 版本号不再维护，统一以 Git commit hash 作为版本标识。
> 当前版本标识以运行时/仓库 HEAD 为准。

---

## 📈 Star History

<a href="https://star-history.com/#RE-TikaRa/Certificate-Management&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=RE-TikaRa/Certificate-Management&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=RE-TikaRa/Certificate-Management&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=RE-TikaRa/Certificate-Management&type=Date" />
 </picture>
</a>

---

## 🤝 如何贡献

非常欢迎您的贡献！请遵循以下流程：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

---

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

---

<div align="center">
  <p>
    <b>Author:</b> <a href="https://github.com/RE-TikaRa">RE-TikaRa</a> |
    <b>Powered by:</b> PySide6 & QFluentWidgets
  </p>

  <p>
    <a href="https://github.com/RE-TikaRa/Certificate-Management/stargazers">
      <img src="https://img.shields.io/github/stars/RE-TikaRa/Certificate-Management?style=social" alt="GitHub stars" />
    </a>
    <a href="https://github.com/RE-TikaRa/Certificate-Management/network/members">
      <img src="https://img.shields.io/github/forks/RE-TikaRa/Certificate-Management?style=social" alt="GitHub forks" />
    </a>
  </p>
</div>
