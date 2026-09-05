"""Persisted appearance preference and Windows app-theme tracking."""

import sys

from PyQt5.QtCore import QObject, QSettings, QTimer, pyqtSignal


def system_is_dark():
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
        except OSError:
            return False
    return False


class Appearance(QObject):
    changed = pyqtSignal(bool)
    MODES = ("system", "light", "dark")

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings if settings is not None else QSettings("LightFieldViewer", "Appearance")
        self.mode = self.settings.value("mode", "system")
        if self.mode not in self.MODES:
            self.mode = "system"
        self.dark = self.mode == "dark" or (self.mode == "system" and system_is_dark())
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.refresh)
        if self.mode == "system":
            self.timer.start()

    def set_mode(self, mode):
        if mode not in self.MODES:
            raise ValueError(f"Unknown appearance mode: {mode}")
        self.mode = mode
        self.settings.setValue("mode", mode)
        self.settings.sync()
        if mode == "system":
            self.timer.start()
        else:
            self.timer.stop()
        self.refresh()

    def refresh(self):
        dark = self.mode == "dark" or (self.mode == "system" and system_is_dark())
        if dark != self.dark:
            self.dark = dark
            self.changed.emit(dark)
