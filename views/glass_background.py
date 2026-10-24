"""Opaque neutral backdrop for the comparison workspace."""

from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QWidget

from views.theme import BACKDROP


class GlassBackground(QWidget):
    dark = False

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        painter.fillRect(rect, QColor(BACKDROP[bool(self.dark)]))
