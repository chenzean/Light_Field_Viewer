"""Exercise data changes through the real controller and Qt widgets."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
from PyQt5.QtCore import QCoreApplication, QEvent, QSettings, Qt
from PyQt5.QtWidgets import QApplication

from controllers.app_controller import AppController
from views.main_window import MainWindow


class ControllerIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'data'
        settings = QSettings(str(Path(self.temp.name) / 'appearance.ini'), QSettings.IniFormat)
        self.window = MainWindow(settings)
        self.window.setAttribute(Qt.WA_DontShowOnScreen)
        self.window.showNormal()
        self.window.resize(1280, 900)
        self.controller = AppController(self.window)
        self.app.processEvents()

    def tearDown(self):
        self.controller._refresh_timer.stop()
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.temp.cleanup()

    def image(self, method, frame, value, size=(24, 32), root=None, uv=(1, 1)):
        path = (root or self.root) / method / 'Scene' / frame / f'{uv[0]}_{uv[1]}.png'
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.full((*size, 3), value, dtype=np.uint8)).save(path)
        return path

    def refresh(self):
        self.controller._refresh_timer.stop()
        self.controller._do_refresh()
        self.app.processEvents()

    def load(self):
        self.controller.on_data_root_changed(str(self.root))
        self.refresh()

    def test_missing_frame_clears_image_and_displays_reason(self):
        for frame in ('frame_1', 'frame_2'):
            self.image('Ground_Truth', frame, 0)
        self.image('A', 'frame_1', 50)
        self.load()
        label = self.window.comparison_panel.sai_tab.labels['A']._sai_label
        self.assertIsNotNone(label._original_pixmap)
        self.window.settings_panel.combo_frame.setCurrentIndex(1)
        self.refresh()
        self.assertIsNone(label._original_pixmap)
        self.assertIn('A', self.window.data_notice.text())
        self.assertIn('缺少', self.window.data_notice.text())

    def test_refresh_reads_replaced_files_and_preserves_selection(self):
        self.image('Ground_Truth', 'frame_1', 0)
        self.image('A', 'frame_1', 50)
        self.load()
        self.assertEqual(int(self.controller._load_sai('A')[0, 0, 0]), 50)
        self.image('A', 'frame_1', 80)
        self.controller.reload_data()
        self.refresh()
        self.assertEqual(int(self.controller._load_sai('A')[0, 0, 0]), 80)
        self.assertEqual(self.controller.current_scene, 'Scene')

    def test_alignment_change_invalidates_images(self):
        for frame in ('frame_1', 'frame_2', 'frame_3'):
            self.image('Ground_Truth', frame, 0)
        self.image('A', 'frame_1', 10)
        self.image('A', 'frame_3', 30)
        self.load()
        panel = self.window.settings_panel
        panel.combo_frame.setCurrentIndex(1)
        self.refresh()
        self.assertIsNone(self.controller._load_sai('A'))
        panel.combo_alignment.setCurrentIndex(1)
        panel.combo_frame.setCurrentIndex(1)
        self.refresh()
        self.assertEqual(int(self.controller._load_sai('A')[0, 0, 0]), 30)
        self.assertIn('按位置', self.window.data_notice.text())

    def test_residual_shape_error_is_visible_and_not_a_false_map(self):
        self.image('Ground_Truth', 'frame_1', 0)
        self.image('A', 'frame_1', 10, size=(25, 32))
        self.load()
        self.controller.rects = [dict(x=1, y=1, w=8, h=8, color=(255, 0, 0), thickness=1)]
        self.window.settings_panel.chk_residual.setChecked(True)
        self.window.comparison_panel.tabs.setCurrentIndex(1)
        self.refresh()
        self.assertIn('尺寸', self.window.data_notice.text())
        self.assertNotIn('A', self.window.comparison_panel.zoom_tab._residual_data)

    def test_empty_directory_removes_previous_scene_and_disables_export(self):
        self.image('Ground_Truth', 'frame_1', 0)
        self.load()
        empty = Path(self.temp.name) / 'empty'
        empty.mkdir()
        self.controller.on_data_root_changed(str(empty))
        self.refresh()
        self.assertEqual(self.controller.current_scene, '')
        self.assertFalse(self.window.export_button.isEnabled())
        self.assertTrue(self.window.data_notice.isVisible())

    def test_invalid_epi_crop_is_reported_instead_of_showing_last_column(self):
        self.image('Ground_Truth', 'frame_1', 0)
        self.load()
        panel = self.window.settings_panel
        panel.spin_epi_spatial.setValue(10)
        panel.chk_epi.setChecked(True)
        self.window.comparison_panel.tabs.setCurrentIndex(2)
        self.refresh()
        self.assertIn('裁剪', self.window.data_notice.text())

    def test_roi_without_intersection_has_specific_feedback(self):
        self.image('Ground_Truth', 'frame_1', 0)
        self.load()
        self.controller.rects = [dict(x=200, y=100, w=8, h=8, color=(255, 0, 0), thickness=1)]
        self.window.comparison_panel.tabs.setCurrentIndex(1)
        self.refresh()
        self.assertIn('选区 1', self.window.data_notice.text())
        self.assertIn('没有交集', self.window.data_notice.text())

    def test_changing_dataset_synchronizes_clamped_view_controls(self):
        self.image('Ground_Truth', 'frame_1', 0)
        self.image('Ground_Truth', 'frame_1', 0, uv=(2, 2))
        self.load()
        self.window.settings_panel.spin_u.setValue(2)
        other = Path(self.temp.name) / 'other'
        self.image('Ground_Truth', 'frame_1', 0, root=other)
        self.controller.on_data_root_changed(str(other))
        self.refresh()
        self.assertEqual(self.controller.current_u, 1)
        self.assertIsNotNone(self.controller._load_sai('Ground_Truth'))


if __name__ == '__main__':
    unittest.main()
