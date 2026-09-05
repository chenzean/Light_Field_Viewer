"""Neutral window backdrop sampled by the translucent sidebar above it.

macOS never tints app chrome with saturated colour, so this stays a near-grey
wash: a flat base, a soft top-down sheen and two very faint pools of light that
keep the translucent panels from looking like flat paint.
"""

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QColor, QLinearGradient, QPainter, QRadialGradient
from PyQt5.QtWidgets import QWidget

from views.theme import BACKDROP


class GlassBackground(QWidget):
    dark = False

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        painter.fillRect(rect, QColor(BACKDROP[bool(self.dark)]))

        # Top-down sheen, a couple of percent of luminance either way.
        sheen = QLinearGradient(QPointF(0, 0), QPointF(0, rect.height()))
        top = QColor(255, 255, 255, 26 if self.dark else 42)
        bottom = QColor(0, 0, 0, 20 if self.dark else 12)
        sheen.setColorAt(0, top)
        sheen.setColorAt(1, bottom)
        painter.fillRect(rect, sheen)

        # Barely-there cool light so glass panels have something to sample.
        reach = max(rect.width(), rect.height())
        for x, y, radius, color in [
            (0.08, 0.00, 0.85, QColor(150, 175, 210, 30 if self.dark else 34)),
            (0.98, 0.90, 0.80, QColor(160, 160, 178, 24 if self.dark else 28)),
        ]:
            gradient = QRadialGradient(
                QPointF(rect.width() * x, rect.height() * y), reach * radius)
            gradient.setColorAt(0, color)
            faded = QColor(color)
            faded.setAlpha(0)
            gradient.setColorAt(1, faded)
            painter.fillRect(rect, gradient)
