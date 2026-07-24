"""
Focused tests for the perception UI inference runner (GEMINI-PERCEPTION-UI-01B).

Tests cover all R2 repair areas:
  A. Multi-template button semantics (play_enabled/play_disabled/pass_enabled)
  B. Strict adapter-output validation + frame-wide safe result
  C. Resource limits enforced before allocation
  D. Source sequence, viewport, and TOCTOU integrity
  E. Normalized OCR ROI contract
  F. Clock CLOCK_INVALID semantics
  G. Output isolation, completeness, and transactional write
  H. CLI exit codes 0/1/2/3 via subprocess
"""
import unittest
import tempfile
import shutil
import json
import hashlib
import sys
import os
import math
import subprocess
from unittest import mock
from pathlib import Path
from types import MappingProxyType
import numpy as np

# Ensure repository root is in python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.perception import (
    load_ui_inference_source,
    load_ui_inference_config,
    run_ui_inference,
    write_ui_inference_result,
    UiInferenceSource,
    UiInferenceConfig,
    UiInferenceFrameRecord,
    UiPredictionRecord,
    UiFailureRecord,
    OcrFieldConfig,
    NormalizedOcrRoi,
    ButtonTemplateConfig,
)
from bot.perception.ui_evaluation import evaluate_ui_predictions, UiEvaluationConfig
from contracts.interfaces import (
    Rect,
    ButtonId,
    ButtonState,
    SeatPosition,
    TurnOwnerEvidence,
    TurnPrimarySignal,
)
from bot.perception.turn_owner import (
    TurnOwnerDetection,
    TurnOwnerConsensusResult,
    NormalizedRect,
    HighlightDetection,
    CardCountDelta,
)
from bot.perception.ocr import OcrText

# ------------------------------------------------------------------ #
# Fake / Mock Adapters for Tests                                      #
# ------------------------------------------------------------------ #

class FakeButtonDetector:
    def __init__(self, detections=None):
        self.detections = detections or ()
        self.calls = 0
    def detect(self, frame):
        self.calls += 1
        return self.detections

class FakeOcrDetector:
    def __init__(self, result=None):
        self.result = result
        self.calls = 0
    def recognize(self, frame, roi, whitelist=""):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        if self.result is None:
            return OcrText("UNKNOWN", roi, 0.0)
        return OcrText(self.result.text, roi, self.result.confidence)

class FakeTurnDetector:
    def __init__(self, result=None):
        self.result = result
        self.calls = 0
    def detect(self, frame, previous_card_counts, current_card_counts):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        if self.result is not None:
            return self.result
        return TurnOwnerDetection(
            turn_owner=None,
            evidence=None,
            primary=HighlightDetection(None, 0.0, None, {}),
            secondary=CardCountDelta(None, None, 0.0)
        )

class FakeTurnConsensus:
    def __init__(self, result=None):
        self.result = result
        self.calls = 0
        self.resets = 0
    def observe(self, bot_id, detection):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        if self.result is not None:
            return self.result
        return TurnOwnerConsensusResult(None, 1, 0, 3)
    def reset(self, bot_id):
        self.resets += 1


def _make_adapters(
    btn_det=None,
    ocr_det=None,
    turn_det=None,
    turn_con=None,
):
    """Build an Adapters namespace with fake defaults."""
    class Adapters:
        button_detector = btn_det or FakeButtonDetector()
        ocr_detector = ocr_det or FakeOcrDetector()
        turn_detector = turn_det or FakeTurnDetector()
        turn_consensus = turn_con or FakeTurnConsensus()
    return Adapters()


