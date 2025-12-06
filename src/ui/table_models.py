from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt


class ObjectTableModel(QAbstractTableModel):
    """Reusable table model that maps objects to columns via accessor callables."""

    def __init__(self, headers: Sequence[str], accessors: Sequence[Callable[[Any], Any]], parent=None):
        super().__init__(parent)
        self._headers = list(headers)
        self._accessors = list(accessors)
        self._objects: list[Any] = []

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._objects)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._headers)

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid():
            return None
        if role in (int(Qt.ItemDataRole.DisplayRole), int(Qt.ItemDataRole.EditRole)):
            obj = self._objects[index.row()]
            value = self._accessors[index.column()](obj)
            return "" if value is None else str(value)
        if role == int(Qt.ItemDataRole.TextAlignmentRole):
            return int(Qt.AlignmentFlag.AlignCenter)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if role != int(Qt.ItemDataRole.DisplayRole):
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self._headers):
            return self._headers[section]
        return super().headerData(section, orientation, role)

    def set_objects(self, objects: Sequence[Any]) -> None:
        self.beginResetModel()
        self._objects = list(objects)
        self.endResetModel()

    def object_at(self, row: int) -> Any:
        return self._objects[row]


class MembersTableModel(ObjectTableModel):
    """Members table model with an extra action column."""

    def __init__(self, parent=None):
        headers = ["姓名", "性别", "电话", "学院", "班级", "操作"]
        accessors = [
            lambda m: m.name or "",
            lambda m: m.gender or "",
            lambda m: m.phone or "",
            lambda m: m.college or "",
            lambda m: m.class_name or "",
            lambda m: "详情",
        ]
        super().__init__(headers, accessors, parent)


class AttachmentTableModel(ObjectTableModel):
    """Attachment table model supporting name/hash/size columns."""

    def __init__(self, parent=None):
        headers = ["序号", "附件名", "MD5", "大小", "操作"]
        accessors = [
            lambda r: r["index"],
            lambda r: r["name"],
            lambda r: r["md5"],
            lambda r: r["size"],
            lambda r: "",
        ]
        super().__init__(headers, accessors, parent)
