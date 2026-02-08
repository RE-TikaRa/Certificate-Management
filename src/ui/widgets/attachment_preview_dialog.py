from __future__ import annotations

from contextlib import suppress
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, InfoBar, MaskDialogBase, PrimaryPushButton, PushButton, ScrollArea, SpinBox

from ..theme import create_page_header


class AttachmentPreviewDialog(MaskDialogBase):
    def __init__(self, parent, *, path: Path) -> None:
        super().__init__(parent)
        self._path = Path(path)
        self._doc = None
        self._page_index = 0
        self._page_count = 1
        self._zoom = 1.0
        self._is_pdf = self._path.suffix.lower() == ".pdf"
        self.setWindowTitle("附件预览")
        self.widget.setMinimumWidth(900)
        self.widget.setMinimumHeight(640)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header = create_page_header("附件预览", self._path.name)
        layout.addWidget(header)

        control_row = QHBoxLayout()
        control_row.setSpacing(8)

        self._page_label = BodyLabel("页码")
        self._page_spin = SpinBox()
        self._page_spin.setRange(1, 1)
        self._page_spin.valueChanged.connect(self._on_page_changed)
        self._page_label.setVisible(self._is_pdf)
        self._page_spin.setVisible(self._is_pdf)
        control_row.addWidget(self._page_label)
        control_row.addWidget(self._page_spin)

        self._zoom_label = BodyLabel("100%")
        zoom_out = PushButton("缩小")
        zoom_in = PushButton("放大")
        zoom_reset = PushButton("重置")
        zoom_out.clicked.connect(lambda: self._set_zoom(self._zoom - 0.2))
        zoom_in.clicked.connect(lambda: self._set_zoom(self._zoom + 0.2))
        zoom_reset.clicked.connect(lambda: self._set_zoom(1.0))

        control_row.addStretch()
        control_row.addWidget(self._zoom_label)
        control_row.addWidget(zoom_out)
        control_row.addWidget(zoom_in)
        control_row.addWidget(zoom_reset)
        layout.addLayout(control_row)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(self._image_label, alignment=Qt.AlignmentFlag.AlignCenter)

        scroll = ScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        action_row = QHBoxLayout()
        action_row.addStretch()
        open_btn = PrimaryPushButton("打开文件")
        close_btn = PushButton("关闭")
        open_btn.clicked.connect(self._open_file)
        close_btn.clicked.connect(self.close)
        action_row.addWidget(open_btn)
        action_row.addWidget(close_btn)
        layout.addLayout(action_row)

    def _load(self) -> None:
        if not self._path.exists():
            InfoBar.error("附件预览", "文件不存在，无法预览", parent=self.window())
            self.close()
            return
        if self._is_pdf:
            try:
                import fitz
            except Exception as exc:
                InfoBar.error("附件预览", f"缺少 PDF 预览依赖：{exc}", parent=self.window())
                self.close()
                return
            try:
                self._doc = fitz.open(self._path)
            except Exception as exc:
                InfoBar.error("附件预览", f"PDF 打开失败：{exc}", parent=self.window())
                self.close()
                return
            self._page_count = max(1, int(self._doc.page_count))
            self._page_spin.setRange(1, self._page_count)
            self._page_spin.setValue(1)
            self._render_pdf()
            return
        self._render_image()

    def _render_image(self) -> None:
        pixmap = QPixmap(str(self._path))
        if pixmap.isNull():
            InfoBar.error("附件预览", "图片加载失败", parent=self.window())
            return
        zoom = max(0.2, min(4.0, self._zoom))
        self._zoom = zoom
        width = max(1, int(pixmap.width() * zoom))
        height = max(1, int(pixmap.height() * zoom))
        scaled = pixmap.scaled(
            width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self._image_label.setPixmap(scaled)
        self._zoom_label.setText(f"{int(self._zoom * 100)}%")

    def _render_pdf(self) -> None:
        if self._doc is None:
            return
        try:
            import fitz
        except Exception:
            return
        zoom = max(0.2, min(4.0, self._zoom))
        self._zoom = zoom
        page = self._doc.load_page(self._page_index)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(image.copy())
        self._image_label.setPixmap(pixmap)
        self._zoom_label.setText(f"{int(self._zoom * 100)}%")

    def _set_zoom(self, value: float) -> None:
        self._zoom = max(0.2, min(4.0, value))
        if self._is_pdf:
            self._render_pdf()
        else:
            self._render_image()

    def _on_page_changed(self, value: int) -> None:
        if not self._is_pdf:
            return
        self._page_index = max(0, min(self._page_count - 1, int(value) - 1))
        self._render_pdf()

    def _open_file(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._path)))

    def closeEvent(self, event) -> None:
        if self._doc is not None:
            with suppress(Exception):
                self._doc.close()
            self._doc = None
        super().closeEvent(event)
