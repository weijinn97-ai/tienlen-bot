import unittest
import json
import os
import shutil
import subprocess
import tempfile
import sys
import hashlib
from pathlib import Path
from types import MappingProxyType
from bot.perception.ui_evaluation import (
    UiEvaluationStatus,
    UiButtonState,
    UiPredictedButtonState,
    UiOcrField,
    UiPredictedOcrField,
    UiGroundTruthRecord,
    UiPredictionRecord,
    UiFrameIndexRecord,
    UiEvaluationBundle,
    UiEvaluationConfig,
    UiEvaluationResult,
    evaluate_ui_predictions,
    load_ui_evaluation_bundle,
    write_ui_evaluation_result,
)
from PIL import Image

class UiEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir)

    def _create_perfect_bundle(self, locked=True, num_records=2000, num_sessions=5, num_seqs=50):
        # Creates in-memory bundle
        fi, gt, pr = [], [], []
        sc = "a" * 40
        csha = "b" * 64
        for i in range(num_records):
            fid = f"s{i%num_sessions:02d}-sq{i%num_seqs:02d}-f{i:04d}"
            
            fi.append(UiFrameIndexRecord(
                frame_id=fid, relative_path=f"frames/{fid}.png", sha256=hashlib.sha256(str(i).encode()).hexdigest(),
                session_id=f"s{i%num_sessions:02d}", sequence_id=f"sq{i%num_seqs:02d}", frame_index=i,
                split="test", review_status="APPROVED", reviewer_id="bot"
            ))
            
            gt.append(UiGroundTruthRecord(
                frame_id=fid,
                buttons=MappingProxyType({"play": UiButtonState(False, False), "pass": UiButtonState(True, True)}),
                ocr_fields=tuple([UiOcrField("f1", "13", True)]),
                expected_turn_owner="SELF",
                critical_transition=True,
                negative_play_frame=True
            ))
            
            pr.append(UiPredictionRecord(
                frame_id=fid,
                buttons=MappingProxyType({"play": UiPredictedButtonState(False, False, 0.99), "pass": UiPredictedButtonState(True, True, 0.99)}),
                ocr_fields=tuple([UiPredictedOcrField("f1", "13", 0.99)]),
                turn_owner="SELF", turn_observed_frames=4, turn_matching_frames=3, turn_latest_frame_matches=True,
                latency_ms=10.0, source_commit=sc, config_sha256=csha
            ))
            
        return UiEvaluationBundle(
            "d1", locked, MappingProxyType({"width": 1280, "height": 720}), tuple(fi), tuple(gt), tuple(pr), MappingProxyType({})
        )

    def test_1_perfect_but_insufficient_negatives(self):
        b = self._create_perfect_bundle(num_records=1999) # thieu 1
        res = evaluate_ui_predictions(b, UiEvaluationConfig())
        self.assertEqual(res.status, "INSUFFICIENT_DATA")
        
    def test_2_sufficient_coverage_pass(self):
        b = self._create_perfect_bundle(num_records=2000)
        res = evaluate_ui_predictions(b, UiEvaluationConfig())
        self.assertEqual(res.status, "PASS")

    def test_3_false_enabled_play_on_negative_frame(self):
        b = self._create_perfect_bundle()
        # mut prediction
        pr = list(b.predictions)
        pr[0] = UiPredictionRecord(
            pr[0].frame_id,
            buttons=MappingProxyType({"play": UiPredictedButtonState(True, True, 0.99), "pass": UiPredictedButtonState(True, True, 0.99)}),
            ocr_fields=pr[0].ocr_fields, turn_owner=pr[0].turn_owner, turn_observed_frames=4, turn_matching_frames=3,
            turn_latest_frame_matches=True, latency_ms=10, source_commit=pr[0].source_commit, config_sha256=pr[0].config_sha256
        )
        b = UiEvaluationBundle(b.dataset_id, b.locked, b.viewport, b.frame_index, b.ground_truth, tuple(pr), b.input_sha256)
        res = evaluate_ui_predictions(b, UiEvaluationConfig())
        self.assertEqual(res.status, "FAIL")
        self.assertEqual(res.metrics.false_play_enabled, 1)

    def test_4_button_accuracy_under_threshold(self):
        b = self._create_perfect_bundle()
        pr = list(b.predictions)
        for i in range(25):
            pr[i] = UiPredictionRecord(
                pr[i].frame_id,
                buttons=MappingProxyType({"play": UiPredictedButtonState(True, False, 0.99), "pass": pr[i].buttons["pass"]}),
                ocr_fields=pr[i].ocr_fields, turn_owner=pr[i].turn_owner, turn_observed_frames=4, turn_matching_frames=3,
                turn_latest_frame_matches=True, latency_ms=10, source_commit=pr[0].source_commit, config_sha256=pr[0].config_sha256
            )
        gt = list(b.ground_truth)
        for i in range(25):
            gt[i] = UiGroundTruthRecord(gt[i].frame_id, gt[i].buttons, gt[i].ocr_fields, gt[i].expected_turn_owner, gt[i].critical_transition, False)
        b = UiEvaluationBundle(b.dataset_id, b.locked, b.viewport, b.frame_index, tuple(gt), tuple(pr), b.input_sha256)
        res = evaluate_ui_predictions(b, UiEvaluationConfig())
        self.assertEqual(res.status, "FAIL")

    def test_5_critical_ocr_sai(self):
        b = self._create_perfect_bundle()
        pr = list(b.predictions)
        pr[0] = UiPredictionRecord(
            pr[0].frame_id, pr[0].buttons, ocr_fields=tuple([UiPredictedOcrField("f1", "WRONG", 0.99)]),
            turn_owner=pr[0].turn_owner, turn_observed_frames=4, turn_matching_frames=3,
            turn_latest_frame_matches=True, latency_ms=10, source_commit=pr[0].source_commit, config_sha256=pr[0].config_sha256
        )
        b = UiEvaluationBundle(b.dataset_id, b.locked, b.viewport, b.frame_index, b.ground_truth, tuple(pr), b.input_sha256)
        res = evaluate_ui_predictions(b, UiEvaluationConfig(min_critical_ocr_exact_accuracy=1.0))
        self.assertEqual(res.status, "FAIL")

    def test_6_low_confidence_ocr_khong_tra_unknown(self):
        b = self._create_perfect_bundle()
        pr = list(b.predictions)
        pr[0] = UiPredictionRecord(
            pr[0].frame_id, pr[0].buttons, ocr_fields=tuple([UiPredictedOcrField("f1", "13", 0.1)]),
            turn_owner=pr[0].turn_owner, turn_observed_frames=4, turn_matching_frames=3,
            turn_latest_frame_matches=True, latency_ms=10, source_commit=pr[0].source_commit, config_sha256=pr[0].config_sha256
        )
        b = UiEvaluationBundle(b.dataset_id, b.locked, b.viewport, b.frame_index, b.ground_truth, tuple(pr), b.input_sha256)
        res = evaluate_ui_predictions(b, UiEvaluationConfig())
        self.assertEqual(res.status, "FAIL")

    def test_7_false_my_turn(self):
        b = self._create_perfect_bundle()
        gt = list(b.ground_truth)
        gt[0] = UiGroundTruthRecord(gt[0].frame_id, gt[0].buttons, gt[0].ocr_fields, "LEFT", gt[0].critical_transition, gt[0].negative_play_frame)
        b = UiEvaluationBundle(b.dataset_id, b.locked, b.viewport, b.frame_index, tuple(gt), b.predictions, b.input_sha256)
        res = evaluate_ui_predictions(b, UiEvaluationConfig())
        self.assertEqual(res.status, "FAIL")
        self.assertEqual(res.metrics.false_my_turn, 1)

    def test_8_critical_turn_3_4_latest_false(self):
        b = self._create_perfect_bundle()
        pr = list(b.predictions)
        pr[0] = UiPredictionRecord(
            pr[0].frame_id, pr[0].buttons, pr[0].ocr_fields, turn_owner=pr[0].turn_owner, turn_observed_frames=4,
            turn_matching_frames=3, turn_latest_frame_matches=False, latency_ms=10, source_commit=pr[0].source_commit, config_sha256=pr[0].config_sha256
        )
        b = UiEvaluationBundle(b.dataset_id, b.locked, b.viewport, b.frame_index, b.ground_truth, tuple(pr), b.input_sha256)
        res = evaluate_ui_predictions(b, UiEvaluationConfig())
        self.assertEqual(res.status, "FAIL")
        self.assertEqual(res.metrics.critical_consensus_violations, 1)

    def _write_json(self, name, obj):
        p = Path(self.tmp_dir) / name
        p.write_text(json.dumps(obj), encoding="utf-8")
        return p

    def _write_jsonl(self, name, rows):
        p = Path(self.tmp_dir) / name
        p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        return p

    def _setup_fs_bundle(self):
        d = Path(self.tmp_dir)
        fid = "s01-sq01-f001"
        img_path = d / "frames" / f"{fid}.png"
        img_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new('RGB', (1280, 720))
        img.save(img_path, "PNG")
        sha = hashlib.sha256(img_path.read_bytes()).hexdigest()
        
        fi = [{"frame_id": fid, "relative_path": f"frames/{fid}.png", "sha256": sha, "session_id": "s01", "sequence_id": "sq01", "frame_index": 1, "split": "test", "review_status": "APPROVED", "reviewer_id": "b"}]
        gt = [{"frame_id": fid, "buttons": {"play": {"visible": False, "enabled": False}, "pass": {"visible": True, "enabled": True}}, "ocr_fields": [{"field_id": "f1", "expected_text": "13", "critical": True}], "expected_turn_owner": "SELF", "critical_transition": True, "negative_play_frame": True}]
        pr = [{"frame_id": fid, "buttons": {"play": {"visible": False, "enabled": False, "confidence": 0.99}, "pass": {"visible": True, "enabled": True, "confidence": 0.99}}, "ocr_fields": [{"field_id": "f1", "text": "13", "confidence": 0.99}], "turn_owner": "SELF", "turn_observed_frames": 4, "turn_matching_frames": 3, "turn_latest_frame_matches": True, "latency_ms": 10.0, "source_commit": "a"*40, "config_sha256": "b"*64}]
        
        self._write_jsonl("fi.jsonl", fi)
        self._write_jsonl("gt.jsonl", gt)
        self._write_jsonl("pr.jsonl", pr)
        
        s1 = hashlib.sha256((d/"fi.jsonl").read_bytes()).hexdigest()
        s2 = hashlib.sha256((d/"gt.jsonl").read_bytes()).hexdigest()
        s3 = hashlib.sha256((d/"pr.jsonl").read_bytes()).hexdigest()
        
        bundle = {
            "schema_version": 1, "dataset_id": "t", "locked": True,
            "viewport": {"width": 1280, "height": 720},
            "files": {"frame_index": "fi.jsonl", "ground_truth": "gt.jsonl", "predictions": "pr.jsonl"},
            "sha256": {"fi.jsonl": s1, "gt.jsonl": s2, "pr.jsonl": s3}
        }
        self._write_json("bundle.json", bundle)
        return bundle, fi, gt, pr

    def test_9_missing_frame_prediction_invalid(self):
        b, fi, gt, pr = self._setup_fs_bundle()
        pr = pr[:-1]
        self._write_jsonl("pr.jsonl", pr)
        b["sha256"]["pr.jsonl"] = hashlib.sha256((Path(self.tmp_dir)/"pr.jsonl").read_bytes()).hexdigest()
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError) as cm:
            load_ui_evaluation_bundle(self.tmp_dir)
        self.assertIn("Mismatch between frame_index and predictions", str(cm.exception))

    def test_9_10_missing_duplicate_fails(self):
        b, fi, gt, pr = self._setup_fs_bundle()
        
        pr.append(pr[0])
        self._write_jsonl("pr.jsonl", pr)
        b["sha256"]["pr.jsonl"] = hashlib.sha256((Path(self.tmp_dir)/"pr.jsonl").read_bytes()).hexdigest()
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError) as cm:
            load_ui_evaluation_bundle(self.tmp_dir)
        self.assertIn("Duplicate frame_id", str(cm.exception))

        pr = pr[:1]
        pr[0]["ocr_fields"].append(pr[0]["ocr_fields"][0])
        self._write_jsonl("pr.jsonl", pr)
        b["sha256"]["pr.jsonl"] = hashlib.sha256((Path(self.tmp_dir)/"pr.jsonl").read_bytes()).hexdigest()
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError) as cm:
            load_ui_evaluation_bundle(self.tmp_dir)
        self.assertIn("Duplicate ocr field_id", str(cm.exception))

    def test_11_duplicate_json_key_and_nan(self):
        b, fi, gt, pr = self._setup_fs_bundle()
        bad_json = '{"frame_id": "f", "frame_id": "f2"}'
        (Path(self.tmp_dir) / "pr.jsonl").write_text(bad_json, encoding="utf-8")
        b["sha256"]["pr.jsonl"] = hashlib.sha256((Path(self.tmp_dir)/"pr.jsonl").read_bytes()).hexdigest()
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError):
            load_ui_evaluation_bundle(self.tmp_dir)
            
        bad_json2 = '{"latency_ms": NaN}'
        (Path(self.tmp_dir) / "pr.jsonl").write_text(bad_json2, encoding="utf-8")
        b["sha256"]["pr.jsonl"] = hashlib.sha256((Path(self.tmp_dir)/"pr.jsonl").read_bytes()).hexdigest()
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError):
            load_ui_evaluation_bundle(self.tmp_dir)

    def test_12_bool_as_int_float_invalid(self):
        b, fi, gt, pr = self._setup_fs_bundle()
        pr[0]["turn_observed_frames"] = True
        self._write_jsonl("pr.jsonl", pr)
        b["sha256"]["pr.jsonl"] = hashlib.sha256((Path(self.tmp_dir)/"pr.jsonl").read_bytes()).hexdigest()
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError) as cm:
            load_ui_evaluation_bundle(self.tmp_dir)
        self.assertIn("must be exactly int", str(cm.exception))

    def test_13_path_traversal_invalid(self):
        b, fi, gt, pr = self._setup_fs_bundle()
        del b["sha256"][b["files"]["frame_index"]]
        b["files"]["frame_index"] = "../fi.jsonl"
        b["sha256"]["../fi.jsonl"] = "0" * 64
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError) as cm:
            load_ui_evaluation_bundle(self.tmp_dir)
        self.assertIn("Invalid path traversal", str(cm.exception))

    def test_14_checksum_mismatch(self):
        b, fi, gt, pr = self._setup_fs_bundle()
        b["sha256"]["fi.jsonl"] = "0" * 64
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError) as cm:
            load_ui_evaluation_bundle(self.tmp_dir)
        self.assertIn("Checksum mismatch", str(cm.exception))

    def test_15_test_frame_chua_approved(self):
        b, fi, gt, pr = self._setup_fs_bundle()
        fi[0]["review_status"] = "REJECTED"
        self._write_jsonl("fi.jsonl", fi)
        b["sha256"]["fi.jsonl"] = hashlib.sha256((Path(self.tmp_dir)/"fi.jsonl").read_bytes()).hexdigest()
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError) as cm:
            load_ui_evaluation_bundle(self.tmp_dir)
        self.assertIn("not APPROVED", str(cm.exception))
        
    def test_16_unlocked_bundle_never_pass(self):
        b = self._create_perfect_bundle(locked=False)
        res = evaluate_ui_predictions(b, UiEvaluationConfig())
        self.assertEqual(res.status, "INSUFFICIENT_DATA")

    def test_17_18_19_20_deterministic_output_and_cli(self):
        b, fi, gt, pr = self._setup_fs_bundle()
        cli = Path(__file__).parent.parent / "tools" / "evaluate_perception_ui.py"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent.parent)
        
        out_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out_dir)
        
        out1 = out_dir / "out1"
        res1 = subprocess.run([sys.executable, str(cli), "--bundle", self.tmp_dir, "--output", str(out1)], env=env)
        self.assertEqual(res1.returncode, 2)
        
        out2 = out_dir / "out2"
        res2 = subprocess.run([sys.executable, str(cli), "--bundle", self.tmp_dir, "--output", str(out2)], env=env)
        self.assertEqual(res2.returncode, 2)
        
        s1 = hashlib.sha256((out1 / "metrics.json").read_bytes()).hexdigest()
        s2 = hashlib.sha256((out2 / "metrics.json").read_bytes()).hexdigest()
        self.assertEqual(s1, s2)
        
        f1 = hashlib.sha256((out1 / "failures.jsonl").read_bytes()).hexdigest()
        f2 = hashlib.sha256((out2 / "failures.jsonl").read_bytes()).hexdigest()
        self.assertEqual(f1, f2)
        
        e1 = hashlib.sha256((out1 / "evaluated_manifest.json").read_bytes()).hexdigest()
        e2 = hashlib.sha256((out2 / "evaluated_manifest.json").read_bytes()).hexdigest()
        self.assertEqual(e1, e2)
        
        # Make it FAIL
        pr[0]["buttons"]["play"]["enabled"] = True
        self._write_jsonl("pr.jsonl", pr)
        b["sha256"]["pr.jsonl"] = hashlib.sha256((Path(self.tmp_dir)/"pr.jsonl").read_bytes()).hexdigest()
        self._write_json("bundle.json", b)
        
        out3 = out_dir / "out3"
        res3 = subprocess.run([sys.executable, str(cli), "--bundle", self.tmp_dir, "--output", str(out3)], env=env)
        self.assertEqual(res3.returncode, 1)

    def test_21_25_source_commit_config_mixed_invalid(self):
        b, fi, gt, pr = self._setup_fs_bundle()
        pr[0]["source_commit"] = "short"
        self._write_jsonl("pr.jsonl", pr)
        b["sha256"]["pr.jsonl"] = hashlib.sha256((Path(self.tmp_dir)/"pr.jsonl").read_bytes()).hexdigest()
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError):
            load_ui_evaluation_bundle(self.tmp_dir)
            
        pr[0]["source_commit"] = "a"*40
        fi.append(fi[0].copy())
        gt.append(gt[0].copy())
        pr.append(pr[0].copy())
        
        img2 = Path(self.tmp_dir) / "frames" / "f2.png"
        Image.new('RGB', (1280, 720), color="red").save(img2, "PNG")
        sha2 = hashlib.sha256(img2.read_bytes()).hexdigest()
        
        fi[1]["frame_id"] = "f2"
        fi[1]["relative_path"] = "frames/f2.png"
        fi[1]["sha256"] = sha2
        fi[1]["frame_index"] = 2
        
        gt[1]["frame_id"] = "f2"
        pr[1]["frame_id"] = "f2"
        pr[1]["source_commit"] = "c"*40
        
        self._write_jsonl("fi.jsonl", fi)
        self._write_jsonl("gt.jsonl", gt)
        self._write_jsonl("pr.jsonl", pr)
        b["sha256"]["fi.jsonl"] = hashlib.sha256((Path(self.tmp_dir)/"fi.jsonl").read_bytes()).hexdigest()
        b["sha256"]["gt.jsonl"] = hashlib.sha256((Path(self.tmp_dir)/"gt.jsonl").read_bytes()).hexdigest()
        b["sha256"]["pr.jsonl"] = hashlib.sha256((Path(self.tmp_dir)/"pr.jsonl").read_bytes()).hexdigest()
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError) as cm:
            load_ui_evaluation_bundle(self.tmp_dir)
        self.assertIn("Mixed source_commit", str(cm.exception))

    def test_22_max_record_guard(self):
        p = Path(self.tmp_dir) / "huge.jsonl"
        with open(p, "w") as f:
            for _ in range(500001):
                f.write('{}\n')
        b, fi, gt, pr = self._setup_fs_bundle()
        del b["sha256"][b["files"]["frame_index"]]
        b["files"]["frame_index"] = "huge.jsonl"
        b["sha256"]["huge.jsonl"] = hashlib.sha256(p.read_bytes()).hexdigest()
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError) as cm:
            load_ui_evaluation_bundle(self.tmp_dir)
        self.assertIn("Too many lines", str(cm.exception))

    def test_23_duplicate_image_checksum_coverage(self):
        b, fi, gt, pr = self._setup_fs_bundle()
        fi.append(fi[0].copy())
        fi[1]["frame_id"] = "f2"
        fi[1]["frame_index"] = 2
        gt.append(gt[0].copy())
        gt[1]["frame_id"] = "f2"
        pr.append(pr[0].copy())
        pr[1]["frame_id"] = "f2"
        self._write_jsonl("fi.jsonl", fi)
        self._write_jsonl("gt.jsonl", gt)
        self._write_jsonl("pr.jsonl", pr)
        b["sha256"]["fi.jsonl"] = hashlib.sha256((Path(self.tmp_dir)/"fi.jsonl").read_bytes()).hexdigest()
        b["sha256"]["gt.jsonl"] = hashlib.sha256((Path(self.tmp_dir)/"gt.jsonl").read_bytes()).hexdigest()
        b["sha256"]["pr.jsonl"] = hashlib.sha256((Path(self.tmp_dir)/"pr.jsonl").read_bytes()).hexdigest()
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError) as cm:
            load_ui_evaluation_bundle(self.tmp_dir)
        self.assertIn("Duplicate test image", str(cm.exception))

    def test_24_thieu_session_sequence(self):
        b = self._create_perfect_bundle(num_records=2000, num_sessions=4, num_seqs=50)
        res = evaluate_ui_predictions(b, UiEvaluationConfig())
        self.assertEqual(res.status, "INSUFFICIENT_DATA")

    def test_26_enum_sai_button_thieu(self):
        b, fi, gt, pr = self._setup_fs_bundle()
        pr[0]["turn_owner"] = "UP"
        self._write_jsonl("pr.jsonl", pr)
        b["sha256"]["pr.jsonl"] = hashlib.sha256((Path(self.tmp_dir)/"pr.jsonl").read_bytes()).hexdigest()
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError) as cm:
            load_ui_evaluation_bundle(self.tmp_dir)
        self.assertIn("Invalid turn_owner", str(cm.exception))
        
        pr[0]["turn_owner"] = "SELF"
        del pr[0]["buttons"]["play"]
        self._write_jsonl("pr.jsonl", pr)
        b["sha256"]["pr.jsonl"] = hashlib.sha256((Path(self.tmp_dir)/"pr.jsonl").read_bytes()).hexdigest()
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError) as cm:
            load_ui_evaluation_bundle(self.tmp_dir)
        self.assertIn("missing keys", str(cm.exception))
        
    def test_symlink_escape(self):
        b, fi, gt, pr = self._setup_fs_bundle()
        if os.name == 'nt':
            return # Skip on Windows as symlinks require admin
        link_target = Path(self.tmp_dir).parent
        link_path = Path(self.tmp_dir) / "escape"
        try:
            link_path.symlink_to(link_target)
        except OSError:
            return
        b["files"]["frame_index"] = "escape/fi.jsonl"
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError) as cm:
            load_ui_evaluation_bundle(self.tmp_dir)
        self.assertIn("Escape path detected", str(cm.exception))

    def test_absolute_unc_path(self):
        b, fi, gt, pr = self._setup_fs_bundle()
        del b["sha256"][b["files"]["frame_index"]]
        if os.name == 'nt':
            b["files"]["frame_index"] = "C:\\Windows\\system32\\fi.jsonl"
            b["sha256"]["C:\\Windows\\system32\\fi.jsonl"] = "0"*64
        else:
            b["files"]["frame_index"] = "/etc/passwd"
            b["sha256"]["/etc/passwd"] = "0"*64
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError) as cm:
            load_ui_evaluation_bundle(self.tmp_dir)
        self.assertIn("absolute", str(cm.exception))
        
    def test_corrupt_image(self):
        b, fi, gt, pr = self._setup_fs_bundle()
        img = Path(self.tmp_dir) / "frames" / f"{fi[0]['frame_id']}.png"
        img.write_bytes(b"NOT_A_PNG")
        fi[0]["sha256"] = hashlib.sha256(b"NOT_A_PNG").hexdigest()
        self._write_jsonl("fi.jsonl", fi)
        b["sha256"]["fi.jsonl"] = hashlib.sha256((Path(self.tmp_dir)/"fi.jsonl").read_bytes()).hexdigest()
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError) as cm:
            load_ui_evaluation_bundle(self.tmp_dir)
        self.assertIn("Corrupt or invalid image", str(cm.exception))

    def test_viewport_mismatch(self):
        b, fi, gt, pr = self._setup_fs_bundle()
        b["viewport"]["width"] = 1920
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError) as cm:
            load_ui_evaluation_bundle(self.tmp_dir)
        self.assertIn("Image dimensions mismatch", str(cm.exception))

    def test_lowered_threshold_non_pass(self):
        b = self._create_perfect_bundle(num_records=10) # very small test set
        res = evaluate_ui_predictions(b, UiEvaluationConfig(min_test_frames=1, min_negative_play_frames=1, min_test_sessions=1, min_test_sequences=1))
        # because the config thresholds are lower than DEFAULT_CONFIG, validate_config returns False, which forces INSUFFICIENT_DATA even if technically PASS
        self.assertEqual(res.status, "INSUFFICIENT_DATA")

    def test_path_collision(self):
        b, fi, gt, pr = self._setup_fs_bundle()
        if os.name != 'nt':
            return
        # A duplicate input that resolves to the same path
        b["files"]["ground_truth"] = "FI.jsonl"
        b["sha256"]["FI.jsonl"] = b["sha256"]["fi.jsonl"]
        del b["sha256"]["gt.jsonl"]
        self._write_json("bundle.json", b)
        with self.assertRaises(ValueError) as cm:
            load_ui_evaluation_bundle(self.tmp_dir)
        self.assertIn("Path collision detected", str(cm.exception))

if __name__ == '__main__':
    unittest.main()
