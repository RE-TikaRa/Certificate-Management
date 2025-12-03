# Certificate Management System - AI Agents Reference Guide

## Project Overview

**Project Name:** 荣誉证书管理系统 (Certificate Management System)

**Type:** Desktop Application GUI

**Tech Stack:**
- **GUI Framework:** PySide6 6.10.1 + QFluentWidgets 1.9.2
- **Database:** SQLAlchemy 2.0.32 + SQLite
- **Language:** Python 3.9+
- **Architecture:** 3-Layer (Presentation / Business / Data)

**Repository:** https://github.com/RE-TikaRa/Certificate-Management

---

## Directory Structure

```
src/
├── main.py                      # Entry point
├── app_context.py               # Dependency injection & bootstrap
├── config.py                    # Configuration management
├── logger.py                    # Logging setup
├── data/
│   ├── models.py               # SQLAlchemy ORM models (Award, TeamMember)
│   └── database.py             # Database connection & session management
├── services/
│   ├── award_service.py        # Award CRUD operations
│   ├── statistics_service.py   # Statistics & analytics
│   ├── import_export.py        # CSV import/export
│   ├── backup_manager.py       # Auto-backup functionality
│   ├── attachment_manager.py   # File attachment handling
│   └── settings_service.py     # Application settings
├── ui/
│   ├── main_window.py          # Main window frame & navigation
│   ├── theme.py                # UI utility functions
│   ├── styled_theme.py         # Theme management (light/dark)
│   └── pages/
│       ├── base_page.py        # Page base class
│       ├── home_page.py        # Home page
│       ├── dashboard_page.py   # Metrics & analytics dashboard
│       ├── entry_page.py       # Award entry form
│       ├── overview_page.py    # Award list with editing dialog
│       ├── management_page.py  # Member management & history
│       ├── recycle_page.py     # Attachment recycle bin
│       └── settings_page.py    # System settings
└── resources/
    ├── styles/                 # QSS stylesheets
    │   ├── styled_light.qss    # Light theme
    │   └── styled_dark.qss     # Dark theme
    └── templates/
        └── awards_template.csv # CSV import template
```

---

## Data Models

### Award (荣誉记录)
```python
# src/data/models.py
class Award(Base):
    __tablename__ = 'awards'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    competition_name: Mapped[str]           # Competition name
    award_date: Mapped[date]                # Award date
    level: Mapped[str]                      # Level: 国家级/省级/校级
    rank: Mapped[str]                       # Rank: 一等奖/二等奖/三等奖/优秀奖
    certificate_code: Mapped[str]           # Certificate number
    remarks: Mapped[str | None]             # Notes
    created_at: Mapped[datetime]            # Creation timestamp
    updated_at: Mapped[datetime]            # Last update timestamp
    
    # Relationships
    members: Mapped[list['TeamMember']] = relationship(
        secondary='award_member_association',
        back_populates='awards'
    )
```

**Key Fields:**
- `level`: Accepts "国家级", "省级", "校级"
- `rank`: Accepts "一等奖", "二等奖", "三等奖", "优秀奖"
- `member_names`: JSON field storing member information

### TeamMember (参与成员)
```python
class TeamMember(Base):
    __tablename__ = 'team_members'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]               # Name
    gender: Mapped[str]             # Gender
    id_card: Mapped[str]            # ID card number
    phone: Mapped[str]              # Phone
    student_id: Mapped[str]         # Student ID
    email: Mapped[str]              # Email
    major: Mapped[str]              # Major
    class_name: Mapped[str]         # Class
    college: Mapped[str]            # College
    
    # Relationships
    awards: Mapped[list['Award']] = relationship(
        secondary='award_member_association',
        back_populates='members'
    )
```

**9 Fields Total:** name, gender, id_card, phone, student_id, email, major, class_name, college

---

## Service Layer

### AwardService
**Location:** `src/services/award_service.py`

**Key Methods:**
- `get_all_awards()` - Retrieve all awards
- `get_award_by_id(award_id)` - Get single award
- `create_award(data)` - Create new award
- `update_award(award_id, data)` - Update award
- `delete_award(award_id)` - Delete award
- `search_awards(query)` - Search awards
- `get_recent_awards(limit=10)` - Get latest awards