class UiInferenceRunnerTests(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir)

    def _write_file(self, rel_path: str, content: str | bytes) -> Path:
        p = Path(self.tmp_dir) / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
        return p

    def _make_png(self, path: Path, width: int = 1280, height: int = 720, fill: int = 0) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        img = np.zeros((height, width, 3), dtype=np.uint8) + fill
        import cv2
        cv2.imwrite(str(path), img)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _setup_valid_bundle(self, extra_templates: dict | None = None):
        """
        Creates a minimal valid bundle with a single play_enabled template.
        extra_templates: dict of {template_key: {"filename": ..., ...}} to add.
        Returns (config_path, src_dir).
        """
        # Write dummy button template
        btn_path = Path(self.tmp_dir) / "templates" / "play_enabled.png"
        btn_sha = self._make_png(btn_path, 50, 20)

        btn_templates_cfg = {
            "play_enabled": {
                "filename": "play_enabled.png",
                "search_roi": {"x": 0.25, "y": 0.45, "width": 0.5, "height": 0.22},
                "threshold": 0.82,
                "sha256": btn_sha,
            }
        }

        if extra_templates:
            for key, tmpl_cfg in extra_templates.items():
                btn_templates_cfg[key] = tmpl_cfg

        config_data = {
            "schema_version": 1,
            "viewport": {"width": 1280, "height": 720},
            "ocr_minimum_confidence": 0.75,
            "ocr_fields": {
                "self_count": {
                    "roi": {"x": 0.45, "y": 0.86, "width": 0.094, "height": 0.056},
                    "whitelist": "0123456789",
                }
            },
            "button_template_dir": "templates",
            "button_templates": btn_templates_cfg,
            "consensus": {
                "history_size": 4,
                "required_matches": 3,
            },
            "resource_limits": {
                "max_file_size_bytes": 209715200,
                "max_records": 500000,
                "max_line_length": 1048576,
                "max_total_input_bytes": 536870912,
                "max_image_pixels": 16777216,
                "max_output_bytes": 104857600,
            },
            "source_commit": "00e82bbc59befeb7db9450bb945c2eaae93d4bb3",
        }
        config_p = self._write_file("config.json", json.dumps(config_data))

        # Source json and index
        frame_path = Path(self.tmp_dir) / "frames" / "f1.png"
        frame_sha = self._make_png(frame_path, 1280, 720)

        index_records = [
            {
                "frame_id": "f1",
                "relative_path": "frames/f1.png",
                "sha256": frame_sha,
                "session_id": "s1",
                "sequence_id": "seq1",
                "frame_index": 1,
                "capture_ts_ms": 1000,
                "player_card_counts": {
                    "SELF": 13, "LEFT": 13, "TOP": 13, "RIGHT": 13,
                },
            }
        ]
        index_jsonl = json.dumps(index_records[0]) + "\n"
        self._write_file("frame_index.jsonl", index_jsonl)
        index_sha = hashlib.sha256(index_jsonl.encode("utf-8")).hexdigest()

        source_data = {
            "schema_version": 1,
            "dataset_id": "ui-source-v1",
            "viewport": {"width": 1280, "height": 720},
            "frame_index": "frame_index.jsonl",
            "frame_index_sha256": index_sha,
        }
        self._write_file("source.json", json.dumps(source_data))

        return config_p, self.tmp_dir

    def _add_second_frame(
        self,
        src_dir: str,
        seq_id: str = "seq1",
        frame_index: int = 2,
        ts: int = 2000,
        fill: int = 10,
    ) -> None:
        """Add a second frame to the existing source bundle."""
        frame_path = Path(src_dir) / "frames" / "f2.png"
        self._make_png(frame_path, 1280, 720, fill=fill)

        existing_fi = (Path(src_dir) / "frame_index.jsonl").read_text(encoding="utf-8").strip()
        rec1 = json.loads(existing_fi)

        rec2 = {
            "frame_id": "f2",
            "relative_path": "frames/f2.png",
            "sha256": hashlib.sha256(frame_path.read_bytes()).hexdigest(),
            "session_id": "s1",
            "sequence_id": seq_id,
            "frame_index": frame_index,
            "capture_ts_ms": ts,
            "player_card_counts": {"SELF": 13, "LEFT": 13, "TOP": 13, "RIGHT": 13},
        }
        new_fi = json.dumps(rec1) + "\n" + json.dumps(rec2) + "\n"
        (Path(src_dir) / "frame_index.jsonl").write_text(new_fi, encoding="utf-8", newline="\n")
        new_sha = hashlib.sha256(new_fi.encode("utf-8")).hexdigest()
        src_json = json.loads((Path(src_dir) / "source.json").read_text(encoding="utf-8"))
        src_json["frame_index_sha256"] = new_sha
        (Path(src_dir) / "source.json").write_text(json.dumps(src_json), encoding="utf-8")

    # ------------------------------------------------------------------ #
    # Test Group 01: Happy Path and Determinism                           #
    # ------------------------------------------------------------------ #

    def test_01_happy_path_calls_adapters_once(self):
        """Happy path runs inference calling each adapter exactly once per frame."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        btn_det = FakeButtonDetector()
        ocr_det = FakeOcrDetector()
        turn_det = FakeTurnDetector()
        turn_con = FakeTurnConsensus()

        res = run_ui_inference(source, _make_adapters(btn_det, ocr_det, turn_det, turn_con), config)
        self.assertEqual(len(res.predictions), 1)
        self.assertEqual(len(res.failures), 0)
        self.assertEqual(btn_det.calls, 1)
        self.assertEqual(ocr_det.calls, 1)
        # Turn detector not called on the very first frame of a sequence (no history)
        self.assertEqual(turn_det.calls, 0)
        self.assertEqual(turn_con.calls, 1)

    def test_02_prediction_evaluator_01a_compatible(self):
        """Predictions generated are fully parseable and validated by 01A evaluator."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        btn_det = FakeButtonDetector([
            ButtonState(ButtonId.PLAY, "Đánh", Rect(0,0,10,10), True, True, 0.9)
        ])
        ocr_det = FakeOcrDetector(OcrText("13", Rect(0,0,10,10), 0.95))
        turn_con = FakeTurnConsensus(TurnOwnerConsensusResult(SeatPosition.SELF, 1, 1, 3))

        res = run_ui_inference(source, _make_adapters(btn_det, ocr_det, turn_con=turn_con), config)

        out_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out_dir)
        write_ui_inference_result(res, out_dir)

        from bot.perception import load_ui_evaluation_bundle
        shutil.copy(Path(src_dir) / "source.json", out_dir / "bundle.json")
        bundle_json_data = json.loads((out_dir / "bundle.json").read_text(encoding="utf-8"))
        bundle_json_data["files"] = {
            "frame_index": "fi.jsonl",
            "ground_truth": "gt.jsonl",
            "predictions": "predictions.jsonl",
        }
        eval_fi_record = {
            "frame_id": "f1",
            "relative_path": "frames/f1.png",
            "sha256": source.frame_index[0].sha256,
            "session_id": "s1",
            "sequence_id": "seq1",
            "frame_index": 1,
            "split": "test",
            "review_status": "APPROVED",
            "reviewer_id": "reviewer-1",
        }
        (out_dir / "fi.jsonl").write_text(json.dumps(eval_fi_record) + "\n", encoding="utf-8")
        (out_dir / "frames").mkdir(parents=True, exist_ok=True)
        shutil.copy(Path(src_dir) / "frames" / "f1.png", out_dir / "frames" / "f1.png")

        gt_record = {
            "frame_id": "f1",
            "buttons": {
                "play": {"visible": True, "enabled": True},
                "pass": {"visible": False, "enabled": False},
            },
            "ocr_fields": [
                {"field_id": "self_count", "expected_text": "13", "critical": True}
            ],
            "expected_turn_owner": "SELF",
            "critical_transition": False,
            "negative_play_frame": False,
        }
        (out_dir / "gt.jsonl").write_text(json.dumps(gt_record) + "\n", encoding="utf-8")

        bundle_json_data["locked"] = True
        bundle_json_data.pop("frame_index", None)
        bundle_json_data.pop("frame_index_sha256", None)
        bundle_json_data["sha256"] = {
            "fi.jsonl": hashlib.sha256((out_dir / "fi.jsonl").read_bytes()).hexdigest(),
            "gt.jsonl": hashlib.sha256((out_dir / "gt.jsonl").read_bytes()).hexdigest(),
            "predictions.jsonl": hashlib.sha256((out_dir / "predictions.jsonl").read_bytes()).hexdigest(),
        }
        (out_dir / "bundle.json").write_text(json.dumps(bundle_json_data), encoding="utf-8")

        eval_bundle = load_ui_evaluation_bundle(out_dir)
        self.assertEqual(len(eval_bundle.predictions), 1)

    def test_03_does_not_read_ground_truth(self):
        """Runner does not access ground_truth files, even if they exist adjacent to source."""
        cfg_p, src_dir = self._setup_valid_bundle()
        gt_file = Path(src_dir) / "ground_truth.jsonl"
        gt_file.write_text("dummy", encoding="utf-8")
        source = load_ui_inference_source(src_dir)
        self.assertNotIn("ground_truth.jsonl", source.input_sha256)

    def test_04_does_not_mutate_inputs(self):
        """Runner does not modify passed source or config dataclass inputs."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)
        orig_dataset_id = source.dataset_id
        orig_source_commit = config.source_commit

        run_ui_inference(source, _make_adapters(), config)
        self.assertEqual(source.dataset_id, orig_dataset_id)
        self.assertEqual(config.source_commit, orig_source_commit)

    def test_05_deterministic_checksums_two_runs(self):
        """Two separate inference runs produce identical predictions.jsonl and failures.jsonl bytes."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        class FixedAdapters:
            button_detector = FakeButtonDetector([
                ButtonState(ButtonId.PLAY, "Đánh", Rect(0,0,10,10), True, True, 0.9)
            ])
            ocr_detector = FakeOcrDetector(OcrText("13", Rect(0,0,10,10), 0.95))
            turn_detector = FakeTurnDetector()
            turn_consensus = FakeTurnConsensus()

        res1 = run_ui_inference(source, FixedAdapters(), config, clock=lambda: 1.0)
        res2 = run_ui_inference(source, FixedAdapters(), config, clock=lambda: 1.0)

        out1 = Path(tempfile.mkdtemp())
        out2 = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out1)
        self.addCleanup(shutil.rmtree, out2)

        write_ui_inference_result(res1, out1)
        write_ui_inference_result(res2, out2)

        self.assertEqual(
            (out1 / "predictions.jsonl").read_bytes(),
            (out2 / "predictions.jsonl").read_bytes(),
            "predictions.jsonl must be byte-deterministic across two runs",
        )
        self.assertEqual(
            (out1 / "failures.jsonl").read_bytes(),
            (out2 / "failures.jsonl").read_bytes(),
            "failures.jsonl must be byte-deterministic across two runs",
        )
        self.assertEqual(
            (out1 / "inference_manifest.json").read_bytes(),
            (out2 / "inference_manifest.json").read_bytes(),
            "inference_manifest.json must be byte-deterministic across two runs",
        )

    # ------------------------------------------------------------------ #
    # Test Group 06-09: Loader Rejections                                 #
    # ------------------------------------------------------------------ #

    def test_06_reject_extra_or_missing_json_keys(self):
        """Loader rejects source/config JSON with extra/missing keys or duplicate keys."""
        cfg_p, src_dir = self._setup_valid_bundle()

        bad_source = {
            "dataset_id": "ui-source-v1",
            "viewport": {"width": 1280, "height": 720},
            "frame_index": "frame_index.jsonl",
            "frame_index_sha256": "0123456789abcdef",
        }
        self._write_file("source.json", json.dumps(bad_source))
        with self.assertRaises(ValueError):
            load_ui_inference_source(src_dir)

        bad_config_str = '{"schema_version": 1, "schema_version": 2}'
        config_bad_p = self._write_file("config_bad.json", bad_config_str)
        with self.assertRaises(ValueError):
            load_ui_inference_config(config_bad_p)

    def test_07_reject_blank_lines_or_nan_in_jsonl(self):
        """Loader rejects blank lines, invalid UTF-8, and NaN/Infinity in JSONL."""
        cfg_p, src_dir = self._setup_valid_bundle()

        self._write_file("frame_index.jsonl", "\n")
        with self.assertRaises(ValueError):
            load_ui_inference_source(src_dir)

        cfg_nan_p = self._write_file("config_nan.json", '{"schema_version": 1, "ocr_minimum_confidence": NaN}')
        with self.assertRaises(ValueError):
            load_ui_inference_config(cfg_nan_p)

    def test_08_reject_bool_as_number(self):
        """Loader rejects boolean values passed where integers/floats are expected."""
        cfg_p, src_dir = self._setup_valid_bundle()
        config_data = json.loads(Path(cfg_p).read_text(encoding="utf-8"))
        config_data["resource_limits"]["max_records"] = True  # bool instead of int
        bad_p = self._write_file("config_bool.json", json.dumps(config_data))
        with self.assertRaises(ValueError, msg="Should reject bool as int for max_records"):
            load_ui_inference_config(bad_p)

    def test_09_reject_traversal_paths(self):
        """Loader rejects traversal, backslashes, drive prefixes, and UNC paths."""
        cfg_p, src_dir = self._setup_valid_bundle()

        bad_source = json.loads((Path(src_dir) / "source.json").read_text(encoding="utf-8"))
        bad_source["frame_index"] = "../evil.jsonl"
        self._write_file("source.json", json.dumps(bad_source))
        with self.assertRaises(ValueError, msg="Should reject traversal path"):
            load_ui_inference_source(src_dir)

    def test_10_reject_invalid_image(self):
        """Loader rejects missing, corrupt, incorrect dimension images."""
        cfg_p, src_dir = self._setup_valid_bundle()

        # Write corrupt image data and update sha256
        frame_path = Path(src_dir) / "frames" / "f1.png"
        frame_path.write_bytes(b"notapng")
        corrupt_sha = hashlib.sha256(b"notapng").hexdigest()

        fi = json.loads((Path(src_dir) / "frame_index.jsonl").read_text(encoding="utf-8"))
        fi["sha256"] = corrupt_sha
        new_fi = json.dumps(fi) + "\n"
        (Path(src_dir) / "frame_index.jsonl").write_text(new_fi, encoding="utf-8", newline="\n")
        new_sha = hashlib.sha256(new_fi.encode("utf-8")).hexdigest()
        src = json.loads((Path(src_dir) / "source.json").read_text(encoding="utf-8"))
        src["frame_index_sha256"] = new_sha
        (Path(src_dir) / "source.json").write_text(json.dumps(src), encoding="utf-8")

        with self.assertRaises(ValueError, msg="Should reject corrupt image"):
            load_ui_inference_source(src_dir)

    def test_11_reject_duplicate_frame_id(self):
        """Loader rejects duplicate frame IDs in the manifest index."""
        cfg_p, src_dir = self._setup_valid_bundle()
        frame_sha = hashlib.sha256((Path(src_dir) / "frames" / "f1.png").read_bytes()).hexdigest()
        # Two rows with same frame_id
        fi1 = {
            "frame_id": "f1", "relative_path": "frames/f1.png", "sha256": frame_sha,
            "session_id": "s1", "sequence_id": "seq1", "frame_index": 1, "capture_ts_ms": 1000,
            "player_card_counts": {"SELF":13, "LEFT":13, "TOP":13, "RIGHT":13},
        }
        fi2 = dict(fi1)
        fi2["relative_path"] = "frames/f1.png"  # same file, same id
        new_fi = json.dumps(fi1) + "\n" + json.dumps(fi2) + "\n"
        (Path(src_dir) / "frame_index.jsonl").write_text(new_fi, encoding="utf-8", newline="\n")
        src = json.loads((Path(src_dir) / "source.json").read_text(encoding="utf-8"))
        src["frame_index_sha256"] = hashlib.sha256(new_fi.encode("utf-8")).hexdigest()
        (Path(src_dir) / "source.json").write_text(json.dumps(src), encoding="utf-8")
        with self.assertRaises(ValueError, msg="Should reject duplicate frame_id"):
            load_ui_inference_source(src_dir)

    def test_12_reject_timestamp_regression(self):
        """Loader rejects capture_ts_ms regressions within a sequence."""
        cfg_p, src_dir = self._setup_valid_bundle()
        frame_sha = hashlib.sha256((Path(src_dir) / "frames" / "f1.png").read_bytes()).hexdigest()
        # Second frame has lower ts
        f2_path = Path(src_dir) / "frames" / "f2.png"
        self._make_png(f2_path, 1280, 720, fill=5)
        f2_sha = hashlib.sha256(f2_path.read_bytes()).hexdigest()
        fi1 = {
            "frame_id": "f1", "relative_path": "frames/f1.png", "sha256": frame_sha,
            "session_id": "s1", "sequence_id": "seq1", "frame_index": 1, "capture_ts_ms": 2000,
            "player_card_counts": {"SELF":13, "LEFT":13, "TOP":13, "RIGHT":13},
        }
        fi2 = {
            "frame_id": "f2", "relative_path": "frames/f2.png", "sha256": f2_sha,
            "session_id": "s1", "sequence_id": "seq1", "frame_index": 2, "capture_ts_ms": 1000,  # regression
            "player_card_counts": {"SELF":13, "LEFT":13, "TOP":13, "RIGHT":13},
        }
        new_fi = json.dumps(fi1) + "\n" + json.dumps(fi2) + "\n"
        (Path(src_dir) / "frame_index.jsonl").write_text(new_fi, encoding="utf-8", newline="\n")
        src = json.loads((Path(src_dir) / "source.json").read_text(encoding="utf-8"))
        src["frame_index_sha256"] = hashlib.sha256(new_fi.encode("utf-8")).hexdigest()
        (Path(src_dir) / "source.json").write_text(json.dumps(src), encoding="utf-8")
        with self.assertRaises(ValueError, msg="Should reject timestamp regression"):
            load_ui_inference_source(src_dir)

    def test_13_reject_invalid_card_count(self):
        """Card counts must be integers in [0, 13] for all 4 seats."""
        cfg_p, src_dir = self._setup_valid_bundle()
        frame_sha = hashlib.sha256((Path(src_dir) / "frames" / "f1.png").read_bytes()).hexdigest()
        fi = {
            "frame_id": "f1", "relative_path": "frames/f1.png", "sha256": frame_sha,
            "session_id": "s1", "sequence_id": "seq1", "frame_index": 1, "capture_ts_ms": 1000,
            "player_card_counts": {"SELF": 14, "LEFT": 13, "TOP": 13, "RIGHT": 13},  # 14 is out of range
        }
        new_fi = json.dumps(fi) + "\n"
        (Path(src_dir) / "frame_index.jsonl").write_text(new_fi, encoding="utf-8", newline="\n")
        src = json.loads((Path(src_dir) / "source.json").read_text(encoding="utf-8"))
        src["frame_index_sha256"] = hashlib.sha256(new_fi.encode("utf-8")).hexdigest()
        (Path(src_dir) / "source.json").write_text(json.dumps(src), encoding="utf-8")
        with self.assertRaises(ValueError, msg="Should reject card count out of range"):
            load_ui_inference_source(src_dir)

    def test_14_reject_forbidden_gt_keys(self):
        """Rejects config or source containing ground_truth or label fields."""
        cfg_p, src_dir = self._setup_valid_bundle()
        fi = {
            "frame_id": "f1", "relative_path": "frames/f1.png",
            "sha256": hashlib.sha256((Path(src_dir) / "frames" / "f1.png").read_bytes()).hexdigest(),
            "session_id": "s1", "sequence_id": "seq1", "frame_index": 1, "capture_ts_ms": 1000,
            "player_card_counts": {"SELF": 13, "LEFT": 13, "TOP": 13, "RIGHT": 13},
            "ground_truth": "injected",  # forbidden
        }
        new_fi = json.dumps(fi) + "\n"
        (Path(src_dir) / "frame_index.jsonl").write_text(new_fi, encoding="utf-8", newline="\n")
        src = json.loads((Path(src_dir) / "source.json").read_text(encoding="utf-8"))
        src["frame_index_sha256"] = hashlib.sha256(new_fi.encode("utf-8")).hexdigest()
        (Path(src_dir) / "source.json").write_text(json.dumps(src), encoding="utf-8")
        with self.assertRaises(ValueError, msg="Should reject ground_truth key in frame index"):
            load_ui_inference_source(src_dir)

    # ------------------------------------------------------------------ #
    # Test Group 15-17: Resource Limits (Fix C)                           #
    # ------------------------------------------------------------------ #

    def test_15_resource_limits_max_records_enforced(self):
        """Config max_records limit is actually used to reject excess frames in JSONL."""
        cfg_p, src_dir = self._setup_valid_bundle()
        # Write config with max_records=1
        config_data = json.loads(Path(cfg_p).read_text(encoding="utf-8"))
        config_data["resource_limits"]["max_records"] = 1
        cfg_limited_p = self._write_file("config_limited.json", json.dumps(config_data))

        config = load_ui_inference_config(cfg_limited_p)

        # Add second frame; source JSONL now has 2 records
        f2_path = Path(src_dir) / "frames" / "f2.png"
        self._make_png(f2_path, 1280, 720, fill=3)
        f1_sha = hashlib.sha256((Path(src_dir) / "frames" / "f1.png").read_bytes()).hexdigest()
        fi1 = {
            "frame_id": "f1", "relative_path": "frames/f1.png", "sha256": f1_sha,
            "session_id": "s1", "sequence_id": "seq1", "frame_index": 1, "capture_ts_ms": 1000,
            "player_card_counts": {"SELF":13,"LEFT":13,"TOP":13,"RIGHT":13},
        }
        fi2 = dict(fi1)
        fi2.update({
            "frame_id": "f2", "relative_path": "frames/f2.png",
            "sha256": hashlib.sha256(f2_path.read_bytes()).hexdigest(),
            "frame_index": 2, "capture_ts_ms": 2000,
        })
        new_fi = json.dumps(fi1) + "\n" + json.dumps(fi2) + "\n"
        (Path(src_dir) / "frame_index.jsonl").write_text(new_fi, encoding="utf-8", newline="\n")
        src = json.loads((Path(src_dir) / "source.json").read_text(encoding="utf-8"))
        src["frame_index_sha256"] = hashlib.sha256(new_fi.encode("utf-8")).hexdigest()
        (Path(src_dir) / "source.json").write_text(json.dumps(src), encoding="utf-8")

        # Loading source with 2 records should fail because max_records=1
        with self.assertRaises(ValueError, msg="Should reject JSONL exceeding max_records=1"):
            load_ui_inference_source(src_dir, resource_limits=config.resource_limits)

    def test_16_resource_limits_zero_rejected(self):
        """Config loader rejects resource limits with zero or negative values."""
        cfg_p, src_dir = self._setup_valid_bundle()
        config_data = json.loads(Path(cfg_p).read_text(encoding="utf-8"))
        config_data["resource_limits"]["max_records"] = 0  # zero not allowed
        bad_p = self._write_file("config_zero.json", json.dumps(config_data))
        with self.assertRaises(ValueError, msg="Should reject zero max_records"):
            load_ui_inference_config(bad_p)

    def test_17_resource_limits_bool_rejected(self):
        """Config loader rejects bool values for resource limits (True/False are not ints)."""
        cfg_p, src_dir = self._setup_valid_bundle()
        config_data = json.loads(Path(cfg_p).read_text(encoding="utf-8"))
        config_data["resource_limits"]["max_file_size_bytes"] = False  # bool
        bad_p = self._write_file("config_bool_limit.json", json.dumps(config_data))
        with self.assertRaises(ValueError, msg="Should reject False as max_file_size_bytes"):
            load_ui_inference_config(bad_p)

    # ------------------------------------------------------------------ #
    # Test Group 18-20: Immutability and Integrity (Fix D, Fix E)         #
    # ------------------------------------------------------------------ #

    def test_18_immutable_dataclasses_mapping(self):
        """Source and config objects use immutable tuples and MappingProxyType."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        self.assertIsInstance(source.viewport, MappingProxyType)
        self.assertIsInstance(source.frame_index, tuple)
        self.assertIsInstance(config.ocr_fields, MappingProxyType)
        self.assertIsInstance(config.button_templates, MappingProxyType)
        self.assertIsInstance(config.resource_limits, MappingProxyType)

        # Caller mutation of viewport dict must not affect config
        with self.assertRaises((TypeError, AttributeError)):
            config.viewport["width"] = 999  # type: ignore

    def test_19_template_image_stored_as_bytes_not_ndarray(self):
        """ButtonTemplateConfig stores immutable bytes, not a mutable numpy array."""
        cfg_p, src_dir = self._setup_valid_bundle()
        config = load_ui_inference_config(cfg_p)
        tmpl = next(iter(config.button_templates.values()))
        # Must be bytes (immutable), not ndarray
        self.assertIsInstance(tmpl.image_bytes, bytes)
        # decode_template_image must return a read-only array
        img = config.decode_template_image(next(iter(config.button_templates)))
        self.assertFalse(img.flags.writeable)

    def test_20_normalized_ocr_roi_resolution(self):
        """Normalized OCR ROI is correctly resolved to pixel Rect for the viewport."""
        cfg_p, src_dir = self._setup_valid_bundle()
        config = load_ui_inference_config(cfg_p)
        fc = config.ocr_fields["self_count"]
        # Normalized coords must be floats in [0.0, 1.0]
        self.assertIsInstance(fc.normalized_roi.x, float)
        self.assertIsInstance(fc.normalized_roi.width, float)
        self.assertGreater(fc.normalized_roi.width, 0.0)
        self.assertLessEqual(fc.normalized_roi.x + fc.normalized_roi.width, 1.0)
        # resolve_ocr_roi must return integer Rect within viewport
        roi = config.resolve_ocr_roi("self_count")
        vw = config.viewport["width"]
        vh = config.viewport["height"]
        self.assertGreater(roi.width, 0)
        self.assertGreater(roi.height, 0)
        self.assertLessEqual(roi.x + roi.width, vw)
        self.assertLessEqual(roi.y + roi.height, vh)

    def test_21_normalized_ocr_roi_rejects_out_of_bounds(self):
        """Config loader rejects OCR ROI with normalized x+w > 1.0."""
        cfg_p, src_dir = self._setup_valid_bundle()
        config_data = json.loads(Path(cfg_p).read_text(encoding="utf-8"))
        config_data["ocr_fields"]["self_count"]["roi"]["x"] = 0.9
        config_data["ocr_fields"]["self_count"]["roi"]["width"] = 0.5  # 0.9 + 0.5 = 1.4 > 1.0
        bad_p = self._write_file("config_oob.json", json.dumps(config_data))
        with self.assertRaises(ValueError, msg="Should reject x+width > 1.0"):
            load_ui_inference_config(bad_p)

    def test_22_normalized_ocr_roi_rejects_zero_width(self):
        """Config loader rejects OCR ROI with normalized width = 0.0."""
        cfg_p, src_dir = self._setup_valid_bundle()
        config_data = json.loads(Path(cfg_p).read_text(encoding="utf-8"))
        config_data["ocr_fields"]["self_count"]["roi"]["width"] = 0.0  # zero not allowed
        bad_p = self._write_file("config_zero_w.json", json.dumps(config_data))
        with self.assertRaises(ValueError, msg="Should reject zero width in OCR ROI"):
            load_ui_inference_config(bad_p)

    def test_23_viewport_mismatch_before_adapter_calls(self):
        """Source/config viewport mismatch is rejected before any adapter call."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)
        mismatched_source = UiInferenceSource(
            dataset_id=source.dataset_id,
            viewport={"width": 1920, "height": 1080},
            frame_index=source.frame_index,
            input_sha256=source.input_sha256,
            source_dir=source.source_dir,
        )
        button_detector = FakeButtonDetector()
        with self.assertRaises(ValueError):
            run_ui_inference(
                mismatched_source,
                _make_adapters(btn_det=button_detector),
                config,
            )
        self.assertEqual(button_detector.calls, 0)

    def test_24_toctou_frame_mutation_after_load(self):
        """Frame file changed after source loading causes IMAGE_INTEGRITY_ERROR at inference."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        # Mutate frame file after load
        frame_path = Path(src_dir) / "frames" / "f1.png"
        original_bytes = frame_path.read_bytes()
        # Write slightly different content
        import cv2
        modified_img = np.ones((720, 1280, 3), dtype=np.uint8) * 128
        cv2.imwrite(str(frame_path), modified_img)

        btn_det = FakeButtonDetector()
        res = run_ui_inference(source, _make_adapters(btn_det), config)

        # Expect integrity failure, not a successful detection
        self.assertEqual(len(res.failures), 1)
        self.assertEqual(res.failures[0].reason_code, "IMAGE_INTEGRITY_ERROR")
        # Safe prediction was emitted
        self.assertEqual(res.predictions[0].buttons["play"].visible, False)
        self.assertEqual(res.predictions[0].buttons["play"].enabled, False)
        # Button adapter must NOT have been called (integrity check came first)
        self.assertEqual(btn_det.calls, 0)

    def test_25_contiguous_frame_index_gap_rejected(self):
        """Loader rejects frame_index gaps (1, 3 instead of 1, 2)."""
        cfg_p, src_dir = self._setup_valid_bundle()
        f2_path = Path(src_dir) / "frames" / "f2.png"
        self._make_png(f2_path, 1280, 720, fill=7)
        f1_sha = hashlib.sha256((Path(src_dir) / "frames" / "f1.png").read_bytes()).hexdigest()
        fi1 = {
            "frame_id": "f1", "relative_path": "frames/f1.png", "sha256": f1_sha,
            "session_id": "s1", "sequence_id": "seq1", "frame_index": 1, "capture_ts_ms": 1000,
            "player_card_counts": {"SELF":13,"LEFT":13,"TOP":13,"RIGHT":13},
        }
        fi2 = dict(fi1)
        fi2.update({
            "frame_id": "f2", "relative_path": "frames/f2.png",
            "sha256": hashlib.sha256(f2_path.read_bytes()).hexdigest(),
            "frame_index": 3,  # gap: expected 2
            "capture_ts_ms": 2000,
        })
        new_fi = json.dumps(fi1) + "\n" + json.dumps(fi2) + "\n"
        (Path(src_dir) / "frame_index.jsonl").write_text(new_fi, encoding="utf-8", newline="\n")
        src = json.loads((Path(src_dir) / "source.json").read_text(encoding="utf-8"))
        src["frame_index_sha256"] = hashlib.sha256(new_fi.encode("utf-8")).hexdigest()
        (Path(src_dir) / "source.json").write_text(json.dumps(src), encoding="utf-8")
        with self.assertRaises(ValueError, msg="Should reject frame_index gap"):
            load_ui_inference_source(src_dir)

    # ------------------------------------------------------------------ #
    # Test Group 26-30: Button Semantics (Fix A)                          #
    # ------------------------------------------------------------------ #

    def test_26_three_template_play_pass_config(self):
        """Config with play_enabled, play_disabled, and pass_enabled produces valid PLAY/PASS."""
        pass_path = Path(self.tmp_dir) / "templates" / "pass_enabled.png"
        pass_sha = self._make_png(pass_path, 50, 20, fill=2)
        play_dis_path = Path(self.tmp_dir) / "templates" / "play_disabled.png"
        play_dis_sha = self._make_png(play_dis_path, 50, 20, fill=3)

        extra = {
            "pass_enabled": {
                "filename": "pass_enabled.png",
                "search_roi": {"x": 0.25, "y": 0.45, "width": 0.5, "height": 0.22},
                "threshold": 0.82,
                "sha256": pass_sha,
            },
            "play_disabled": {
                "filename": "play_disabled.png",
                "search_roi": {"x": 0.25, "y": 0.45, "width": 0.5, "height": 0.22},
                "threshold": 0.70,
                "sha256": play_dis_sha,
            },
        }
        cfg_p, src_dir = self._setup_valid_bundle(extra_templates=extra)
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        # Verify all three template IDs loaded correctly with correct ButtonId
        self.assertIn("play_enabled", config.button_templates)
        self.assertIn("play_disabled", config.button_templates)
        self.assertIn("pass_enabled", config.button_templates)
        self.assertEqual(config.button_templates["play_enabled"].button_id, ButtonId.PLAY)
        self.assertEqual(config.button_templates["play_disabled"].button_id, ButtonId.PLAY)
        self.assertEqual(config.button_templates["pass_enabled"].button_id, ButtonId.PASS)
        self.assertTrue(config.button_templates["play_enabled"].is_enabled)
        self.assertFalse(config.button_templates["play_disabled"].is_enabled)
        self.assertTrue(config.button_templates["pass_enabled"].is_enabled)

        # Run inference with a high-confidence PLAY detection — must not raise BUTTON_DETECTOR_ERROR
        btn = FakeButtonDetector([
            ButtonState(ButtonId.PLAY, "Đánh", Rect(0,0,10,10), True, True, 0.9),
            ButtonState(ButtonId.PASS, "Bỏ Lượt", Rect(10,10,10,10), True, True, 0.85),
        ])
        res = run_ui_inference(source, _make_adapters(btn), config)
        self.assertEqual(len(res.failures), 0, "Should produce no BUTTON_DETECTOR_ERROR")
        self.assertTrue(res.predictions[0].buttons["play"].visible)
        self.assertTrue(res.predictions[0].buttons["pass"].visible)

    def test_27_duplicate_button_highest_confidence_selected(self):
        """If adapter returns two states for same ButtonId, highest confidence wins."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        # Two PLAY states; second has higher confidence
        btn = FakeButtonDetector([
            ButtonState(ButtonId.PLAY, "Đánh", Rect(0,0,10,10), True, True, 0.5),
            ButtonState(ButtonId.PLAY, "Đánh", Rect(0,0,10,10), True, True, 0.95),
        ])
        res = run_ui_inference(source, _make_adapters(btn), config)
        self.assertEqual(len(res.failures), 0)
        # Highest confidence 0.95 wins; threshold 0.82 → visible
        play = res.predictions[0].buttons["play"]
        self.assertAlmostEqual(play.confidence, 0.95, places=5)
        self.assertTrue(play.visible)

    def test_28_duplicate_button_deterministic_tie(self):
        """Duplicate button states with same confidence have a deterministic tie-break."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        conf = 0.9
        btn = FakeButtonDetector([
            ButtonState(ButtonId.PLAY, "Đánh", Rect(0,0,10,10), True, True, conf),
            ButtonState(ButtonId.PLAY, "Đánh", Rect(5,5,10,10), True, True, conf),
        ])
        res1 = run_ui_inference(source, _make_adapters(btn), config, clock=lambda: 1.0)
        res2 = run_ui_inference(source, _make_adapters(btn), config, clock=lambda: 1.0)
        self.assertEqual(
            res1.predictions[0].buttons["play"].confidence,
            res2.predictions[0].buttons["play"].confidence,
        )

    def test_29_missing_button_id_becomes_invisible_disabled(self):
        """Missing ButtonId in adapter output → visible=False, enabled=False, confidence=0.0."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        btn = FakeButtonDetector([])  # returns nothing
        res = run_ui_inference(source, _make_adapters(btn), config)
        play = res.predictions[0].buttons["play"]
        self.assertFalse(play.visible)
        self.assertFalse(play.enabled)
        self.assertEqual(play.confidence, 0.0)
        pass_btn = res.predictions[0].buttons["pass"]
        self.assertFalse(pass_btn.visible)
        self.assertFalse(pass_btn.enabled)

    def test_30_invisible_button_must_always_be_disabled(self):
        """Buttons predicted as invisible are strictly forced to disabled=False."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        # Confidence 0.1 < threshold 0.82 → invisible, even if detector says is_enabled=True
        btn = FakeButtonDetector([
            ButtonState(ButtonId.PLAY, "Đánh", Rect(0,0,10,10), True, True, 0.1)
        ])
        res = run_ui_inference(source, _make_adapters(btn), config)
        play = res.predictions[0].buttons["play"]
        self.assertFalse(play.visible)
        self.assertFalse(play.enabled, "Invisible button must be disabled")

    # ------------------------------------------------------------------ #
    # Test Group 31-38: Adapter Validation + Frame-Wide Safe (Fix B)      #
    # ------------------------------------------------------------------ #

    def test_31_malformed_button_wrong_type_triggers_frame_safe(self):
        """Adapter returning non-ButtonState triggers frame-wide safe result."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        class BadButtonDetector:
            def detect(self, frame):
                return [{"button_id": "PLAY", "confidence": 0.9}]  # dict not ButtonState

        res = run_ui_inference(source, _make_adapters(BadButtonDetector()), config)
        self.assertGreater(len(res.failures), 0)
        self.assertEqual(res.failures[0].reason_code, "BUTTON_DETECTOR_ERROR")
        # Frame-wide safe: everything negative
        self.assertFalse(res.predictions[0].buttons["play"].visible)
        self.assertFalse(res.predictions[0].buttons["play"].enabled)
        self.assertEqual(res.predictions[0].ocr_fields[0].text, "UNKNOWN")
        self.assertIsNone(res.predictions[0].turn_owner)

    def test_32_malformed_button_nan_confidence_triggers_frame_safe(self):
        """ButtonState with NaN confidence triggers frame-wide safe result."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        class NaNConfDetector:
            def detect(self, frame):
                return [ButtonState(ButtonId.PLAY, "Đánh", Rect(0,0,10,10), True, True, float("nan"))]

        res = run_ui_inference(source, _make_adapters(NaNConfDetector()), config)
        self.assertGreater(len(res.failures), 0)
        self.assertEqual(res.failures[0].reason_code, "BUTTON_DETECTOR_ERROR")

    def test_33_malformed_button_bool_confidence_triggers_frame_safe(self):
        """ButtonState with bool confidence triggers frame-wide safe result."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        class BoolConfDetector:
            def detect(self, frame):
                return [ButtonState(ButtonId.PLAY, "Đánh", Rect(0,0,10,10), True, True, True)]

        res = run_ui_inference(source, _make_adapters(BoolConfDetector()), config)
        self.assertGreater(len(res.failures), 0)
        self.assertEqual(res.failures[0].reason_code, "BUTTON_DETECTOR_ERROR")

    def test_34_button_detector_exception_triggers_frame_safe(self):
        """Button detector exception causes frame-wide safe result."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        class CrashDetector:
            def detect(self, frame):
                raise RuntimeError("Button detector crash")

        res = run_ui_inference(source, _make_adapters(CrashDetector()), config)
        self.assertEqual(res.failures[0].reason_code, "BUTTON_DETECTOR_ERROR")
        self.assertFalse(res.predictions[0].buttons["play"].visible)
        self.assertEqual(res.predictions[0].ocr_fields[0].text, "UNKNOWN")
        self.assertIsNone(res.predictions[0].turn_owner)

    def test_35_ocr_nan_confidence_triggers_frame_safe(self):
        """OcrText with NaN confidence triggers frame-wide safe result."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        class NaNOcr:
            def recognize(self, frame, roi, whitelist=""):
                return OcrText("text", roi, float("nan"))

        res = run_ui_inference(source, _make_adapters(ocr_det=NaNOcr()), config)
        self.assertEqual(res.failures[0].reason_code, "OCR_DETECTOR_ERROR")
        self.assertEqual(res.predictions[0].ocr_fields[0].text, "UNKNOWN")
        self.assertIsNone(res.predictions[0].turn_owner)

    def test_36_ocr_wrong_text_type_triggers_frame_safe(self):
        """OcrText with non-str text field triggers frame-wide safe result."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        class BadTextOcr:
            def recognize(self, frame, roi, whitelist=""):
                return OcrText(123, roi, 0.9)  # type: ignore — int instead of str

        res = run_ui_inference(source, _make_adapters(ocr_det=BadTextOcr()), config)
        self.assertEqual(res.failures[0].reason_code, "OCR_DETECTOR_ERROR")

    def test_37_malformed_consensus_result_triggers_frame_safe(self):
        """Invalid TurnOwnerConsensusResult (matching > observed) causes frame-wide safe."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        class BadConsensus:
            def observe(self, bot_id, detection):
                # matching=5 > observed=3 violates invariant
                return TurnOwnerConsensusResult(None, 3, 5, 3)
            def reset(self, bot_id):
                pass

        res = run_ui_inference(source, _make_adapters(turn_con=BadConsensus()), config)
        self.assertEqual(res.failures[0].reason_code, "CONSENSUS_ERROR")
        self.assertIsNone(res.predictions[0].turn_owner)

    def test_38_ocr_low_confidence_unknown(self):
        """OCR outputs with confidence < minimum_confidence default to UNKNOWN text."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        ocr = FakeOcrDetector(OcrText("13", Rect(0,0,10,10), 0.1))  # 0.1 < 0.75 threshold
        res = run_ui_inference(source, _make_adapters(ocr_det=ocr), config)
        self.assertEqual(res.predictions[0].ocr_fields[0].text, "UNKNOWN")

    def test_39_ocr_text_not_modified(self):
        """Runner preserves exact OCR text without trimming or case-folding."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        ocr = FakeOcrDetector(OcrText("  MixedCase  ", Rect(0,0,10,10), 0.9))
        res = run_ui_inference(source, _make_adapters(ocr_det=ocr), config)
        self.assertEqual(res.predictions[0].ocr_fields[0].text, "  MixedCase  ")

    def test_40_turn_detector_exception_triggers_frame_safe(self):
        """Turn detector exception results in frame-wide safe result and reset."""
        cfg_p, src_dir = self._setup_valid_bundle()
        self._add_second_frame(src_dir)
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        turn_con = FakeTurnConsensus()
        res = run_ui_inference(
            source,
            _make_adapters(
                turn_det=FakeTurnDetector(RuntimeError("Turn crash")),
                turn_con=turn_con,
            ),
            config,
        )
        self.assertEqual(res.failures[0].reason_code, "TURN_DETECTOR_ERROR")
        # Safe prediction on failure frame
        self.assertIsNone(res.predictions[1].turn_owner)

    # ------------------------------------------------------------------ #
    # Test Group 41-44: Clock CLOCK_INVALID (Fix F)                       #
    # ------------------------------------------------------------------ #

    def test_41_clock_nan_triggers_clock_invalid(self):
        """NaN clock value causes CLOCK_INVALID failure and frame-wide safe result."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        res = run_ui_inference(source, _make_adapters(), config, clock=lambda: float("nan"))
        self.assertEqual(len(res.failures), 1)
        self.assertEqual(res.failures[0].reason_code, "CLOCK_INVALID")
        self.assertEqual(res.predictions[0].buttons["play"].visible, False)
        self.assertIsNone(res.predictions[0].turn_owner)

    def test_42_clock_infinity_triggers_clock_invalid(self):
        """Infinity clock value causes CLOCK_INVALID failure."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        res = run_ui_inference(source, _make_adapters(), config, clock=lambda: float("inf"))
        self.assertEqual(res.failures[0].reason_code, "CLOCK_INVALID")

    def test_43_clock_regression_triggers_clock_invalid(self):
        """Clock regression (t1 < t0) causes CLOCK_INVALID failure."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        # First call returns 5.0 (t0), second returns 0.0 (t1 < t0)
        times = iter([5.0, 0.0])
        def regressing_clock():
            return next(times)

        res = run_ui_inference(source, _make_adapters(), config, clock=regressing_clock)
        self.assertEqual(res.failures[0].reason_code, "CLOCK_INVALID")

    def test_44_clock_bool_triggers_clock_invalid(self):
        """Bool clock value causes CLOCK_INVALID failure."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        res = run_ui_inference(source, _make_adapters(), config, clock=lambda: True)
        self.assertEqual(res.failures[0].reason_code, "CLOCK_INVALID")

    # ------------------------------------------------------------------ #
    # Test Group 45-50: Output Isolation and Transactional Write (Fix G)  #
    # ------------------------------------------------------------------ #

    def test_45_four_required_output_files_written(self):
        """Writer produces all four required output files."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        res = run_ui_inference(source, _make_adapters(), config)

        out_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out_dir)
        write_ui_inference_result(res, out_dir)

        required = {"predictions.jsonl", "failures.jsonl", "inference_manifest.json", "run_metadata.json"}
        actual = {p.name for p in out_dir.iterdir()}
        self.assertEqual(actual, required, f"Expected {required}, got {actual}")

    def test_46_manifest_hashes_match_emitted_bytes(self):
        """inference_manifest.json output_sha256 hashes match the actual emitted file bytes."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        res = run_ui_inference(source, _make_adapters(), config)
        out_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out_dir)
        write_ui_inference_result(res, out_dir)

        manifest = json.loads((out_dir / "inference_manifest.json").read_bytes())
        pred_actual_sha = hashlib.sha256((out_dir / "predictions.jsonl").read_bytes()).hexdigest()
        fail_actual_sha = hashlib.sha256((out_dir / "failures.jsonl").read_bytes()).hexdigest()
        self.assertEqual(manifest["output_sha256"]["predictions.jsonl"], pred_actual_sha)
        self.assertEqual(manifest["output_sha256"]["failures.jsonl"], fail_actual_sha)

    def test_47_allow_nan_false_prevents_nan_in_artifacts(self):
        """Writer uses allow_nan=False; a prediction with NaN latency raises ValueError."""
        from bot.perception.ui_evaluation import UiPredictedButtonState, UiPredictedOcrField
        from bot.perception.ui_inference_runner import UiInferenceResult

        bad_pred = UiPredictionRecord(
            frame_id="f1",
            buttons=MappingProxyType({
                "play": UiPredictedButtonState(False, False, 0.0),
                "pass": UiPredictedButtonState(False, False, 0.0),
            }),
            ocr_fields=(),
            turn_owner=None,
            turn_observed_frames=1,
            turn_matching_frames=0,
            turn_latest_frame_matches=False,
            latency_ms=float("nan"),   # NaN latency
            source_commit="a" * 40,
            config_sha256="b" * 64,
        )
        result = UiInferenceResult(
            predictions=(bad_pred,),
            failures=(),
            source_commit="a" * 40,
            config_sha256="b" * 64,
            dataset_id="test",
            input_sha256={},
        )
        out_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out_dir)
        with self.assertRaises((ValueError, OverflowError), msg="Should raise on NaN in output"):
            write_ui_inference_result(result, out_dir)

    def test_48_transactional_cleanup_no_partial_output(self):
        """Failed write leaves no partial output in the final directory."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)
        res = run_ui_inference(source, _make_adapters(), config)

        out_parent = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out_parent)
        out_dir = out_parent / "output"

        # Patch write_bytes to fail halfway through by making dir read-only after staging
        import unittest.mock as mock
        original_rename = os.rename
        call_count = [0]

        def failing_rename(src, dst):
            call_count[0] += 1
            raise OSError("Simulated rename failure")

        with mock.patch("os.rename", side_effect=failing_rename):
            try:
                write_ui_inference_result(res, out_dir)
            except Exception:
                pass

        # Final output dir must not exist (no partial output)
        self.assertFalse(out_dir.exists(), "Partial output must not exist after transactional failure")
        # No stray staging dirs either
        stray = [p for p in out_parent.iterdir() if p.name.startswith(".stage_")]
        self.assertEqual(len(stray), 0, "Staging directories must be cleaned up on failure")

    def test_49_direct_writer_source_overlap_rejected(self):
        """Writer raises ValueError if output dir is inside or equal to source dir."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)
        res = run_ui_inference(source, _make_adapters(), config)

        # output inside source dir
        overlap_out = Path(src_dir) / "output"
        with self.assertRaises(ValueError, msg="Output inside source must be rejected"):
            write_ui_inference_result(res, overlap_out, source_path=src_dir)

    def test_50_run_metadata_excluded_from_deterministic_comparison(self):
        """run_metadata.json content differs between runs; predictions/failures/manifest are identical."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        class FixedAdapters:
            button_detector = FakeButtonDetector()
            ocr_detector = FakeOcrDetector()
            turn_detector = FakeTurnDetector()
            turn_consensus = FakeTurnConsensus()

        res = run_ui_inference(source, FixedAdapters(), config, clock=lambda: 1.0)

        out1 = Path(tempfile.mkdtemp())
        out2 = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out1)
        self.addCleanup(shutil.rmtree, out2)

        write_ui_inference_result(res, out1, run_start_ts=1000.0)
        write_ui_inference_result(res, out2, run_start_ts=2000.0)

        # The three deterministic artifacts must match
        for fn in ["predictions.jsonl", "failures.jsonl", "inference_manifest.json"]:
            self.assertEqual(
                (out1 / fn).read_bytes(),
                (out2 / fn).read_bytes(),
                f"{fn} must be byte-identical across runs",
            )

    # ------------------------------------------------------------------ #
    # Test Group 51-55: CLI Exit Codes 0/1/2/3 via subprocess (Fix H)    #
    # ------------------------------------------------------------------ #

    def _cli_path(self) -> str:
        return str(Path(__file__).parent.parent / "tools" / "run_perception_ui_replay.py")

    def _cli_env(self) -> dict:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent.parent)
        return env

    def test_51_cli_exit_3_invalid_missing_source(self):
        """CLI returns exit code 3 (INVALID) for missing source, with no traceback in stderr."""
        res = subprocess.run(
            [sys.executable, self._cli_path(),
             "--source", "nonexistent_dir",
             "--config", "nonexistent_cfg",
             "--output", "nonexistent_out"],
            env=self._cli_env(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 3, "Missing source must exit 3")
        self.assertIn("STATUS=INVALID", res.stdout)
        self.assertNotIn("Traceback", res.stderr)

    def test_52_cli_exit_0_complete(self):
        """CLI returns exit code 0 (COMPLETE) for a valid run with no failures."""
        cfg_p, src_dir = self._setup_valid_bundle()
        out_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out_dir)

        wrapper_script = Path(self.tmp_dir) / "run_complete.py"
        repo_root = str(Path(__file__).parent.parent)
        wrapper_script.write_text(
            f"""
