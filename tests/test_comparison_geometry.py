"""Pixel geometry and comparison-layout checks using native Qt widgets."""

import unittest
import tempfile
from pathlib import Path

from PyQt5.QtCore import QCoreApplication, QEvent, QPoint, QPointF, QSettings, Qt
from PyQt5.QtGui import QPixmap, QWheelEvent, QMouseEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton

from views.comparison_panel import SAILabel, SAIGridTab, ZoomCompareTab, ImageLabel, EPICompareTab
from views.main_window import MainWindow
from models.residual import generate_colorbar
from utils.image_utils import ndarray_to_qpixmap


def solid_pixmap(width, height):
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.green)
    return pixmap


class ComparisonGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # These widgets do not instantiate Appearance or access QSettings.
        self.widgets = []

    def widget(self, cls, width=400, height=300):
        widget = cls()
        widget.setAttribute(Qt.WA_DontShowOnScreen)
        widget.resize(width, height)
        widget.show()
        self.app.processEvents()
        self.widgets.append(widget)
        return widget

    def tearDown(self):
        for widget in self.widgets:
            widget.close()
            widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_fit_and_zoom_share_exact_image_coordinate_transform(self):
        label = self.widget(SAILabel)
        label.set_original_pixmap(solid_pixmap(200, 100))
        label.show_full()
        rect = label.display_rect()
        self.assertAlmostEqual(rect.width() / rect.height(), 2.0)
        self.assertAlmostEqual(rect.top(), 50.0)
        self.assertIsNone(label._map_to_orig(QPoint(200, 20)))
        self.assertEqual(label._map_to_orig(QPoint(200, 150)), (100, 50))
        label.apply_viewport(50, 25, 100, 50)
        self.assertEqual(label._map_to_orig(QPoint(200, 150)), (100, 50))
        self.assertEqual(label._map_to_orig(QPoint(0, 50)), (50, 25))

    def test_roi_cannot_start_in_letterbox_and_clamps_endpoint(self):
        label = self.widget(SAILabel)
        label.set_original_pixmap(solid_pixmap(200, 100))
        label.show_full()
        rects = []
        label.rect_drawn.connect(lambda *rect: rects.append(rect))
        QTest.mousePress(label, Qt.RightButton, pos=QPoint(20, 20))
        QTest.mouseRelease(label, Qt.RightButton, pos=QPoint(200, 150))
        self.assertEqual(rects, [])
        QTest.mousePress(label, Qt.RightButton, pos=QPoint(100, 100))
        QTest.mouseRelease(label, Qt.RightButton, pos=QPoint(400, 290))
        self.assertEqual(rects, [(50, 25, 150, 75)])

    def test_missing_frame_clears_visible_and_source_pixmaps(self):
        grid = self.widget(SAIGridTab)
        grid.set_methods(['A'])
        grid.set_sai('A', solid_pixmap(200, 100))
        grid.set_sai('A', None)
        label = grid.labels['A']._sai_label
        self.assertIsNone(label._original_pixmap)
        self.assertTrue(label.pixmap() is None or label.pixmap().isNull())
        self.assertIn('缺少', label.text())

    def test_reference_geometry_is_independent_of_last_method_update(self):
        grid = self.widget(SAIGridTab)
        grid.set_methods(['Ground_Truth', 'A', 'B'])
        grid.set_sai('Ground_Truth', solid_pixmap(200, 100))
        grid.set_sai('A', solid_pixmap(200, 100))
        grid.set_sai('B', solid_pixmap(100, 100))
        self.assertEqual((grid._img_w, grid._img_h), (200, 100))
        self.assertIn('尺寸不一致', grid.labels['B']._sai_label.text())
        self.assertIsNone(grid.labels['B']._sai_label._map_to_orig(QPoint(20, 20)))
        grid.set_sai('B', solid_pixmap(200, 100))
        self.assertEqual(grid.labels['B']._sai_label.text(), '')
        self.assertIsNotNone(grid.labels['B']._sai_label._original_pixmap)

    def test_sai_fits_container_without_extra_toolbar(self):
        grid = self.widget(SAIGridTab, 500, 400)
        grid.set_methods(['A'])
        grid.set_sai('A', solid_pixmap(2000, 1000))
        self.assertEqual(grid.findChildren(QPushButton), [])
        self.assertEqual(grid.layout().count(), 1)
        for width, height in ((500, 400), (340, 220)):
            with self.subTest(window=(width, height)):
                grid.resize(width, height)
                self.app.processEvents()
                label = grid.labels['A']._sai_label
                bounds = label.display_rect()
                scale = min(label.width() / 2000, label.height() / 1000)
                self.assertAlmostEqual(bounds.width(), 2000 * scale)
                self.assertAlmostEqual(bounds.height(), 1000 * scale)
                self.assertEqual(grid._zoom, 1.0)

    def test_wheel_anchors_to_image_and_ignores_letterbox(self):
        grid = self.widget(SAIGridTab, 500, 400)
        grid.set_methods(['A'])
        grid.set_sai('A', solid_pixmap(200, 100))
        self.app.processEvents()
        label = grid.labels['A']._sai_label
        bounds = label.display_rect()
        point = QPointF(bounds.left() + bounds.width() * .3,
                        bounds.top() + bounds.height() * .7)
        before = label._map_to_orig(point)
        event = QWheelEvent(point, point, QPoint(), QPoint(0, 120),
                            Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
        label.wheelEvent(event)
        after = label._map_to_orig(point)
        self.assertLessEqual(abs(after[0] - before[0]), 1)
        self.assertLessEqual(abs(after[1] - before[1]), 1)
        zoom = grid._zoom
        outside = QPointF(bounds.center().x(), bounds.top() / 2)
        label.wheelEvent(QWheelEvent(outside, outside, QPoint(), QPoint(0, 120),
                                     Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False))
        self.assertEqual(grid._zoom, zoom)

    def test_pan_uses_same_uniform_scale_on_both_axes(self):
        label = self.widget(SAILabel)
        label.set_original_pixmap(solid_pixmap(200, 100))
        label.apply_viewport(50, 25, 100, 50)
        deltas = []
        label.drag_delta.connect(lambda *value: deltas.append(value))
        QTest.mousePress(label, Qt.LeftButton, pos=QPoint(200, 150))
        label.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, QPointF(220, 170),
                                        Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        self.assertEqual(deltas, [(-5.0, -5.0)])

    def test_crop_and_residual_stay_in_one_method_cell_with_reference_slot(self):
        tab = self.widget(ZoomCompareTab, 900, 600)
        methods = ['Ground_Truth', 'A', 'Missing']
        image = solid_pixmap(80, 50)
        tab.update_zooms(methods, [dict(x=0, y=0, w=80, h=50, color=(255, 0, 0))],
                         {'Ground_Truth': [image], 'A': [image]}, {'A': [image]})
        cells = tab.container.findChildren(type(tab.container), 'methodComparison')
        self.assertEqual([cell.property('method') for cell in cells], methods)
        for cell in cells:
            self.assertIsNotNone(cell.findChild(ImageLabel, 'cropImage'))
            self.assertIsNotNone(cell.findChild(ImageLabel, 'residualImage'))
        self.assertIn('参考', cells[0].findChild(ImageLabel, 'residualImage').text())

    def test_epi_methods_share_one_scale(self):
        tab = self.widget(EPICompareTab, 900, 600)
        tab.update_epis(['A', 'B'], {})
        tab.update_epis(['A', 'B'], {'A': solid_pixmap(200, 10), 'B': solid_pixmap(200, 20)})
        a, b = [row[2] for row in tab._rows]
        self.assertEqual(a.width(), b.width())
        self.assertEqual(a.height() * 2, b.height())
        self.assertEqual(b.height(), tab.EPI_DISPLAY_HEIGHT)

    def test_epi_fits_resize_without_extra_toolbar(self):
        tab = self.widget(EPICompareTab, 1200, 600)
        self.assertEqual(tab.findChildren(QPushButton), [])
        self.assertEqual(tab.layout().count(), 1)
        tab.update_epis(['A', 'B'], {m: solid_pixmap(100, 5) for m in ['A', 'B']})
        QTest.qWait(160)
        wide_scale = tab._scale
        tab.resize(480, 420)
        QTest.qWait(160)
        self.assertLess(tab._scale, wide_scale)
        self.assertEqual(tab.scroll.horizontalScrollBar().maximum(), 0)
        narrow_scale = tab._scale
        tab.resize(1000, 600)
        QTest.qWait(160)
        self.assertGreater(tab._scale, narrow_scale)
        tab.resize(480, 420)
        QTest.qWait(160)
        self.assertEqual(tab.scroll.horizontalScrollBar().maximum(), 0)
        self.assertFalse(tab._resize_timer.isActive())

    def test_colorbar_stays_at_top_of_tall_single_column_group(self):
        tab = self.widget(ZoomCompareTab, 380, 460)
        methods = ['Ground_Truth', 'A', 'B', 'C', 'D', 'E']
        image = solid_pixmap(80, 80)
        tab.update_zooms(methods, [dict(x=0, y=0, w=80, h=80, color=(255, 0, 0))],
                         {m: [image] for m in methods},
                         {m: [image] for m in methods[1:]},
                         ndarray_to_qpixmap(generate_colorbar(1.0, height=600)))
        QTest.qWait(180)
        self.assertEqual(tab._last_cols, 1)
        colorbar = tab.container.findChild(ImageLabel, 'residualColorbar')
        self.assertEqual(colorbar.height(), 320)
        self.assertEqual(colorbar.pixmap().height(), 320)
        self.assertLess(colorbar.mapTo(tab.scroll.viewport(), QPoint()).y(), 100)
        self.assertLess(colorbar.mapTo(tab.scroll.viewport(), QPoint(0, colorbar.height())).y(),
                        tab.scroll.viewport().height())

    def test_long_method_names_do_not_widen_comparison_columns(self):
        name = 'Very_Long_Method_Name_With_Additional_Experiment_Settings_Seed_12345'
        methods = ['Ground_Truth', name]
        image = solid_pixmap(100, 100)
        sai = self.widget(SAIGridTab, 500, 400)
        sai.set_methods(methods)
        for method in methods:
            sai.set_sai(method, image)
        zoom = self.widget(ZoomCompareTab, 500, 600)
        zoom.update_zooms(methods, [dict(x=0, y=0, w=100, h=100, color=(255, 0, 0))],
                          {m: [image] for m in methods}, {name: [image]})
        QTest.qWait(180)
        for tab in (sai, zoom):
            with self.subTest(tab=type(tab).__name__):
                self.assertEqual(tab.scroll.horizontalScrollBar().maximum(), 0)
                titles = [label for label in tab.container.findChildren(QLabel)
                          if label.toolTip() == name]
                self.assertEqual(len(titles), 1)
                self.assertIn('…', titles[0].text())
                self.assertLessEqual(titles[0].fontMetrics().horizontalAdvance(titles[0].text()),
                                     titles[0].contentsRect().width())

    def test_epi_long_name_and_missing_rows_fit_a_narrow_viewport(self):
        name = 'Very_Long_Method_Name_With_Additional_Experiment_Settings_Seed_12345'
        tab = self.widget(EPICompareTab, 900, 400)
        for data in ({name: solid_pixmap(200, 10)}, {}):
            with self.subTest(all_missing=not data):
                tab.resize(900, 400)
                tab.update_epis([name, 'Missing'], data)
                QTest.qWait(160)
                tab.resize(320, 400)
                QTest.qWait(160)
                self.assertEqual(tab.scroll.horizontalScrollBar().maximum(), 0)
                title = tab._rows[0][1]
                self.assertEqual(title.toolTip(), name)
                self.assertIn('…', title.text())
                self.assertLessEqual(title.fontMetrics().horizontalAdvance(title.text()), title.width())

    def test_epi_names_keep_their_column_in_styled_main_window(self):
        methods = ['Ground_Truth', 'RIFE',
                   'Very_Long_Method_Name_With_Additional_Experiment_Settings_Seed_12345']
        with tempfile.TemporaryDirectory() as folder:
            settings = QSettings(str(Path(folder) / 'appearance.ini'), QSettings.IniFormat)
            window = MainWindow(settings=settings)
            self.widgets.append(window)
            window.setAttribute(Qt.WA_DontShowOnScreen)
            window.showNormal()
            panel = window.comparison_panel
            panel.set_methods(methods)
            panel.update_all_epis(methods, {m: solid_pixmap(100, 5) for m in methods})
            panel.tabs.setCurrentWidget(panel.epi_tab)
            for width in (1500, 800):
                with self.subTest(window_width=width):
                    window.resize(width, 700)
                    QTest.qWait(180)
                    for method, (row, name, image) in zip(methods, panel.epi_tab._rows):
                        self.assertTrue(name.isVisible())
                        self.assertEqual(name.width(), 118)
                        self.assertEqual(name.toolTip(), method)
                        if method in ('Ground_Truth', 'RIFE'):
                            self.assertEqual(name.text(), method)
                        self.assertEqual(image.x() - name.x(), 128)
                    self.assertEqual(panel.epi_tab.scroll.horizontalScrollBar().maximum(), 0)
            window.close()


if __name__ == '__main__':
    unittest.main()