**Important:** Member data is stored in `member_names` field as JSON structure with 9 fields per member.

### StatisticsService
**Location:** `src/services/statistics_service.py`

**Key Methods:**
- `get_level_statistics()` - Awards by level (国家级/省级/校级)
- `get_rank_statistics()` - Awards by rank (一等奖/二等奖/三等奖/优秀奖)
- `get_metrics()` - 8 key metrics for dashboard
- `get_member_count()` - Total members
- `get_award_trend()` - Time-series data

**Dashboard Metrics (8 total):**
1. Total awards
2. National level awards
3. Provincial level awards
4. School level awards
5. First rank awards
6. Second rank awards
7. Third rank awards
8. Excellence awards

### ManagementPageService
**Auto-refresh Detection:** Checks these 10 fields for changes:
- id, name, gender, id_card, phone, student_id, email, major, class_name, college

---

## UI Architecture

### Main Window
**Location:** `src/ui/main_window.py`

**Key Features:**
- `_center_window()` - Centers window on screen
- `_init_navigation_fast()` - Quick home page load
- `_load_remaining_pages()` - Background async page loading (100ms delay)
- Dynamic theme switching (light/dark)
- Navigation bar with 7 pages

**Pages Registration:**
```
home → dashboard → overview → entry → management → recycle → settings
```

### Base Page
**Location:** `src/ui/pages/base_page.py`

All pages inherit from `BasePage`:
```python
class BasePage(QWidget):
    def __init__(self, ctx: AppContext, theme_manager: ThemeManager):
        super().__init__()
        self.ctx = ctx  # Context with all services
        self.theme_manager = theme_manager
```

**Context (ctx) includes:**
- `ctx.awards` - AwardService
- `ctx.statistics` - StatisticsService
- `ctx.settings` - SettingsService
- `ctx.members` - Member management
- etc.

### Key Pages

#### DashboardPage
**Location:** `src/ui/pages/dashboard_page.py`

**Components:**
- 8 metric cards with gradient colors
- Recent awards table (5 columns, read-only)
- Pie chart: level distribution
- Bar chart: rank distribution
- Summary tables

**Color Scheme:**
```
总数: Purple (#a071ff → #7b6cff)
国家级: Blue (#5a80f3 → #4ac6ff)
省级: Gold (#ffb347 → #ffcc33)
校级: Green (#3ec8a0 → #45dd8e)
一等奖: Cyan (#00b4d8 → #48cae4)
二等奖: Purple-pink (#b54cb8 → #d896ff)
三等奖: Red (#ff6b6b → #ff8787)
优秀奖: Blue (#5a80f3 → #4ac6ff)
```

#### EntryPage
**Location:** `src/ui/pages/entry_page.py`

**Features:**
- Award form fields (name, date, level, rank, code, remarks)
- Member card system (2-column dynamic layout)
- Add/remove member cards
- 9 member fields per card
- Real-time validation

**Member Card Layout:**
```
Column 1: name, gender, id_card, phone, student_id
Column 2: email, major, class_name, college
```

#### OverviewPage
**Location:** `src/ui/pages/overview_page.py`

**Components:**
- Award list with cards
- Edit button → AwardDetailDialog
- Delete button with confirmation
- AwardDetailDialog class (complete member management)

**AwardDetailDialog Features:**
- Display existing award data
- Member card system (matches entry_page)
- Add/remove members in dialog
- Save with member refresh
- Auto-refresh management_page after save

**Parent Traversal for Refresh:**
```python
# In AwardDetailDialog._save()
parent = self.parent()
while parent:
    if hasattr(parent, 'management_page') and parent.management_page:
        parent.management_page.refresh()
        break
    parent = parent.parent()
```

#### ManagementPage
**Location:** `src/ui/pages/management_page.py`

**Features:**
- Member list view
- Member details (all awards they participated in)
- Edit member information
- Auto-refresh on data changes

**Auto-refresh Detection (10 fields):**
- Monitors: id, name, gender, id_card, phone, student_id, email, major, class_name, college
- Triggers refresh when any field changes

#### SettingsPage
**Location:** `src/ui/pages/settings_page.py`

