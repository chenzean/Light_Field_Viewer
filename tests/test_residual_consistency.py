"""Compare preview residual pixels with exported PNGs."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication

import config as cfg
from controllers.app_controller import AppController
from controllers.export_controller import ExportController


def pixmap_pixels(pixmap):
    image = pixmap.toImage().convertToFormat(QImage.Format_RGB888)
    bits = image.bits()
    bits.setsize(image.byteCount())
    rows = np.frombuffer(bits, dtype=np.uint8).reshape(image.height(), image.bytesPerLine())
    return rows[:, :image.width() * 3].reshape(image.height(), image.width(), 3).copy()


class ResidualConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def test_preview_matches_export(self):
        for mode in ('sai', 'mli'):
            for thickness in (1, 3):
                for zero_residual in (False, True):
                    with self.subTest(mode=mode, thickness=thickness, zero=zero_residual):
                        self.check_export(mode, thickness, zero_residual)

    def check_export(self, mode, thickness, zero_residual):
        gt = np.zeros((24, 30, 3), dtype=np.uint8)
        method_a = gt.copy()
        method_b = gt.copy()
        if not zero_residual:
            method_a[2:10, 2:10] = 30
            method_a[12:20, 12:20] = 90
            method_b[:] = 15
            method_b[23, 29] = 255  # Global maximum outside every ROI.
        images = {'Ground_Truth': gt, 'A': method_a, 'B': method_b, 'Missing': None}
        rects = [dict(x=x, y=y, w=8, h=8, color=(0, 255, 0), thickness=thickness)
                 for x, y in ((2, 2), (12, 12), (0, 0), (25, 19))]
        comparison = Mock()
        app = SimpleNamespace(
            selected_methods=list(images), rects=rects, residual_enabled=True,
            comparison=comparison,
            lf_data=SimpleNamespace(load_sai=lambda method, *args: images[method],
                                    load_mli=lambda method, *args: images[method]))
        with patch('controllers.app_controller.generate_colorbar') as colorbar:
            colorbar.return_value = np.zeros((10, 3, 3), dtype=np.uint8)
            AppController._refresh_zoom_tab(app, images.get)
            self.assertAlmostEqual(colorbar.call_args.args[0], 0.0 if zero_residual else 1.0)
        residuals = comparison.update_all_zooms.call_args.args[3]
        self.assertEqual(set(residuals), {'A', 'B'})
        with tempfile.TemporaryDirectory() as directory:
            params = dict(export_dir=directory, methods=list(images), rects=rects,
                          scene='scene', frame_index=0, u=1, v=1, mode='image',
                          residual_enabled=True, epi_enabled=False)
            exporter = ExportController(app)
            getattr(exporter, '_export_' + mode)(params)
            for method in ('A', 'B'):
                base = f'{method}_scene_f0_' + ('1_1' if mode == 'sai' else 'mli')
                for index, pixmap in enumerate(residuals[method], 1):
                    path = (Path(directory) / cfg.EXPORT_DIR_RESIDUAL_CROP / method
                            / f'{base}_rect{index}_residual.png')
                    with Image.open(path) as saved:
                        np.testing.assert_array_equal(pixmap_pixels(pixmap), np.asarray(saved))


if __name__ == '__main__':
    unittest.main()