import sys
sys.path.insert(0, {repr(repo_root)})
from tools.run_perception_ui_replay import main
from bot.perception.ocr import OcrText
from bot.perception.turn_owner import TurnOwnerConsensusResult

class ButtonDetector:
    def detect(self, frame):
        return ()
class OcrDetector:
    def recognize(self, frame, roi, whitelist=""):
        return OcrText("UNKNOWN", roi, 0.0)
class TurnDetector:
    def detect(self, frame, previous_card_counts, current_card_counts):
        raise AssertionError("turn detector must not run on first frame")
class Consensus:
    def reset(self, bot_id):
        pass
    def observe(self, bot_id, detection):
        return TurnOwnerConsensusResult(None, 1, 0, 3)
class FakeAdapters:
    button_detector = ButtonDetector()
    ocr_detector = OcrDetector()
    turn_detector = TurnDetector()
    turn_consensus = Consensus()

def factory(config):
    return FakeAdapters()

sys.exit(main(adapter_factory=factory))
""",
            encoding="utf-8",
        )

        res = subprocess.run(
            [sys.executable, str(wrapper_script),
             "--source", src_dir,
             "--config", str(cfg_p),
             "--output", str(out_dir)],
            env=self._cli_env(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Expected exit 0 (COMPLETE). stdout={res.stdout} stderr={res.stderr}")
        self.assertIn("STATUS=COMPLETE", res.stdout)
        self.assertNotIn("Traceback", res.stderr)
        self.assertEqual(
            {path.name for path in out_dir.iterdir()},
            {
                "predictions.jsonl",
                "failures.jsonl",
                "inference_manifest.json",
                "run_metadata.json",
            },
        )

    def test_53_cli_exit_2_no_data(self):
        """CLI returns exit code 2 (NO_DATA) when source has zero frames."""
        cfg_p, src_dir = self._setup_valid_bundle()
        out_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out_dir)

        # Rebuild source with zero frames in JSONL
        empty_fi = ""
        (Path(src_dir) / "frame_index.jsonl").write_text(empty_fi, encoding="utf-8", newline="\n")
        src = json.loads((Path(src_dir) / "source.json").read_text(encoding="utf-8"))
        src["frame_index_sha256"] = hashlib.sha256(empty_fi.encode("utf-8")).hexdigest()
        (Path(src_dir) / "source.json").write_text(json.dumps(src), encoding="utf-8")

        res = subprocess.run(
            [
                sys.executable,
                self._cli_path(),
                "--source",
                src_dir,
                "--config",
                str(cfg_p),
                "--output",
                str(out_dir),
            ],
            env=self._cli_env(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 2)
        self.assertIn("STATUS=NO_DATA", res.stdout)
        self.assertNotIn("Traceback", res.stderr)
        self.assertEqual(list(out_dir.iterdir()), [])

    def test_54_cli_exit_1_degraded(self):
        """CLI returns exit code 1 and safe artifacts after a detector failure."""
        cfg_p, src_dir = self._setup_valid_bundle()
        out_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out_dir)
        wrapper_script = Path(self.tmp_dir) / "run_degraded.py"
        repo_root = str(Path(__file__).parent.parent)
        wrapper_script.write_text(
            f"""