**Settings:**
- Theme selection (light/dark)
- Auto-backup frequency
- Log level configuration
- Data directory path
- Backup management

---

## Theme System

### ThemeManager
**Location:** `src/ui/styled_theme.py`

**Methods:**
- `set_theme(theme)` - Switch between Light/Dark
- `get_window_stylesheet()` - Complete window styling
- `apply_theme_color(widget)` - Apply colors to widgets
- `is_dark` - Current theme state

**Color Palette:**
- Deep theme card background: `#353751`
- Light theme card background: `#f5f5f5`
- QSS files: `styled_light.qss` and `styled_dark.qss`

---

## Database & Session Management

### Database Module
**Location:** `src/data/database.py`

**Key Components:**
- SQLite local database (`data/awards.db`)
- SQLAlchemy session management
- `session_scope()` context manager for transactions
- Support for transaction rollback

**Usage Pattern:**
```python
from src.data.database import session_scope

with session_scope() as session:
    award = session.query(Award).filter(Award.id == award_id).first()
    # Transaction auto-commits or rolls back
```

---

## Common Development Tasks

### Adding a New Award Field

1. **Update Model** (`src/data/models.py`):
   ```python
   new_field: Mapped[str | None] = mapped_column(nullable=True)
   ```

2. **Update Service** (`src/services/award_service.py`):
   - Add to create/update methods

3. **Update UI Forms** (`entry_page.py`, `overview_page.py`):
   - Add input widget
   - Add to member cards if applicable

4. **Update Dashboard** if it's a statistical field:
   - Update `StatisticsService`
   - Update metric cards in `dashboard_page.py`

### Adding a New Page

1. **Create Page Class** (`src/ui/pages/new_page.py`):
   ```python
   from .base_page import BasePage
   
   class NewPage(BasePage):
       def __init__(self, ctx: AppContext, theme_manager: ThemeManager):
           super().__init__(ctx, theme_manager)
           self._init_ui()
       
       def _init_ui(self):
           # Build UI layout
           pass
   ```

2. **Register in MainWindow** (`src/ui/main_window.py`):
   - Add to `_load_remaining_pages()`
   - Add to pages list with icon and label
   - Update route_keys dictionary

3. **Update Navigation**:
   - Add icon import (FluentIcon)
   - Register in navigation bar

### Modifying Member Data Refresh

**Location:** `src/ui/pages/management_page.py`

**Method:** `_auto_refresh()`

**Current Monitoring (10 fields):**
```python
old_tuple = (m.id, m.name, m.gender, m.id_card, m.phone, 
             m.student_id, m.email, m.major, m.class_name, m.college)
```

**To Add New Fields:**
1. Add to tuple in `_auto_refresh()`
2. Update dialog refresh logic if needed

---

## Important Code Patterns

### Context Dependency Injection
```python
# All pages receive AppContext
class SomePage(BasePage):
    def __init__(self, ctx: AppContext, theme_manager: ThemeManager):
        super().__init__(ctx, theme_manager)
        
        # Access services
        self.ctx.awards.get_all_awards()
        self.ctx.statistics.get_metrics()
        self.ctx.settings.get("theme_mode")
```

### Theme-Aware Widget Styling
```python
if self.theme_manager.is_dark:
    bg_color = "#353751"
else:
    bg_color = "#f5f5f5"
    
card.setStyleSheet(f"background-color: {bg_color}")
```

### Parent Navigation
```python
# Find parent window from child dialog
parent = self.parent()
while parent and not isinstance(parent, MainWindow):
    parent = parent.parent()
```

### Modal Dialog Pattern
```python
# Dialog shows and waits for result
if dialog.exec() == QDialog.Accepted:
    # Process result
    pass
```

---

## Common Issues & Solutions

### Issue: Window appears in screen corner instead of center
**Solution:** `MainWindow._center_window()` uses `QApplication.primaryScreen()` to center window

### Issue: Member data changes not showing in management page
**Solution:** Enhanced `_auto_refresh()` to check all 10 member fields. Dialog calls `management_page.refresh()` after save

### Issue: Pages loading causes startup freeze
**Solution:** Async loading with `QTimer.singleShot(100, _load_remaining_pages)` in main window

