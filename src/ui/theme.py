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

PAGE_STYLE = """
QWidget#pageRoot {
    background-color: #f4f6fb;
}
QLabel#pageTitle {
    font-size: 22px;
    font-weight: 600;
    color: #1f2c65;
}
QLabel#sectionTitle {
    font-size: 16px;
    font-weight: 600;
    color: #5a6cf3;
    margin-bottom: 8px;
}
QLabel#sectionHint {
    color: #7c84a6;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid rgba(90, 108, 243, 0.15);
    border-radius: 12px;
    margin-top: 16px;
    padding: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #465087;
    font-weight: 600;
}
QFrame[card="true"] {
    background-color: rgba(255, 255, 255, 0.96);
    border-radius: 20px;
    border: 1px solid rgba(90, 108, 243, 0.06);
}
QFrame[metricTile="true"] {
    border-radius: 18px;
    padding: 18px;
    color: #ffffff;
}
QFrame[metricTile="true"][accent="violet"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #a071ff, stop:1 #7b6cff);
}
QFrame[metricTile="true"][accent="blue"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5a80f3, stop:1 #4ac6ff);
}
QFrame[metricTile="true"][accent="gold"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffb347, stop:1 #ffcc33);
}
QFrame[metricTile="true"][accent="green"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3ec8a0, stop:1 #45dd8e);
}
QLabel[metricValue="true"] {
    font-size: 28px;
    font-weight: 700;
    color: #ffffff;
}
QLabel[metricCaption="true"] {
    color: rgba(255, 255, 255, 0.85);
    font-size: 13px;
}
QLabel[dataChip="true"] {
    background: rgba(90, 108, 243, 0.1);
    border-radius: 14px;
    padding: 4px 12px;
    color: #4a5096;
    font-size: 12px;
}
QLineEdit,
QTextEdit,
QPlainTextEdit,
QComboBox,
QDateEdit,
QSpinBox,
QDoubleSpinBox {
    min-height: 42px;
    border: 1px solid rgba(88, 99, 135, 0.24);
    border-radius: 14px;
    padding: 0 14px;
    background: rgba(255, 255, 255, 0.98);
    font-size: 14px;
}
QLineEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QComboBox:focus,
QDateEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus {
    border: 1px solid #5a6cf3;
    outline: none;
}
QLabel[inputField="true"] {
    border: 1px dashed rgba(88, 99, 135, 0.35);
    border-radius: 14px;
    min-height: 42px;
    padding: 10px 16px;
    color: #5a5f7a;
    background: rgba(255, 255, 255, 0.96);
}
QTextEdit {
    min-height: 110px;
    padding: 12px;
}
QListWidget {
    border: 1px solid rgba(114, 122, 161, 0.18);
    border-radius: 14px;
    padding: 8px;
    background: rgba(255, 255, 255, 0.97);
}
QComboBox::drop-down,
QDateEdit::drop-down {
    border: none;
    width: 28px;
}
QCheckBox {
    spacing: 10px;
    font-size: 14px;
    color: #2a2f55;
}
QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 6px;
    border: 1px solid rgba(88, 99, 135, 0.35);
    background: rgba(255, 255, 255, 0.95);
}
QCheckBox::indicator:hover {
    border-color: #5a6cf3;
}
QCheckBox::indicator:checked {
    border: 1px solid #4f7df5;
    background: #4f7df5;
    image: url(:/qt-project.org/styles/commonstyle/images/checklistindicator.png);
}
QTableWidget {
    background: transparent;
    border: none;
    gridline-color: transparent;
    alternate-background-color: #f1f4ff;
    selection-background-color: rgba(90, 108, 243, 0.18);
    selection-color: #0f1a42;
}
QHeaderView::section {
    background-color: rgba(90, 108, 243, 0.08);
    color: #2a2f55;
    border: none;
    padding: 8px;
    font-weight: 600;
}
"""


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


def create_card(shadow: bool = True) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setProperty("card", True)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)
    if shadow:
        effect = QGraphicsDropShadowEffect(frame)
        effect.setBlurRadius(40)
        effect.setOffset(0, 16)
        effect.setColor(QColor(15, 26, 66, 35))
        frame.setGraphicsEffect(effect)
    return frame, layout


def apply_table_style(table: QTableWidget) -> None:
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setSelectionMode(QTableWidget.SingleSelection)
    table.setShowGrid(False)
    table.verticalHeader().setVisible(False)
    header = table.horizontalHeader()
    header.setStretchLastSection(True)
    header.setSectionResizeMode(QHeaderView.ResizeToContents)
    header.setHighlightSections(False)
