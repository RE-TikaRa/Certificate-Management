from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout
from qfluentwidgets import (
    BodyLabel,
    LineEdit,
    MaskDialogBase,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
)


class FluentProgressDialog(MaskDialogBase):
    def __init__(
        self,
        text: str = "",
        cancel_text: str = "",
        minimum: int = 0,
        maximum: int = 0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._auto_close = True
        self._minimum_duration = 0
        self._cancel_btn: PushButton | None = None

        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self._label = BodyLabel(text)
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self._label)

        self._progress = ProgressBar(self.widget)
        self._progress.setRange(minimum, maximum)
        layout.addWidget(self._progress)

        if cancel_text:
            btn_row = QHBoxLayout()
            btn_row.addStretch()
            self._cancel_btn = PushButton(cancel_text)
            self._cancel_btn.clicked.connect(self.reject)
            btn_row.addWidget(self._cancel_btn)
            layout.addLayout(btn_row)

    def setLabelText(self, text: str) -> None:
        self._label.setText(text)

    def setRange(self, minimum: int, maximum: int) -> None:
        self._progress.setRange(minimum, maximum)

    def setValue(self, value: int) -> None:
        self._progress.setValue(value)

    def setCancelButton(self, button) -> None:
        if button is None and self._cancel_btn is not None:
            self._cancel_btn.setDisabled(True)
            self._cancel_btn.hide()

    def setAutoClose(self, value: bool) -> None:
        self._auto_close = value

    def setMinimumDuration(self, duration: int) -> None:
        self._minimum_duration = duration


class TextInputDialog(MaskDialogBase):
    def __init__(
        self,
        parent,
        *,
        title: str,
        label: str,
        text: str = "",
        placeholder: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)

        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self._label = BodyLabel(label)
        layout.addWidget(self._label)

        self._input = LineEdit()
        if placeholder:
            self._input.setPlaceholderText(placeholder)
        if text:
            self._input.setText(text)
        layout.addWidget(self._input)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = PushButton("取消")
        self._ok_btn = PrimaryPushButton("确定")
        self._cancel_btn.clicked.connect(self.reject)
        self._ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._ok_btn)
        layout.addLayout(btn_row)

    def text(self) -> str:
        return self._input.text()

    @staticmethod
    def get_text(parent, title: str, label: str, text: str = "", placeholder: str | None = None) -> tuple[str, bool]:
        dialog = TextInputDialog(parent, title=title, label=label, text=text, placeholder=placeholder)
        result = dialog.exec()
        return dialog.text(), result == dialog.DialogCode.Accepted