### Issue: Unused imports cluttering code
**Solution:** Regularly review imports and remove unused ones (recent cleanup removed 8 unused imports)

---

## Testing & Validation

### Syntax Validation
```bash
python -m py_compile src/
```

### Run Application
```bash
python -m src.main
```

### Debug Mode
```bash
python -m src.main --debug
```

---

## Recent Changes (December 2025)

1. **Window Centering:** Added `_center_window()` method
2. **README Rewrite:** Professional documentation following best practices template
3. **Import Cleanup:** Removed 8 unused imports across 4 files
4. **Member Refresh:** Enhanced detection to all 10 fields
5. **Dashboard Simplification:** Removed edit/delete operations from recent awards
6. **Code Quality:** Multi-phase optimization and refactoring

---

## Performance Characteristics

**Startup Time:** ~1.8 seconds total
- Bootstrap: ~0.16s
- MainWindow init: ~1.6s
- Home page: Immediate
- Other pages: Async (~100ms delay)

**Database:** SQLite with SQLAlchemy ORM
- Local storage: `data/awards.db`
- Transaction support: Yes
- Backup: Auto-backup configurable

---

## Key File References for Modifications

| Feature | Primary File | Secondary Files |
|---------|-------------|-----------------|
| Award data | `src/services/award_service.py` | `src/data/models.py` |
| Statistics | `src/services/statistics_service.py` | `src/ui/pages/dashboard_page.py` |
| Member mgmt | `src/ui/pages/management_page.py` | `src/data/models.py` |
| Award entry | `src/ui/pages/entry_page.py` | `src/services/award_service.py` |
| Award edit | `src/ui/pages/overview_page.py` | `src/services/award_service.py` |
| Settings | `src/ui/pages/settings_page.py` | `src/services/settings_service.py` |
| Themes | `src/ui/styled_theme.py` | `src/resources/styles/*.qss` |
| Navigation | `src/ui/main_window.py` | All page files |

---

## External Dependencies Map

```
PySide6 (GUI Framework)
├── QWidget, QMainWindow, QDialog, etc.
└── For: All UI components

QFluentWidgets (Fluent Design)
├── FluentWindow, NavigationInterface, etc.
└── For: Modern UI styling and components

SQLAlchemy (ORM)
├── Model definition, session management
└── For: Database operations

pandas (Data Processing)
└── For: CSV import/export, data analysis

APScheduler (Task Scheduling)
└── For: Auto-backup scheduling

loguru (Logging)
└── For: Application logging and debugging
```

---

## Best Practices for This Project

1. **Always use AppContext for service access** - Don't create service instances directly
2. **Use theme_manager.is_dark for theme checking** - Not hardcoded colors
3. **Implement _init_ui() in all pages** - Keep __init__ clean
4. **Use session_scope() for all DB operations** - Ensures transaction safety
5. **Add docstrings to all methods** - Especially in services
6. **Update management_page after member changes** - Use parent traversal pattern
7. **Test syntax after changes** - Run py_compile validation
8. **Keep member field count at 9** - Consistent across all pages

---

## Contact & Contribution

**Author:** RE-TikaRa
**Repository:** https://github.com/RE-TikaRa/Certificate-Management
**Issue Tracking:** GitHub Issues
**License:** MIT

---

## Quick Reference: Core Classes

```python
# Main window
from src.ui.main_window import MainWindow

# All pages
from src.ui.pages.dashboard_page import DashboardPage
from src.ui.pages.entry_page import EntryPage
from src.ui.pages.overview_page import OverviewPage
from src.ui.pages.management_page import ManagementPage
from src.ui.pages.recycle_page import RecyclePage
from src.ui.pages.settings_page import SettingsPage
from src.ui.pages.home_page import HomePage

# Services
from src.services.award_service import AwardService
from src.services.statistics_service import StatisticsService
from src.services.settings_service import SettingsService

# Models
from src.data.models import Award, TeamMember

# Theme
from src.ui.styled_theme import ThemeManager

# Database
from src.data.database import session_scope
```

---

**Last Updated:** 2025-12-03
**Version:** 1.0.0
