"""Desktop controls drawn the way macOS draws them, on native Qt widgets.

Qt style sheets can shape a control but cannot draw a glyph inside it, animate
anything, or paint outside a widget's own rect. So the chevrons, checkmarks,
radio dots, focus halos and the sliding segmented thumb are painted here.
Behaviour, focus and keyboard handling stay entirely native.
"""

from PyQt5.QtCore import (
    Qt, QEasingCurve, QPointF, QRectF, QVariantAnimation
)
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLineEdit,
    QListView, QPushButton, QRadioButton, QSpinBox, QStyle,
    QStyleOptionButton, QStyleOptionViewItem, QStyledItemDelegate, QWidget,
)

from views import theme

# Motion is short and decelerating, the way macOS eases its controls.
FOCUS_MS = 130
GLYPH_MS = 150
SLIDE_MS = 200
EASING = QEasingCurve.OutCubic

FOCUS_RING_STEPS = 3


def set_dark(dark):
    """Repoint every painted glyph at the appearance now on screen."""
    theme.set_active(dark)


_color = theme.color


def _animator(owner, slot, duration):
    animation = QVariantAnimation(owner)
    animation.setDuration(duration)
    animation.setEasingCurve(EASING)
    animation.valueChanged.connect(slot)
    return animation


def _lerp_rect(start, end, t):
    return QRectF(
        start.x() + (end.x() - start.x()) * t,
        start.y() + (end.y() - start.y()) * t,
        start.width() + (end.width() - start.width()) * t,
        start.height() + (end.height() - start.height()) * t,
    )


def paint_focus_ring(painter, rect, radius, strength=1.0):
    """macOS's focus halo.

    Qt clips a widget's painting to its own rect, so the halo is drawn just
    inside the edge — concentric hairlines fading inwards — rather than as the
    outer glow AppKit draws.
    """
    if strength <= 0.01 or rect.isEmpty():
        return
    accent = _color("accent")
    painter.setBrush(Qt.NoBrush)
    for step in range(FOCUS_RING_STEPS):
        alpha = int(165 * strength * (1.0 - step * 0.28))
        if alpha <= 0:
            continue
        ring = QColor(accent)
        ring.setAlpha(alpha)
        painter.setPen(QPen(ring, 1))
        inset = 0.5 + step
        corner = max(0.5, radius - step)
        painter.drawRoundedRect(
            rect.adjusted(inset, inset, -inset, -inset), corner, corner)


class _Focusable:
    """Mixin adding an eased focus halo to a widget that paints itself.

    Mixed in ahead of the Qt class so its focus events run first and then
    delegate through ``super()`` to the real widget.
    """

    def _init_focus(self, radius):
        self._focus_radius = radius
        self._focus = 1.0 if self.hasFocus() else 0.0
        self._focus_anim = _animator(self, self._on_focus_value, FOCUS_MS)

    def _on_focus_value(self, value):
        self._focus = float(value)
        self.update()

    def _fade_focus(self, target):
        self._focus_anim.stop()
        self._focus_anim.setStartValue(self._focus)
        self._focus_anim.setEndValue(float(target))
        self._focus_anim.start()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._fade_focus(1.0)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._fade_focus(0.0)

    def _paint_focus(self, painter, rect=None):
        paint_focus_ring(painter, rect if rect is not None else QRectF(self.rect()),
                         self._focus_radius, self._focus)


