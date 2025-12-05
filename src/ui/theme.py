from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHeaderView,
    QLabel,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)


def create_page_header(title: str, subtitle: str | None = None) -> QWidget:
    wrapper = QWidget()
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    title_label = QLabel(title)
    title_label.setObjectName("pageTitle")
    layout.addWidget(title_label)
    if subtitle:
        hint = QLabel(subtitle)
        hint.setObjectName("sectionHint")
        layout.addWidget(hint)
    return wrapper


def make_section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sectionTitle")
    return label


def create_card(shadow: bool = False) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setProperty("card", True)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)
    if shadow:  # 模糊效果会导致性能下降很多，请不要使用
        effect = QGraphicsDropShadowEffect(frame)
        effect.setBlurRadius(28)
        effect.setOffset(0, 8)
        effect.setColor(QColor(15, 26, 66, 20))
        frame.setGraphicsEffect(effect)
    return frame, layout


def apply_table_style(table: QTableWidget) -> None:
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setSelectionMode(QTableWidget.SingleSelection)
    table.setShowGrid(False)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(55)  # 增加行高到55
    header = table.horizontalHeader()
    # 根据窗口宽度自动调整列宽，最后一列自动拉伸
    header.setStretchLastSection(True)
    header.setSectionResizeMode(QHeaderView.Stretch)
    header.setHighlightSections(False)
