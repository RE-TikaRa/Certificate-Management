from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGraphicsDropShadowEffect,
    QHeaderView,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import CardWidget, TableItemDelegate, TableView, isDarkTheme

CARD_RADIUS = 12


class StyledCardWidget(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBorderRadius(CARD_RADIUS)

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        if isDarkTheme():
            painter.setPen(QColor(148, 163, 184, 46))
        else:
            painter.setPen(QColor(148, 163, 184, 89))
        painter.setBrush(self.backgroundColor)
        radius = self.getBorderRadius()
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), radius, radius)


class CenterAlignDelegate(TableItemDelegate):
    def initStyleOption(self, option, index) -> None:
        super().initStyleOption(option, index)
        opt = cast(Any, option)
        opt.displayAlignment = Qt.AlignmentFlag.AlignCenter


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


def create_card(shadow: bool = False) -> tuple[StyledCardWidget, QVBoxLayout]:
    card = StyledCardWidget()
    card.setProperty("card", True)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(12)
    if shadow:  # 模糊效果会导致性能下降很多，请不要使用
        effect = QGraphicsDropShadowEffect(card)
        effect.setBlurRadius(28)
        effect.setOffset(0, 8)
        effect.setColor(QColor(15, 26, 66, 20))
        card.setGraphicsEffect(effect)
    return card, layout


def apply_table_style(table: TableView) -> None:
    table.setAlternatingRowColors(False)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setShowGrid(False)
    table.setItemDelegate(CenterAlignDelegate(table))
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(44)
    table.verticalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
    header = table.horizontalHeader()
    # 根据窗口宽度自动调整列宽，最后一列自动拉伸
    header.setStretchLastSection(True)
    header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    header.setHighlightSections(False)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
    header.setMinimumHeight(36)