def _chevrons(painter, rect, color, gap=2.6):
    """The stacked up/down chevrons of a pop-up button or stepper."""
    painter.setPen(QPen(color, 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    cx = rect.center().x()
    cy = rect.center().y()
    reach = rect.width() * 0.26
    for direction in (-1, 1):
        tip = cy + direction * (gap + reach * 0.62)
        base = cy + direction * gap
        painter.drawPolyline(QPolygonF([
            QPointF(cx - reach, base),
            QPointF(cx, tip),
            QPointF(cx + reach, base),
        ]))


def _indicator_rect(widget, width, height):
    x = 7 if widget.layoutDirection() == Qt.RightToLeft else widget.width() - width - 7
    return QRectF(x, (widget.height() - height) / 2.0, width, height)


class PushButton(_Focusable, QPushButton):
    """Standard button plus the focus halo."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._init_focus(theme.RADIUS_CONTROL)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._focus <= 0.01:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._paint_focus(painter)


class TextField(_Focusable, QLineEdit):
    """Single-line field carrying the same halo as every other control."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_focus(theme.RADIUS_CONTROL)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._focus <= 0.01:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._paint_focus(painter)


class NumberBox(_Focusable, QSpinBox):
    """Numeric editor with a macOS-style stepper on its trailing edge."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_focus(theme.RADIUS_CONTROL)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = _indicator_rect(self, 17, 21)
        enabled = self.isEnabled()
        painter.setPen(QPen(_color("border" if enabled else "border_soft"), 1))
        painter.setBrush(_color("control_press" if enabled else "control"))
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 4.5, 4.5)
        _chevrons(painter, rect, _color("text_2" if enabled else "text_off"), 2.2)
        self._paint_focus(painter)


class SelectionBox(_Focusable, QComboBox):
    """Pop-up button with native selection behaviour.

    The chevron well is the same neutral bezel the stepper uses rather than
    AppKit's blue one, so every control in the sidebar reads as one family.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMaxVisibleItems(12)
        view = QListView()
        view.setFrameShape(QFrame.NoFrame)
        view.setSpacing(1)
        view.setTextElideMode(Qt.ElideMiddle)
        self.setView(view)
        self._round_popup()
        self.set_dark(False)
        self._init_focus(theme.RADIUS_CONTROL)

    def _round_popup(self):
        """Round the popup window itself, not just the list inside it.

        Qt wraps the view in a container that draws its own styled panel, so
        the rounded list corners were being framed by hard square ones.
        """
        container = self.view().window()
        container.setWindowFlags(
            container.windowFlags() | Qt.FramelessWindowHint
            | Qt.NoDropShadowWindowHint)
        container.setAttribute(Qt.WA_TranslucentBackground, True)
        if isinstance(container, QFrame):
            container.setFrameShape(QFrame.NoFrame)
        # Giving the container a rule of its own is what makes Qt's style-sheet
        # machinery stop painting a panel behind the rounded list.
        container.setStyleSheet(
            "QComboBoxPrivateContainer { background: transparent;"
            " border: none; }")

    def showPopup(self):
        # Qt restores the container's frame from the style on each show.
        self._round_popup()
        super().showPopup()

    def set_dark(self, dark):
        palette = theme.DARK if dark else theme.LIGHT
        self.view().setStyleSheet(f"""
            QListView {{ background: {palette['menu']}; color: {palette['text']};
                border: 1px solid {palette['border_soft']}; border-radius: 8px;
                padding: 4px; outline: none; }}
            QListView::item {{ min-height: 22px; padding: 3px 9px;
                border-radius: 5px; }}
            QListView::item:hover {{ background: {palette['track']}; }}
            QListView::item:selected {{ background: {palette['accent']};
                color: {palette['on_accent']}; }}
        """)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = _indicator_rect(self, 17, 21)
        enabled = self.isEnabled()
        painter.setPen(QPen(_color("border" if enabled else "border_soft"), 1))
        painter.setBrush(_color("control_press" if enabled else "control"))
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 4.5, 4.5)
        _chevrons(painter, rect, _color("text_2" if enabled else "text_off"), 2.2)
        self._paint_focus(painter)


def _draw_check(painter, rect, color, scale=1.0):
    painter.setPen(QPen(color, 1.9, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    points = QPolygonF([
        QPointF(x + w * 0.24, y + h * 0.52),
        QPointF(x + w * 0.43, y + h * 0.71),
        QPointF(x + w * 0.77, y + h * 0.30),
    ])
    if scale >= 0.999:
        painter.drawPolyline(points)
        return
    centre = rect.center()
    painter.save()
    painter.translate(centre)
    painter.scale(scale, scale)
    painter.translate(-centre)
    painter.drawPolyline(points)
    painter.restore()


class _GlyphToggle(_Focusable):
    """Shared behaviour for the checkbox and the radio: the box is style-sheet
    work, the glyph inside it is painted here and eased in on toggle."""

    def _init_glyph(self):
        self._init_focus(theme.RADIUS_CONTROL)
        self._glyph = 1.0 if self.isChecked() else 0.0
        self._glyph_anim = _animator(self, self._on_glyph_value, GLYPH_MS)
        self.toggled.connect(self._on_toggled)

    def _on_glyph_value(self, value):
        self._glyph = float(value)
        self.update()

    def _on_toggled(self, checked):
        self._glyph_anim.stop()
        self._glyph_anim.setStartValue(self._glyph)
        self._glyph_anim.setEndValue(1.0 if checked else 0.0)
        self._glyph_anim.start()

    def _indicator(self, element):
        option = QStyleOptionButton()
        self.initStyleOption(option)
        return self.style().subElementRect(element, option, self)

    def _paint_toggle_focus(self, painter, box):
        """Halo hugs the indicator when there is one, else the whole segment."""
        if self._focus <= 0.01:
            return
        if box.isEmpty() or box.width() < 6:
            self._paint_focus(painter)
        else:
            self._paint_focus(painter, QRectF(box).adjusted(-3, -3, 3, 3))


class CheckBox(_GlyphToggle, QCheckBox):
    """Checkbox whose tick is drawn rather than left to the platform style."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._init_glyph()

    def paintEvent(self, event):
        super().paintEvent(event)
        box = self._indicator(QStyle.SE_CheckBoxIndicator)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._paint_toggle_focus(painter, box)
        if box.isEmpty() or self._glyph <= 0.01:
            return
        tint = _color("on_accent" if self.isEnabled() else "control")
        tint.setAlphaF(min(1.0, self._glyph))
        if self.checkState() == Qt.PartiallyChecked:
            painter.setPen(QPen(tint, 1.9, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(
                QPointF(box.x() + box.width() * 0.26, box.center().y() + 0.5),
                QPointF(box.x() + box.width() * 0.74, box.center().y() + 0.5))
        else:
            _draw_check(painter, QRectF(box), tint, 0.7 + 0.3 * self._glyph)


class RadioButton(_GlyphToggle, QRadioButton):
    """Radio whose dot is drawn to match the checkbox weight."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._init_glyph()

    def paintEvent(self, event):
        super().paintEvent(event)
        box = self._indicator(QStyle.SE_RadioButtonIndicator)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._paint_toggle_focus(painter, box)
        if box.isEmpty() or box.width() < 6 or self._glyph <= 0.01:
            return
        tint = _color("on_accent" if self.isEnabled() else "control")
        tint.setAlphaF(min(1.0, self._glyph))
        painter.setPen(Qt.NoPen)
        painter.setBrush(tint)
        radius = box.width() * 0.19 * (0.6 + 0.4 * self._glyph)
        painter.drawEllipse(QRectF(box).center(), radius, radius)


class SegmentedControl(QWidget):
    """A recessed track whose thumb slides to the selected segment.

    Style sheets cannot animate, so the selected segment's white thumb is
    painted by this container — underneath the radios, which stay transparent —
    and interpolated between the old and new segment geometry.
    """

    def __init__(self, buttons, parent=None):
        super().__init__(parent)
        self.setObjectName("segmented")
        self.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self._buttons = list(buttons)
        for button in self._buttons:
            button.setProperty("segmented", True)
            button.setCursor(Qt.PointingHandCursor)
            button.toggled.connect(self._on_toggled)
            # Equal segments keep the thumb's target from moving when the
            # selected label changes weight.
            layout.addWidget(button, 1)
        self._from = QRectF()
        self._to = QRectF()
        self._progress = 1.0
        self._anim = _animator(self, self._on_progress, SLIDE_MS)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)

    def buttons(self):
        return tuple(self._buttons)

    def _checked_rect(self):
        for button in self._buttons:
            if button.isChecked():
                return QRectF(button.geometry())
        return QRectF()

    def _thumb_rect(self):
        if self._to.isEmpty():
            return QRectF()
        if self._from.isEmpty():
            return self._to
        return _lerp_rect(self._from, self._to, self._progress)

    def _on_toggled(self, checked):
        if not checked:
            return
        target = self._checked_rect()
        if target.isEmpty():
            return
        current = self._thumb_rect()
        if current.isEmpty() or not self.isVisible():
            self._snap()
            return
        self._anim.stop()
        self._from = current
        self._to = target
        self._progress = 0.0
        self._anim.start()

    def _on_progress(self, value):
        self._progress = float(value)
        self.update()

    def _snap(self):
        target = self._checked_rect()
        if target.isEmpty():
            return
        self._anim.stop()
        self._from = self._to = target
        self._progress = 1.0
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._snap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._snap()

    def paintEvent(self, event):
        super().paintEvent(event)      # the style sheet paints the track
        thumb = self._thumb_rect()
        if thumb.isEmpty():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(_color("border_soft"), 1))
        painter.setBrush(_color("thumb"))
        painter.drawRoundedRect(
            thumb.adjusted(0.5, 0.5, -0.5, -0.5),
            theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)


class CheckListDelegate(QStyledItemDelegate):
    """Adds the tick to list check indicators.

    The rounded blue box itself comes from ``QListWidget::indicator`` in the
    style sheet, so item layout and hit-testing stay exactly as Qt computes
    them; only the glyph, which style sheets cannot express, is painted here.
    """

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        if not opt.features & QStyleOptionViewItem.HasCheckIndicator:
            return
        if opt.checkState != Qt.Checked:
            return
        widget = opt.widget
        style = widget.style() if widget else QApplication.style()
        box = style.subElementRect(
            QStyle.SE_ItemViewItemCheckIndicator, opt, widget)
        if box.isEmpty():
            return
        side = min(box.width(), box.height())
        square = QRectF(box.x(), box.center().y() - side / 2.0, side, side)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        _draw_check(painter, square, _color("on_accent"))
        painter.restore()
