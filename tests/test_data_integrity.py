"""Small synthetic checks for frame identity and scientific input integrity."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from models import epi_extractor
from models.light_field_data import LightFieldData
from models.residual import compute_residual


class FrameAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lfv_integrity_")
        self.root = Path(self.temp.name)
        self.data = LightFieldData()

    def tearDown(self):
        self.temp.cleanup()

    def write_image(self, relative_path, value=1, shape=(3, 4, 3)):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.full(shape, value, dtype=np.uint8)).save(path)
        return path

    def test_sai_missing_frame_does_not_shift_later_frames(self):
        for frame in (1, 3):
            self.write_image(f"A/scene/sample_{frame:06d}/1_1.png", frame)
        for frame in (1, 2, 3):
            self.write_image(f"Ground_Truth/scene/frame_{frame:04d}/1_1.png", frame)
        self.data.scan_root(str(self.root))
        self.assertEqual(self.data.get_frame_display_list("scene"),
                         ["frame_0001", "frame_0002", "frame_0003"])
        self.assertIsNone(self.data.load_sai("A", "scene", 1, 1, 1))
        self.assertIsNone(self.data.resolve_sai_path("A", "scene", 1, 1, 1))
        self.assertEqual(int(self.data.load_sai("A", "scene", 2, 1, 1)[0, 0, 0]), 3)
        path = self.data.resolve_sai_path("A", "scene", 2, 1, 1)
        self.assertEqual(Path(path).parent.name, "sample_000003")

    def test_sai_union_includes_frames_missing_from_reference(self):
        for method, frames in (("A", (1, 3)), ("B", (2, 4))):
            for frame in frames:
                self.write_image(f"{method}/scene/frame_{frame}/1_1.png", frame)
        self.data.scan_root(str(self.root))
        self.assertEqual(self.data.get_frame_display_list("scene"),
                         ["frame_1", "frame_2", "frame_3", "frame_4"])
        self.assertIsNone(self.data.load_sai("A", "scene", 1, 1, 1))

    def test_explicit_index_alignment_preserves_legacy_order(self):
        for method, frames in (("A", (1, 3)), ("B", (1, 2, 3))):
            for frame in frames:
                self.write_image(f"{method}/scene/frame_{frame:04d}/1_1.png", frame)
        self.data.scan_root(str(self.root))
        self.data.set_frame_alignment("index")
        self.assertEqual(int(self.data.load_sai("A", "scene", 1, 1, 1)[0, 0, 0]), 3)
        self.data.set_frame_alignment("name")
        self.assertIsNone(self.data.load_sai("A", "scene", 1, 1, 1))
        with self.assertRaises(ValueError):
            self.data.set_frame_alignment("unknown")

    def test_mli_missing_frame_and_index_compatibility(self):
        for frame in (1, 3):
            self.write_image(f"A/scene/sample_{frame:06d}.png", frame)
        for frame in (1, 2, 3):
            self.write_image(f"B/scene/frame_{frame:04d}.png", frame)
        self.data.scan_root(str(self.root))
        self.assertEqual(self.data.get_mli_frame_display_list("scene"),
                         ["frame_0001", "frame_0002", "frame_0003"])
        self.assertIsNone(self.data.load_mli("A", "scene", 1, "video"))
        path = self.data.resolve_mli_path("A", "scene", 2, "video")
        self.assertEqual(Path(path).name, "sample_000003.png")
        self.data.set_frame_alignment("index")
        self.assertEqual(int(self.data.load_mli("A", "scene", 1, "video")[0, 0, 0]), 3)

    def test_non_numeric_frame_names_align_exactly(self):
        for method, names in (("A", ("left", "right")), ("B", ("left", "middle", "right"))):
            for name in names:
                self.write_image(f"{method}/scene/{name}/1_1.png")
        self.data.scan_root(str(self.root))
        self.assertEqual(self.data.get_frame_display_list("scene"), ["left", "middle", "right"])
        self.assertIsNone(self.data.load_sai("A", "scene", 1, 1, 1))

    def test_duplicate_frame_id_is_not_silently_selected(self):
        for name in ("frame_1", "sample_001"):
            self.write_image(f"A/scene/{name}/1_1.png")
        self.data.scan_root(str(self.root))
        with self.assertRaises(ValueError):
            self.data.resolve_sai_path("A", "scene", 0, 1, 1)

    def test_mli_image_mode_preserves_direct_file_loading(self):
        path = self.write_image("A/scene.png", value=42)
        self.data.scan_root(str(self.root))
        self.assertEqual(Path(self.data.resolve_mli_path("A", "scene")), path)
        self.assertEqual(int(self.data.load_mli("A", "scene")[0, 0, 0]), 42)

    def test_incomplete_light_field_is_rejected(self):
        self.write_image("A/scene/1_1.png")
        self.data.scan_root(str(self.root))
        with self.assertRaisesRegex(ValueError, "2|missing|缺"):
            self.data.load_light_field("A", "scene", 0, 2, 2)
        self.assertIsNone(self.data.load_light_field("A", "absent", 0, 2, 2))

    def test_missing_first_view_is_not_an_absent_frame(self):
        self.write_image("A/scene/1_2.png")
        self.data.scan_root(str(self.root))
        with self.assertRaises(ValueError):
            self.data.load_light_field("A", "scene", 0, 1, 2)

    def test_light_field_rejects_mismatched_view_shapes(self):
        self.write_image("A/scene/1_1.png", shape=(3, 4, 3))
        self.write_image("A/scene/1_2.png", shape=(4, 4, 3))
        self.data.scan_root(str(self.root))
        with self.assertRaises(ValueError):
            self.data.load_light_field("A", "scene", 0, 1, 2)

    def test_complete_light_field_keeps_angular_coordinates(self):
        for u in (1, 2):
            for v in (1, 2, 3):
                self.write_image(f"A/scene/{u}_{v}.png", value=10 * u + v)
        self.data.scan_root(str(self.root))
        lf = self.data.load_light_field("A", "scene", 0, 2, 3)
        self.assertEqual(lf.shape, (2, 3, 3, 4, 3))
        self.assertEqual(int(lf[1, 2, 0, 0, 0]), 23)


class ComputationIntegrityTests(unittest.TestCase):
    def test_residual_requires_equal_shapes(self):
        with self.assertRaises(ValueError):
            compute_residual(np.zeros((5, 4, 3), np.uint8), np.zeros((4, 4, 3), np.uint8))

    def test_residual_retains_rgb_mean_absolute_error(self):
        img = np.array([[[255, 0, 0], [0, 255, 255]]], dtype=np.uint8)
        np.testing.assert_allclose(compute_residual(img, np.zeros_like(img)), [[1 / 3, 2 / 3]])

    def test_epi_uses_orientation_specific_angular_dimension(self):
        lf = np.arange(3 * 5 * 2 * 4 * 3).reshape(3, 5, 2, 4, 3)
        np.testing.assert_array_equal(epi_extractor.extract_epi(lf, "vertical", 5, 3), lf[:, 4, :, 3, :])
        np.testing.assert_array_equal(epi_extractor.extract_epi(lf, "horizontal", 3, 1), lf[2, :, 1, :, :])

    def test_epi_rejects_invalid_coordinates_instead_of_clamping(self):
        lf = np.zeros((5, 3, 2, 4, 3), dtype=np.uint8)
        for orientation, angular, spatial in (
            ("vertical", 5, 0), ("horizontal", 0, 0),
            ("horizontal", 1, 2), ("vertical", 1, 4),
            ("horizontal", 1, -1), ("diagonal", 1, 0),
        ):
            with self.subTest(orientation=orientation, angular=angular, spatial=spatial):
                with self.assertRaises(ValueError):
                    epi_extractor.extract_epi(lf, orientation, angular, spatial)

    def test_epi_crop_rejects_invalid_ranges_instead_of_clamping(self):
        epi = np.zeros((5, 32, 3), dtype=np.uint8)
        for start, end in ((200, 260), (20, 10), (10, 10), (-1, 10), (10, 33)):
            with self.subTest(start=start, end=end):
                with self.assertRaisesRegex(ValueError, "32"):
                    epi_extractor.crop_epi(epi, start, end)

    def test_epi_crop_accepts_half_open_boundary_ranges(self):
        epi = np.arange(5 * 32 * 3).reshape(5, 32, 3)
        np.testing.assert_array_equal(epi_extractor.crop_epi(epi, 0, 32), epi)
        np.testing.assert_array_equal(epi_extractor.crop_epi(epi, 31, 32), epi[:, 31:32])
        np.testing.assert_array_equal(epi_extractor.crop_epi(epi, 0, 1), epi[:, :1])


if __name__ == "__main__":
    unittest.main()
