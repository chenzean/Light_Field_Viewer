"""Desktop controls with consistent appearance and native Qt interaction."""

from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import QComboBox, QListView, QFrame, QSpinBox


def _paint_indicator(widget):
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.Antialiasing)
    x = 9 if widget.layoutDirection() == Qt.RightToLeft else widget.width() - 27
    y = (widget.height() - 18) / 2
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#007aff" if widget.isEnabled() else "#c7c7cc"))
    painter.drawRoundedRect(QRectF(x, y, 18, 18), 5, 5)
    painter.setPen(QPen(QColor("white"), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    for offset, direction in [(6, -1), (12, 1)]:
        painter.drawPolyline(QPolygonF([
            QPointF(x + 6, y + offset),
            QPointF(x + 9, y + offset + direction * 2.5),
            QPointF(x + 12, y + offset),
        ]))


class NumberBox(QSpinBox):
    """Numeric editor retaining native step buttons with a shared indicator."""

    def paintEvent(self, event):
        super().paintEvent(event)
        _paint_indicator(self)


class SelectionBox(QComboBox):
    """Keep standard selection and keyboard behavior with a custom indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMaxVisibleItems(10)
        view = QListView()
        view.setFrameShape(QFrame.NoFrame)
        view.setSpacing(2)
        view.setTextElideMode(Qt.ElideMiddle)
        view.setStyleSheet("""
            QListView { background: #ffffff; color: #242426;
                border: 1px solid #d8d8dc; border-radius: 8px;
                padding: 5px; outline: none; }
            QListView::item { min-height: 24px; padding: 4px 10px;
                border-radius: 5px; }
            QListView::item:selected { background: #007aff; color: white; }
            QListView::item:hover { background: #e8f1ff; color: #242426; }
            QListView::item:selected:hover { background: #007aff; color: white; }
        """)
        self.setView(view)
        self._light_popup_style = view.styleSheet()

    def set_dark(self, dark):
        style = self._light_popup_style
        if dark:
            style = (style.replace("#ffffff", "#292e39")
                     .replace("#242426", "#eef0f5")
                     .replace("#d8d8dc", "#505969")
                     .replace("#e8f1ff", "#394c66"))
        self.view().setStyleSheet(style)

    def paintEvent(self, event):
        super().paintEvent(event)
        _paint_indicator(self)
