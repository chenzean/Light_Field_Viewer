"""Regression checks for the reorganized desktop controls."""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from PyQt5.QtCore import Qt, QCoreApplication, QEvent, QSettings, QPoint
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest

from views.main_window import MainWindow
from views.appearance import Appearance


class WorkspaceLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = QSettings(str(Path(self.temp.name) / "appearance.ini"), QSettings.IniFormat)
        self.window = MainWindow(settings=self.settings)
        self.window.setAttribute(Qt.WA_DontShowOnScreen)
        self.window.showNormal()
        self.window.resize(1280, 900)
        self.app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.temp.cleanup()

    def test_appearance_persistence_and_explicit_override(self):
        with patch("views.appearance.system_is_dark", return_value=False):
            self.window.appearance.set_mode("dark")
            self.assertTrue(self.window.centralWidget().dark)
            self.window.appearance.refresh()
            self.assertTrue(self.window.appearance.dark)
            restored = Appearance(settings=self.settings)
            self.assertEqual(restored.mode, "dark")
            self.assertTrue(restored.dark)
            self.window.appearance.set_mode("light")
            self.assertFalse(self.window.centralWidget().dark)

    def test_follow_system_changes(self):
        with patch("views.appearance.system_is_dark", return_value=False):
            self.window.appearance.set_mode("system")
            self.assertFalse(self.window.appearance.dark)
        with patch("views.appearance.system_is_dark", return_value=True):
            self.window.appearance.refresh()
            self.assertTrue(self.window.centralWidget().dark)
        with patch("views.appearance.system_is_dark", return_value=False):
            self.window.appearance.refresh()
            self.assertFalse(self.window.centralWidget().dark)

    def test_reparented_controls_and_mode_switches(self):
        panel = self.window.settings_panel
        self.assertEqual(panel.sections.count(), 3)
        panel.sections.setCurrentIndex(1)
        panel.radio_mli.click()
        self.assertTrue(panel.grp_epi.isHidden())
        panel.radio_sai.click()
        self.assertFalse(panel.grp_epi.isHidden())
        panel.radio_image.click()
        self.assertTrue(panel.hbox_frame_widget.isHidden())
        events = []
        panel.angular_resolution_changed.connect(lambda u, v: events.append((u, v)))
        panel.spin_u_max.setValue(7)
        self.assertEqual(events[-1][0], 7)
        self.assertEqual(panel.spin_u.maximum(), 7)

    def test_toolbar_actions_and_sidebar(self):
        events = []
        self.window.settings_panel.export_requested.connect(lambda: events.append("export"))
        self.window.settings_panel.refresh_requested.connect(lambda: events.append("refresh"))
        self.window.export_button.click()
        self.window.refresh_button.click()
        self.assertEqual(events, ["export", "refresh"])
        self.window.sidebar_button.click()
        self.assertTrue(self.window.settings_panel.isHidden())
        self.window.sidebar_button.click()
        self.assertFalse(self.window.settings_panel.isHidden())

    def test_dropdown_keyboard_selection(self):
        panel = self.window.settings_panel
        panel.set_scenes(["Scene A", "Scene B"])
        events = []
        panel.scene_changed.connect(events.append)
        panel.combo_scene.setFocus()
        QTest.keyClick(panel.combo_scene, Qt.Key_Down)
        self.assertEqual(panel.combo_scene.currentText(), "Scene B")
        self.assertEqual(events, ["Scene B"])

    def test_numeric_step_buttons(self):
        spin = self.window.settings_panel.spin_u_max
        before = spin.value()
        QTest.mouseClick(spin, Qt.LeftButton, pos=QPoint(spin.width() - 18, 10))
        self.assertEqual(spin.value(), before + 1)
        QTest.mouseClick(spin, Qt.LeftButton, pos=QPoint(spin.width() - 18, spin.height() - 10))
        self.assertEqual(spin.value(), before)

    def test_empty_canvas_tracks_method_selection(self):
        panel = self.window.comparison_panel
        self.assertEqual(panel.content_stack.currentIndex(), 0)
        panel.set_methods(["Ground_Truth"])
        self.assertEqual(panel.content_stack.currentIndex(), 1)
        panel.set_methods([])
        self.assertEqual(panel.content_stack.currentIndex(), 0)

    def test_all_setting_pages_fit_sidebar(self):
        for width, height in [(800, 600), (1440, 960)]:
            self.window.resize(width, height)
            for index in range(3):
                tabs = self.window.settings_panel.sections
                tabs.setCurrentIndex(index)
                self.app.processEvents()
                area = tabs.widget(index)
                self.assertLessEqual(area.widget().width(), area.viewport().width())


if __name__ == "__main__":
    unittest.main()
