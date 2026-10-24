"""Check batch isolation, source identity, and truthful partial-export reports."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image

import config as cfg
from controllers.export_controller import ExportController
from models.light_field_data import LightFieldData


class ExportIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lfv_export_test_')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data_root = self.root / 'data'
        self.data_root.mkdir()
        self.output = self.root / 'output'
        self.data = LightFieldData()
        self.status = Mock()
        self.params = dict(
            data_root=str(self.data_root), export_dir=str(self.output),
            methods=['Ground_Truth', 'A'], rects=[], scene='scene',
            frame_index=0, u=1, v=1, angular_u=2, angular_v=2,
            mode='video', vis_mode='sai', residual_enabled=True,
            epi_enabled=False, epi_orientation='horizontal', epi_angular_idx=1,
            epi_spatial_pos=1, epi_crop_start=0, epi_crop_end=4, epi_stretch=1,
        )
        app = SimpleNamespace(lf_data=self.data, get_export_params=lambda: self.params,
                              window=SimpleNamespace(statusBar=lambda: self.status))
        self.exporter = ExportController(app)

    def write_image(self, relative, value=0, shape=(5, 6, 3)):
        path = self.data_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.full(shape, value, dtype=np.uint8)).save(path)
        return path

    def scan(self):
        self.data.scan_root(str(self.data_root))

    def run_export(self):
        batch = Path(self.exporter.export())
        manifest = json.loads((batch / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['image_count'], len(manifest['outputs']))
        for output in manifest['outputs']:
            self.assertTrue(Path(output['path']).is_file())
            self.assertEqual(Path(output['path']), batch / output['relative_path'])
        return batch, manifest

    def test_consecutive_exports_preserve_first_batch_and_log(self):
        self.write_image('Ground_Truth/scene/frame_0001/1_1.png')
        source = self.write_image('A/scene/sample_000001/1_1.png', 30)
        self.scan()
        first, first_manifest = self.run_export()
        first_files = {path.relative_to(first): path.read_bytes()
                       for path in first.rglob('*') if path.is_file()}
        Image.fromarray(np.full((5, 6, 3), 60, dtype=np.uint8)).save(source)
        second, second_manifest = self.run_export()
        self.assertNotEqual(first, second)
        self.assertAlmostEqual(first_manifest['residual']['vmax'], 30 / 255)
        self.assertAlmostEqual(second_manifest['residual']['vmax'], 60 / 255)
        for relative, content in first_files.items():
            self.assertEqual((first / relative).read_bytes(), content)
        self.assertEqual(self.params['export_dir'], str(self.output))

    def test_zero_residual_exports_colorbar_and_actual_frame_paths(self):
        self.write_image('Ground_Truth/scene/frame_0007/1_1.png')
        source = self.write_image('A/scene/sample_000007/1_1.png')
        self.scan()
        batch, manifest = self.run_export()
        self.assertTrue((batch / cfg.EXPORT_DIR_RESIDUAL_ANNOTATED / 'colorbar.png').is_file())
        self.assertEqual(manifest['residual']['vmax'], 0.0)
        self.assertEqual(manifest['residual']['display_vmax'], 1e-12)
        self.assertEqual(manifest['methods']['A']['source']['path'], str(source.resolve()))
        self.assertEqual(manifest['methods']['A']['source']['frame_name'], 'sample_000007')
        self.assertEqual(manifest['parameters']['epi_spatial_pos'], 1)
        self.assertEqual(manifest['frame_alignment'], 'name')
        self.assertEqual(manifest['status'], 'complete')

    def test_missing_corrupt_and_mismatched_methods_are_not_reported_as_success(self):
        self.write_image('Ground_Truth/scene/frame_0001/1_1.png')
        self.write_image('A/scene/frame_0001/1_1.png', 30)
        broken = self.write_image('Broken/scene/frame_0001/1_1.png')
        broken.write_bytes(b'not an image')
        self.write_image('WrongSize/scene/frame_0001/1_1.png', 40, (3, 4, 3))
        self.params['methods'] += ['Missing', 'Broken', 'WrongSize']
        self.scan()
        batch, manifest = self.run_export()
        self.assertEqual(manifest['status'], 'partial')
        self.assertEqual(manifest['methods']['A']['status'], 'complete')
        self.assertEqual(manifest['methods']['Missing']['status'], 'skipped')
        self.assertEqual(manifest['methods']['Broken']['status'], 'failed')
        self.assertEqual(manifest['methods']['WrongSize']['status'], 'partial')
        self.assertEqual(manifest['residual']['methods'], ['A'])
        self.assertFalse((batch / cfg.EXPORT_DIR_RESIDUAL_ANNOTATED / 'WrongSize').exists())
        self.assertIn('部分导出', self.status.showMessage.call_args.args[0])
        self.assertEqual(manifest['methods']['Broken']['source']['path'], str(broken.resolve()))

    def test_missing_reference_preserves_originals_and_reports_skipped_residual(self):
        self.write_image('A/scene/frame_0001/1_1.png', 20)
        self.scan()
        batch, manifest = self.run_export()
        self.assertEqual(manifest['status'], 'partial')
        self.assertTrue(any(i['stage'] == 'residual' for i in manifest['issues']))
        self.assertIsNone(manifest['residual']['vmax'])
        self.assertFalse((batch / cfg.EXPORT_DIR_RESIDUAL_ANNOTATED).exists())

    def test_all_missing_is_failed_not_successful_zero_image_export(self):
        self.scan()
        _, manifest = self.run_export()
        self.assertEqual(manifest['image_count'], 0)
        self.assertEqual(manifest['status'], 'failed')
        self.assertIn('导出失败', self.status.showMessage.call_args.args[0])

    def test_epi_uses_snapshot_parameters_and_records_sources(self):
        for u in (1, 2):
            for v in (1, 2):
                self.write_image(f'A/scene/frame_0001/{u}_{v}.png', 10 * u + v)
        self.params.update(methods=['A'], residual_enabled=False, epi_enabled=True,
                           epi_orientation='vertical', epi_angular_idx=2)
        self.scan()
        _, manifest = self.run_export()
        entry = manifest['methods']['A']
        self.assertEqual(entry['status'], 'complete')
        self.assertEqual(len(entry['epi_sources']), 4)
        full = next(output for output in entry['outputs'] if output['kind'] == 'epi_full')
        with Image.open(full['path']) as image:
            actual = np.asarray(image)
        self.assertEqual(actual.shape, (2, 5, 3))
        np.testing.assert_array_equal(actual[:, 0, 0], [12, 22])

    def test_incomplete_epi_retains_requested_line_but_reports_failed_epi(self):
        self.write_image('A/scene/frame_0001/1_1.png', 20)
        self.params.update(methods=['A'], residual_enabled=False, epi_enabled=True)
        self.scan()
        _, manifest = self.run_export()
        entry = manifest['methods']['A']
        self.assertEqual(entry['status'], 'partial')
        self.assertTrue(any(i['stage'] == 'epi' and i['status'] == 'failed'
                            for i in entry['issues']))
        self.assertFalse(any(o['kind'].startswith('epi') for o in entry['outputs']))
        annotated = next(o for o in entry['outputs'] if o['kind'] == 'annotated')
        with Image.open(annotated['path']) as image:
            pixels = np.asarray(image)
            np.testing.assert_array_equal(pixels[1, 0], [0, 0, 255])
            np.testing.assert_array_equal(pixels[4, 5], [20, 20, 20])

    def test_invalid_epi_crop_is_reported_without_silently_clamping(self):
        for u in (1, 2):
            for v in (1, 2):
                self.write_image(f'A/scene/frame_0001/{u}_{v}.png', 20)
        self.params.update(methods=['A'], residual_enabled=False, epi_enabled=True,
                           epi_crop_end=100)
        self.scan()
        _, manifest = self.run_export()
        self.assertEqual(manifest['status'], 'partial')
        self.assertTrue(any(i['stage'] == 'epi_output' and i['status'] == 'failed'
                            for i in manifest['issues']))
        self.assertTrue(any(o['kind'] == 'epi_full' for o in manifest['outputs']))
        self.assertFalse(any(o['kind'] == 'epi_crop' for o in manifest['outputs']))

    def test_nonintersecting_roi_does_not_block_following_valid_crops(self):
        self.write_image('Ground_Truth/scene/frame_0001/1_1.png')
        self.write_image('A/scene/frame_0001/1_1.png', 30)
        self.params['rects'] = [
            dict(x=x, y=y, w=2, h=2, color=(0, 255, 0), thickness=1)
            for x, y in ((1, 1), (20, 20), (3, 2), (-4, 0))
        ]
        self.scan()
        batch, manifest = self.run_export()
        self.assertEqual(manifest['status'], 'partial')
        for category, suffix in ((cfg.EXPORT_DIR_ZOOM_CROP, ''),
                                 (cfg.EXPORT_DIR_RESIDUAL_CROP, '_residual')):
            for index in (1, 3):
                self.assertTrue((batch / category / 'A' /
                                 f'A_scene_f0_1_1_rect{index}{suffix}.png').is_file())
            for index in (2, 4):
                self.assertFalse((batch / category / 'A' /
                                  f'A_scene_f0_1_1_rect{index}{suffix}.png').exists())
        issues = manifest['methods']['A']['issues']
        for kind in ('crop', 'residual_crop'):
            reasons = [issue['reason'] for issue in issues if issue['stage'] == kind]
            self.assertTrue(any('ROI 2' in reason and 'x=20' in reason and '无交集' in reason
                                for reason in reasons))
            self.assertTrue(any('ROI 4' in reason and 'x=-4' in reason for reason in reasons))

    def test_partially_outside_roi_retains_clipped_pixels(self):
        self.write_image('A/scene/frame_0001/1_1.png', 30)
        self.params.update(methods=['A'], residual_enabled=False, rects=[
            dict(x=4, y=3, w=4, h=4, color=(0, 255, 0), thickness=1)])
        self.scan()
        _, manifest = self.run_export()
        self.assertEqual(manifest['status'], 'complete')
        crop = next(output for output in manifest['outputs'] if output['kind'] == 'crop')
        with Image.open(crop['path']) as image:
            self.assertEqual(image.size, (2, 2))
            expected = np.broadcast_to([0, 255, 0], (2, 2, 3))
            np.testing.assert_array_equal(np.asarray(image), expected)

    def test_mli_missing_frame_does_not_export_next_frame(self):
        for frame in (1, 2):
            self.write_image(f'Ground_Truth/scene/frame_{frame:04d}.png', frame)
        self.write_image('A/scene/sample_000002.png', 2)
        self.params.update(vis_mode='mli', frame_index=0)
        self.scan()
        _, manifest = self.run_export()
        self.assertEqual(manifest['methods']['A']['status'], 'skipped')
        self.assertIsNone(manifest['methods']['A']['source'])
        self.assertEqual(manifest['methods']['Ground_Truth']['source']['frame_name'], 'frame_0001')

    def test_write_failure_is_recorded_and_other_methods_survive(self):
        self.write_image('Ground_Truth/scene/frame_0001/1_1.png')
        self.write_image('A/scene/frame_0001/1_1.png', 20)
        self.scan()
        save = self.exporter._save_image

        def fail_method_a(array, path):
            if Path(path).parent.name == 'A':
                raise OSError('test output failure')
            save(array, path)

        with patch.object(self.exporter, '_save_image', side_effect=fail_method_a):
            _, manifest = self.run_export()
        self.assertEqual(manifest['status'], 'partial')
        self.assertEqual(manifest['methods']['A']['status'], 'failed')
        self.assertEqual(manifest['methods']['Ground_Truth']['status'], 'complete')
        self.assertTrue(any(i['reason'] == 'test output failure' for i in manifest['issues']))

    def test_log_failure_is_recorded_in_manifest_and_status(self):
        self.write_image('A/scene/frame_0001/1_1.png', 20)
        self.params.update(methods=['A'], residual_enabled=False)
        self.scan()
        with patch('controllers.export_controller.write_export_log',
                   side_effect=OSError('test log failure')):
            _, manifest = self.run_export()
        self.assertEqual(manifest['status'], 'partial')
        self.assertTrue(any(i['stage'] == 'log_output' for i in manifest['issues']))
        self.assertIn('部分导出', self.status.showMessage.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