import sys
sys.path.insert(0, {repr(repo_root)})
from tools.run_perception_ui_replay import main

class ButtonDetector:
    def detect(self, frame):
        raise RuntimeError("deliberate detector failure")
class Unused:
    def recognize(self, *args, **kwargs):
        raise AssertionError("OCR must not run after button failure")
    def detect(self, *args, **kwargs):
        raise AssertionError("turn must not run after button failure")
    def observe(self, *args, **kwargs):
        raise AssertionError("consensus must not run after button failure")
    def reset(self, bot_id):
        pass
class FakeAdapters:
    button_detector = ButtonDetector()
    ocr_detector = Unused()
    turn_detector = Unused()
    turn_consensus = Unused()

def factory(config):
    return FakeAdapters()

sys.exit(main(adapter_factory=factory))
""",
            encoding="utf-8",
        )
        res = subprocess.run(
            [
                sys.executable,
                str(wrapper_script),
                "--source",
                src_dir,
                "--config",
                str(cfg_p),
                "--output",
                str(out_dir),
            ],
            env=self._cli_env(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("STATUS=DEGRADED", res.stdout)
        self.assertNotIn("Traceback", res.stderr)
        self.assertIn(
            "BUTTON_DETECTOR_ERROR",
            (out_dir / "failures.jsonl").read_text(encoding="utf-8"),
        )

    def test_55_cli_exit_3_overlap_check(self):
        """CLI returns exit code 3 (INVALID) when output dir is inside source dir."""
        cfg_p, src_dir = self._setup_valid_bundle()
        # output inside source
        overlap_out = str(Path(src_dir) / "results")
        res = subprocess.run(
            [sys.executable, self._cli_path(),
             "--source", src_dir,
             "--config", str(cfg_p),
             "--output", overlap_out],
            env=self._cli_env(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 3, "Output inside source must exit 3")
        self.assertIn("STATUS=INVALID", res.stdout)
        self.assertNotIn("Traceback", res.stderr)

    # ------------------------------------------------------------------ #
    # Test Group 56-58: Sanitized Failures + Misc                         #
    # ------------------------------------------------------------------ #

    def test_56_failure_details_do_not_contain_absolute_paths(self):
        """Failure details are sanitized: no absolute paths, no traceback strings."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        class PathLeakDetector:
            def detect(self, frame):
                # Raise with an absolute path in the message
                raise RuntimeError(f"File not found: C:\\secret\\data\\frame.png")

        res = run_ui_inference(source, _make_adapters(PathLeakDetector()), config)
        self.assertGreater(len(res.failures), 0)
        details = res.failures[0].details
        self.assertNotIn("C:\\secret", details, "Absolute Windows path must be sanitized")
        self.assertNotIn("frame.png", details, "Specific filenames must be sanitized in details")

    def test_57_ocr_field_order_preserved(self):
        """OCR field order in predictions matches config insertion order deterministically."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        res1 = run_ui_inference(source, _make_adapters(), config, clock=lambda: 1.0)
        res2 = run_ui_inference(source, _make_adapters(), config, clock=lambda: 1.0)

        fields1 = [f.field_id for f in res1.predictions[0].ocr_fields]
        fields2 = [f.field_id for f in res2.predictions[0].ocr_fields]
        self.assertEqual(fields1, fields2, "OCR field order must be deterministic across runs")

    def test_58_reset_at_session_and_sequence_boundary(self):
        """Consensus history resets at both session and sequence boundaries."""
        cfg_p, src_dir = self._setup_valid_bundle()
        self._add_second_frame(src_dir, seq_id="seq2", frame_index=1, ts=2000)
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        turn_con = FakeTurnConsensus()
        res = run_ui_inference(source, _make_adapters(turn_con=turn_con), config)
        # 1 reset at start + 1 reset at seq boundary = at least 2 resets
        self.assertGreaterEqual(turn_con.resets, 2)

    def test_59_hash_consistency_across_loads(self):
        """Config SHA-256 is identical across two loads of the same config file."""
        cfg_p, src_dir = self._setup_valid_bundle()
        config1 = load_ui_inference_config(cfg_p)
        config2 = load_ui_inference_config(cfg_p)
        self.assertEqual(config1.config_sha256, config2.config_sha256)

    def test_60_prediction_count_equals_frame_count(self):
        """Prediction records count always equals source frame count."""
        cfg_p, src_dir = self._setup_valid_bundle()
        self._add_second_frame(src_dir)
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        res = run_ui_inference(source, _make_adapters(), config)
        self.assertEqual(len(res.predictions), len(source.frame_index))

    def test_61_lazy_import_no_side_effects(self):
        """A clean subprocess imports the runner without importing pytesseract or ADB modules."""
        repo_root = str(Path(__file__).parent.parent)
        script = (
            "import sys;"
            f"sys.path.insert(0,{repo_root!r});"
            "import bot.perception.ui_inference_runner;"
            "blocked={'pytesseract','adb','ppadb'};"
            "assert not blocked.intersection(sys.modules)"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_62_explicit_invisible_button_never_becomes_visible(self):
        """A high-confidence detector state with is_visible=False remains invisible and disabled."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)
        hidden = ButtonState(
            ButtonId.PLAY,
            "play",
            Rect(0, 0, 10, 10),
            False,
            True,
            0.95,
        )
        result = run_ui_inference(
            source,
            _make_adapters(btn_det=FakeButtonDetector([hidden])),
            config,
            clock=lambda: 1.0,
        )
        self.assertFalse(result.predictions[0].buttons["play"].visible)
        self.assertFalse(result.predictions[0].buttons["play"].enabled)

    def test_63_first_frame_false_self_consensus_is_rejected(self):
        """The first frame cannot emit SELF without card-count delta or 3/4 consensus."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)
        false_consensus = FakeTurnConsensus(
            TurnOwnerConsensusResult(SeatPosition.SELF, 1, 0, 3)
        )
        result = run_ui_inference(
            source,
            _make_adapters(turn_con=false_consensus),
            config,
            clock=lambda: 1.0,
        )
        self.assertEqual(result.failures[0].reason_code, "CONSENSUS_ERROR")
        self.assertIsNone(result.predictions[0].turn_owner)

    def test_64_ocr_result_for_wrong_roi_is_rejected(self):
        """OCR output must refer to the exact ROI requested by the runner."""
        cfg_p, src_dir = self._setup_valid_bundle()
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)

        class WrongRoiOcr:
            def recognize(self, frame, roi, whitelist=""):
                return OcrText("13", Rect(0, 0, 1, 1), 0.9)

        result = run_ui_inference(
            source,
            _make_adapters(ocr_det=WrongRoiOcr()),
            config,
            clock=lambda: 1.0,
        )
        self.assertEqual(result.failures[0].reason_code, "OCR_DETECTOR_ERROR")
        self.assertEqual(result.predictions[0].ocr_fields[0].text, "UNKNOWN")

    def test_65_configured_total_input_limit_is_enforced(self):
        """A configured total-input limit rejects the source before inference."""
        cfg_p, src_dir = self._setup_valid_bundle()
        data = json.loads(Path(cfg_p).read_text(encoding="utf-8"))
        data["resource_limits"]["max_total_input_bytes"] = 100
        limited_path = self._write_file("config_total_limit.json", json.dumps(data))
        config = load_ui_inference_config(limited_path)
        with self.assertRaisesRegex(ValueError, "Total input bytes"):
            load_ui_inference_source(src_dir, resource_limits=config.resource_limits)

    def test_66_configured_image_pixel_limit_is_enforced(self):
        """A configured image-pixel limit is applied before inference."""
        cfg_p, src_dir = self._setup_valid_bundle()
        data = json.loads(Path(cfg_p).read_text(encoding="utf-8"))
        data["resource_limits"]["max_image_pixels"] = 100
        limited_path = self._write_file("config_pixel_limit.json", json.dumps(data))
        config = load_ui_inference_config(limited_path)
        with self.assertRaisesRegex(ValueError, "pixel limit"):
            load_ui_inference_source(src_dir, resource_limits=config.resource_limits)

    def test_67_positive_turn_requires_valid_hybrid_evidence_and_three_of_four(self):
        """A positive owner is emitted only with agreeing hybrid evidence and latest 3/4 consensus."""
        cfg_p, src_dir = self._setup_valid_bundle()
        self._add_second_frame(src_dir)
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)
        roi = Rect(10, 10, 20, 20)
        evidence = TurnOwnerEvidence(
            primary_signal=TurnPrimarySignal.AVATAR_HIGHLIGHT,
            primary_roi=roi,
            primary_confidence=0.9,
            secondary_confidence=0.8,
            signals_agree=True,
        )
        detection = TurnOwnerDetection(
            turn_owner=SeatPosition.SELF,
            evidence=evidence,
            primary=HighlightDetection(SeatPosition.SELF, 0.9, roi, {SeatPosition.SELF: 0.9}),
            secondary=CardCountDelta(SeatPosition.RIGHT, SeatPosition.SELF, 0.8, 1),
        )
        class SequenceConsensus:
            def __init__(self):
                self.calls = 0
            def reset(self, bot_id):
                pass
            def observe(self, bot_id, observed_detection):
                self.calls += 1
                if self.calls == 1:
                    return TurnOwnerConsensusResult(None, 1, 0, 3)
                return TurnOwnerConsensusResult(SeatPosition.SELF, 4, 3, 3)

        result = run_ui_inference(
            source,
            _make_adapters(
                turn_det=FakeTurnDetector(detection),
                turn_con=SequenceConsensus(),
            ),
            config,
            clock=lambda: 1.0,
        )
        self.assertIsNone(result.predictions[0].turn_owner)
        self.assertEqual(result.predictions[1].turn_owner, "SELF")
        self.assertTrue(result.predictions[1].turn_latest_frame_matches)

    def test_68_disagreeing_hybrid_evidence_cannot_emit_owner(self):
        """A detector owner with signals_agree=False produces a frame-wide safe result."""
        cfg_p, src_dir = self._setup_valid_bundle()
        self._add_second_frame(src_dir)
        source = load_ui_inference_source(src_dir)
        config = load_ui_inference_config(cfg_p)
        roi = Rect(10, 10, 20, 20)
        evidence = TurnOwnerEvidence(
            primary_signal=TurnPrimarySignal.AVATAR_HIGHLIGHT,
            primary_roi=roi,
            primary_confidence=0.9,
            secondary_confidence=0.8,
            signals_agree=False,
        )
        detection = TurnOwnerDetection(
            turn_owner=SeatPosition.SELF,
            evidence=evidence,
            primary=HighlightDetection(SeatPosition.SELF, 0.9, roi, {SeatPosition.SELF: 0.9}),
            secondary=CardCountDelta(SeatPosition.RIGHT, SeatPosition.SELF, 0.8, 1),
        )
        result = run_ui_inference(
            source,
            _make_adapters(turn_det=FakeTurnDetector(detection)),
            config,
            clock=lambda: 1.0,
        )
        self.assertEqual(result.failures[0].reason_code, "TURN_DETECTOR_ERROR")
        self.assertIsNone(result.predictions[1].turn_owner)

    def test_69_configured_line_limit_is_enforced_while_streaming(self):
        """The configured JSONL line-byte limit is used by source ingestion."""
        cfg_p, src_dir = self._setup_valid_bundle()
        data = json.loads(Path(cfg_p).read_text(encoding="utf-8"))
        data["resource_limits"]["max_line_length"] = 16
        limited_path = self._write_file("config_line_limit.json", json.dumps(data))
        config = load_ui_inference_config(limited_path)
        with self.assertRaisesRegex(ValueError, "max length"):
            load_ui_inference_source(src_dir, resource_limits=config.resource_limits)

    def test_70_configured_file_limit_is_checked_before_image_read(self):
        """The configured per-file limit rejects an oversized image at source loading."""
        cfg_p, src_dir = self._setup_valid_bundle()
        image_path = Path(src_dir) / "frames" / "f1.png"
        data = json.loads(Path(cfg_p).read_text(encoding="utf-8"))
        config_size = Path(cfg_p).stat().st_size
        self.assertGreater(image_path.stat().st_size, config_size)
        data["resource_limits"]["max_file_size_bytes"] = image_path.stat().st_size - 1
        limited_path = self._write_file("config_file_limit.json", json.dumps(data))
        config = load_ui_inference_config(limited_path)
        with self.assertRaisesRegex(ValueError, "exceeds limit"):
            load_ui_inference_source(src_dir, resource_limits=config.resource_limits)

    def test_71_configured_output_limit_is_enforced_by_writer(self):
        """The writer uses the configured output limit carried by the inference result."""
        cfg_p, src_dir = self._setup_valid_bundle()
        data = json.loads(Path(cfg_p).read_text(encoding="utf-8"))
        data["resource_limits"]["max_output_bytes"] = 1
        limited_path = self._write_file("config_output_limit.json", json.dumps(data))
        config = load_ui_inference_config(limited_path)
        source = load_ui_inference_source(src_dir, resource_limits=config.resource_limits)
        result = run_ui_inference(source, _make_adapters(), config, clock=lambda: 1.0)
        out_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out_dir)
        with self.assertRaisesRegex(ValueError, "Total output bytes"):
            write_ui_inference_result(result, out_dir)

    def test_72_cli_validates_config_before_loading_source(self):
        """CLI does not call the source loader when configuration validation fails."""
        from tools import run_perception_ui_replay as cli

        source_loader = mock.Mock(side_effect=AssertionError("source loader called"))
        with mock.patch.object(cli, "load_ui_inference_source", source_loader):
            exit_code = cli.main(
                [
                    "--source",
                    "missing-source",
                    "--config",
                    "missing-config",
                    "--output",
                    str(Path(self.tmp_dir) / "out"),
                ]
            )
        self.assertEqual(exit_code, 3)
        source_loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
