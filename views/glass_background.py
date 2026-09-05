"""Soft ambient backdrop for the application's translucent panels."""

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QColor, QPainter, QRadialGradient
from PyQt5.QtWidgets import QWidget


class GlassBackground(QWidget):
    dark = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#151922" if self.dark else "#e9edf5"))
        # Broad gradients provide diffuse light without blurring image content.
        for x, y, radius, color in [
            (0.02, 0.12, 0.70, "#203a57" if self.dark else "#b6d5f4"),
            (0.95, 0.05, 0.65, "#37304e" if self.dark else "#d3c9ed"),
            (0.22, 1.00, 0.60, "#1b3b40" if self.dark else "#c0e0de"),
        ]:
            gradient = QRadialGradient(
                QPointF(self.width() * x, self.height() * y),
                max(self.width(), self.height()) * radius,
            )
            gradient.setColorAt(0, QColor(color))
            transparent = QColor(color)
            transparent.setAlpha(0)
            gradient.setColorAt(1, transparent)
            painter.fillRect(self.rect(), gradient)
