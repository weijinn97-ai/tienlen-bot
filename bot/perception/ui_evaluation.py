"""Deterministic evaluator for perception UI."""

import json
import math
import hashlib
import os
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Optional
from pathlib import Path
from enum import Enum


class UiEvaluationStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INVALID_BUNDLE = "INVALID_BUNDLE"


@dataclass(frozen=True)
class UiButtonState:
    visible: bool
    enabled: bool


@dataclass(frozen=True)
class UiPredictedButtonState:
    visible: bool
    enabled: bool
    confidence: float


@dataclass(frozen=True)
class UiOcrField:
    field_id: str
    expected_text: str
    critical: bool


@dataclass(frozen=True)
class UiPredictedOcrField:
    field_id: str
    text: str
    confidence: float


@dataclass(frozen=True)
class UiGroundTruthRecord:
    frame_id: str
    buttons: dict[str, UiButtonState]
    ocr_fields: list[UiOcrField]
    expected_turn_owner: Optional[str]
    critical_transition: bool
    negative_play_frame: bool


@dataclass(frozen=True)
class UiPredictionRecord:
    frame_id: str
    buttons: dict[str, UiPredictedButtonState]
    ocr_fields: list[UiPredictedOcrField]
    turn_owner: Optional[str]
    turn_observed_frames: int
    turn_matching_frames: int
    turn_latest_frame_matches: bool
    latency_ms: float
    source_commit: str
    config_sha256: str


@dataclass(frozen=True)
class UiFrameIndexRecord:
    frame_id: str
    relative_path: str
    sha256: str
    session_id: str
    sequence_id: str
    frame_index: int
    split: str
    review_status: str
    reviewer_id: str


@dataclass(frozen=True)
class UiEvaluationBundle:
    dataset_id: str
    locked: bool
    frame_index: list[UiFrameIndexRecord]
    ground_truth: list[UiGroundTruthRecord]
    predictions: list[UiPredictionRecord]


@dataclass(frozen=True)
class UiEvaluationConfig:
    ocr_confidence_threshold: float = 0.75
    min_test_frames: int = 1
    min_negative_play_frames: int = 2000
    min_test_sessions: int = 5
    min_test_sequences: int = 50
    min_button_exact_accuracy: float = 0.995
    min_critical_ocr_exact_accuracy: float = 0.99


@dataclass(frozen=True)
class UiFailureRecord:
    frame_id: str
    reason_code: str
    details: str


@dataclass(frozen=True)
class UiMetrics:
    test_frames: int
    test_sessions: int
    test_sequences: int
    unique_test_image_sha256: int
    button_state_total: int
    button_state_correct: int
    button_exact_accuracy: Optional[float]
    negative_play_frames: int
    false_play_enabled: int
    critical_ocr_total: int
    critical_ocr_correct: int
    critical_ocr_exact_accuracy: Optional[float]
    low_confidence_ocr_non_unknown: int
    turn_total: int
    turn_exact: int
    turn_exact_accuracy: Optional[float]
    false_my_turn: int
    critical_turn_total: int
    critical_consensus_violations: int
    latency_mean: Optional[float]
    latency_p50: Optional[float]
    latency_p95: Optional[float]
    latency_max: Optional[float]


@dataclass(frozen=True)
class UiEvaluationResult:
    status: str
    metrics: UiMetrics
    failures: list[UiFailureRecord]
    source_commit: str
    config_sha256: str


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    res: dict[str, Any] = {}
    for k, v in pairs:
        if type(k) is str and k in res:
            raise ValueError(f"Duplicate JSON key: {k!r}")
        res[k] = v
    return res


def _reject_json_constant(val: str) -> None:
    raise ValueError(f"Non-finite JSON constant not allowed: {val!r}")


def _load_json(path: Path) -> Any:
    try:
        content = path.read_text(encoding="utf-8")
        return json.loads(
            content,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except Exception as e:
        raise ValueError(f"Invalid JSON in {path.name}: {e}")


def _load_jsonl(path: Path) -> list[Any]:
    res = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > 500000:
            raise ValueError(f"Too many lines in {path.name}")
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(
                line,
                parse_constant=_reject_json_constant,
                object_pairs_hook=_reject_duplicate_json_keys,
            )
            res.append(obj)
    except Exception as e:
        raise ValueError(f"Invalid JSONL in {path.name}: {e}")
    return res


def _require_keys(d: dict, expected: set[str], name: str) -> None:
    if type(d) is not dict:
        raise ValueError(f"{name} must be dict")
    for k in d.keys():
        if type(k) is not str:
            raise ValueError(f"{name} string keys required")
    actual = set(d.keys())
    missing = expected - actual
    extra = actual - expected
    if missing:
        raise ValueError(f"{name} missing keys: {missing}")
    if extra:
        raise ValueError(f"{name} extra keys: {extra}")


def _require_type(v: Any, t: type, name: str) -> Any:
    if type(v) is not t:
        raise ValueError(f"{name} must be exactly {t.__name__}")
    return v


def _require_finite_float(v: Any, name: str) -> float:
    if type(v) is bool or not isinstance(v, (int, float)):
        raise ValueError(f"{name} must be number")
    f = float(v)
    if not math.isfinite(f):
        raise ValueError(f"{name} must be finite")
    return f


def _validate_path(rel_path: str) -> None:
    if "\\" in rel_path or ".." in rel_path or rel_path.startswith("/") or os.path.isabs(rel_path):
        raise ValueError(f"Invalid relative path: {rel_path}")


def load_ui_evaluation_bundle(bundle_dir: str) -> UiEvaluationBundle:
    base = Path(bundle_dir).resolve()
    bundle_json_path = base / "bundle.json"
    if not bundle_json_path.exists():
        raise ValueError("Missing bundle.json")
    
    b = _load_json(bundle_json_path)
    _require_keys(b, {"schema_version", "dataset_id", "locked", "viewport", "files", "sha256"}, "bundle.json")
    if _require_type(b["schema_version"], int, "schema_version") != 1:
        raise ValueError("Unsupported schema_version")
    dataset_id = _require_type(b["dataset_id"], str, "dataset_id")
    locked = _require_type(b["locked"], bool, "locked")
    
    vp = _require_type(b["viewport"], dict, "viewport")
    _require_keys(vp, {"width", "height"}, "viewport")
    _require_type(vp["width"], int, "viewport.width")
    _require_type(vp["height"], int, "viewport.height")

    files_dict = _require_type(b["files"], dict, "files")
    _require_keys(files_dict, {"frame_index", "ground_truth", "predictions"}, "files")
    
    sha256_dict = _require_type(b["sha256"], dict, "sha256")

    # Load and verify checksums
    loaded_data = {}
    for key, expected_filename in files_dict.items():
        _require_type(expected_filename, str, f"files.{key}")
        _validate_path(expected_filename)
        expected_sha = sha256_dict.get(expected_filename)
        if type(expected_sha) is not str:
            raise ValueError(f"Missing or invalid sha256 for {expected_filename}")
        
        file_path = base / expected_filename
        if not file_path.exists():
            raise ValueError(f"Missing file: {expected_filename}")
        
        actual_sha = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError(f"Checksum mismatch for {expected_filename}: expected {expected_sha}, got {actual_sha}")
        
        loaded_data[key] = _load_jsonl(file_path)

    # Parse Frame Index
    frame_index = []
    seen_frame_ids = set()
    for row in loaded_data["frame_index"]:
        _require_keys(row, {"frame_id", "relative_path", "sha256", "session_id", "sequence_id", "frame_index", "split", "review_status", "reviewer_id"}, "frame_index row")
        fid = _require_type(row["frame_id"], str, "frame_id")
        if not fid or any(ord(c) < 32 for c in fid):
            raise ValueError("Invalid frame_id")
        if fid in seen_frame_ids:
            raise ValueError(f"Duplicate frame_id in index: {fid}")
        seen_frame_ids.add(fid)
        
        _validate_path(_require_type(row["relative_path"], str, "relative_path"))
        split = _require_type(row["split"], str, "split")
        if split not in ("train", "val", "test"):
            raise ValueError(f"Invalid split: {split}")
        
        r_status = _require_type(row["review_status"], str, "review_status")
        if split == "test" and r_status != "APPROVED":
            raise ValueError(f"Test frame {fid} not APPROVED")
        
        frame_index.append(UiFrameIndexRecord(
            frame_id=fid,
            relative_path=row["relative_path"],
            sha256=_require_type(row["sha256"], str, "sha256"),
            session_id=_require_type(row["session_id"], str, "session_id"),
            sequence_id=_require_type(row["sequence_id"], str, "sequence_id"),
            frame_index=_require_type(row["frame_index"], int, "frame_index"),
            split=split,
            review_status=r_status,
            reviewer_id=_require_type(row["reviewer_id"], str, "reviewer_id")
        ))

    # Parse Ground Truth
    ground_truth = []
    gt_ids = set()
    for row in loaded_data["ground_truth"]:
        _require_keys(row, {"frame_id", "buttons", "ocr_fields", "expected_turn_owner", "critical_transition", "negative_play_frame"}, "ground_truth row")
        fid = _require_type(row["frame_id"], str, "frame_id")
        if fid in gt_ids:
            raise ValueError(f"Duplicate frame_id in ground_truth: {fid}")
        gt_ids.add(fid)

        buttons_raw = _require_type(row["buttons"], dict, "buttons")
        _require_keys(buttons_raw, {"play", "pass"}, "buttons")
        buttons = {}
        for b_name in ("play", "pass"):
            b_dict = _require_type(buttons_raw[b_name], dict, f"buttons.{b_name}")
            _require_keys(b_dict, {"visible", "enabled"}, f"buttons.{b_name}")
            buttons[b_name] = UiButtonState(
                visible=_require_type(b_dict["visible"], bool, "visible"),
                enabled=_require_type(b_dict["enabled"], bool, "enabled")
            )

        ocr_fields = []
        ocr_ids = set()
        for ocr_raw in _require_type(row["ocr_fields"], list, "ocr_fields"):
            _require_type(ocr_raw, dict, "ocr_field")
            _require_keys(ocr_raw, {"field_id", "expected_text", "critical"}, "ocr_field")
            oid = _require_type(ocr_raw["field_id"], str, "field_id")
            if oid in ocr_ids:
                raise ValueError(f"Duplicate ocr field_id: {oid}")
            ocr_ids.add(oid)
            ocr_fields.append(UiOcrField(
                field_id=oid,
                expected_text=_require_type(ocr_raw["expected_text"], str, "expected_text"),
                critical=_require_type(ocr_raw["critical"], bool, "critical")
            ))

        eto = row["expected_turn_owner"]
        if eto is not None:
            eto = _require_type(eto, str, "expected_turn_owner")
            if eto not in ("SELF", "LEFT", "TOP", "RIGHT"):
                raise ValueError(f"Invalid expected_turn_owner: {eto}")
        
        ground_truth.append(UiGroundTruthRecord(
            frame_id=fid,
            buttons=buttons,
            ocr_fields=ocr_fields,
            expected_turn_owner=eto,
            critical_transition=_require_type(row["critical_transition"], bool, "critical_transition"),
            negative_play_frame=_require_type(row["negative_play_frame"], bool, "negative_play_frame")
        ))

    # Parse Predictions
    predictions = []
    pred_ids = set()
    for row in loaded_data["predictions"]:
        _require_keys(row, {"frame_id", "buttons", "ocr_fields", "turn_owner", "turn_observed_frames", "turn_matching_frames", "turn_latest_frame_matches", "latency_ms", "source_commit", "config_sha256"}, "prediction row")
        fid = _require_type(row["frame_id"], str, "frame_id")
        if fid in pred_ids:
            raise ValueError(f"Duplicate frame_id in predictions: {fid}")
        pred_ids.add(fid)

        buttons_raw = _require_type(row["buttons"], dict, "buttons")
        _require_keys(buttons_raw, {"play", "pass"}, "buttons")
        buttons = {}
        for b_name in ("play", "pass"):
            b_dict = _require_type(buttons_raw[b_name], dict, f"buttons.{b_name}")
            _require_keys(b_dict, {"visible", "enabled", "confidence"}, f"buttons.{b_name}")
            buttons[b_name] = UiPredictedButtonState(
                visible=_require_type(b_dict["visible"], bool, "visible"),
                enabled=_require_type(b_dict["enabled"], bool, "enabled"),
                confidence=_require_finite_float(b_dict["confidence"], "confidence")
            )
        
        ocr_fields = []
        ocr_ids = set()
        for ocr_raw in _require_type(row["ocr_fields"], list, "ocr_fields"):
            _require_type(ocr_raw, dict, "ocr_field")
            _require_keys(ocr_raw, {"field_id", "text", "confidence"}, "ocr_field")
            oid = _require_type(ocr_raw["field_id"], str, "field_id")
            if oid in ocr_ids:
                raise ValueError(f"Duplicate ocr field_id: {oid}")
            ocr_ids.add(oid)
            ocr_fields.append(UiPredictedOcrField(
                field_id=oid,
                text=_require_type(ocr_raw["text"], str, "text"),
                confidence=_require_finite_float(ocr_raw["confidence"], "confidence")
            ))

        to = row["turn_owner"]
        if to is not None:
            to = _require_type(to, str, "turn_owner")
            if to not in ("SELF", "LEFT", "TOP", "RIGHT"):
                raise ValueError(f"Invalid turn_owner: {to}")

        latency = _require_finite_float(row["latency_ms"], "latency_ms")
        if latency < 0 or latency > 60000:
            raise ValueError(f"Invalid latency_ms: {latency}")

        sc = _require_type(row["source_commit"], str, "source_commit")
        csha = _require_type(row["config_sha256"], str, "config_sha256")
        if len(sc) != 40:
            raise ValueError("Invalid source_commit format")
        if len(csha) != 64:
            raise ValueError("Invalid config_sha256 format")

        predictions.append(UiPredictionRecord(
            frame_id=fid,
            buttons=buttons,
            ocr_fields=ocr_fields,
            turn_owner=to,
            turn_observed_frames=_require_type(row["turn_observed_frames"], int, "turn_observed_frames"),
            turn_matching_frames=_require_type(row["turn_matching_frames"], int, "turn_matching_frames"),
            turn_latest_frame_matches=_require_type(row["turn_latest_frame_matches"], bool, "turn_latest_frame_matches"),
            latency_ms=latency,
            source_commit=sc,
            config_sha256=csha
        ))

    # Consistency checks
    if set(seen_frame_ids) != set(gt_ids):
        raise ValueError("Mismatch between frame_index and ground_truth frame_ids")
    if set(seen_frame_ids) != set(pred_ids):
        raise ValueError("Mismatch between frame_index and predictions frame_ids")

    # Image duplicate check within test split
    test_images = set()
    for fr in frame_index:
        if fr.split == "test":
            if fr.sha256 in test_images:
                raise ValueError(f"Duplicate test image sha256: {fr.sha256}")
            test_images.add(fr.sha256)

    # Mixed commits/config check
    commits = set(p.source_commit for p in predictions)
    configs = set(p.config_sha256 for p in predictions)
    if len(commits) > 1:
        raise ValueError("Mixed source_commit in predictions")
    if len(configs) > 1:
        raise ValueError("Mixed config_sha256 in predictions")

    return UiEvaluationBundle(
        dataset_id=dataset_id,
        locked=locked,
        frame_index=frame_index,
        ground_truth=ground_truth,
        predictions=predictions
    )


def evaluate_ui_predictions(bundle: UiEvaluationBundle, config: UiEvaluationConfig) -> UiEvaluationResult:
    failures = []
    
    index_map = {r.frame_id: r for r in bundle.frame_index}
    gt_map = {r.frame_id: r for r in bundle.ground_truth}
    pred_map = {r.frame_id: r for r in bundle.predictions}

    test_frame_ids = [fid for fid, rec in index_map.items() if rec.split == "test"]
    
    test_sessions = len(set(index_map[fid].session_id for fid in test_frame_ids))
    test_sequences = len(set(f"{index_map[fid].session_id}_{index_map[fid].sequence_id}" for fid in test_frame_ids))
    unique_sha256 = len(set(index_map[fid].sha256 for fid in test_frame_ids))

    button_state_total = 0
    button_state_correct = 0
    negative_play_frames = 0
    false_play_enabled = 0

    critical_ocr_total = 0
    critical_ocr_correct = 0
    low_confidence_ocr_non_unknown = 0

    turn_total = 0
    turn_exact = 0
    false_my_turn = 0
    critical_turn_total = 0
    critical_consensus_violations = 0

    latencies = []

    for fid in test_frame_ids:
        gt = gt_map[fid]
        pr = pred_map[fid]
        
        latencies.append(pr.latency_ms)

        # Buttons
        for b_name in ("play", "pass"):
            button_state_total += 1
            if gt.buttons[b_name].visible == pr.buttons[b_name].visible and gt.buttons[b_name].enabled == pr.buttons[b_name].enabled:
                button_state_correct += 1
            else:
                failures.append(UiFailureRecord(fid, "BUTTON_MISMATCH", f"{b_name} expected {gt.buttons[b_name]}, got {pr.buttons[b_name]}"))
        
        if gt.negative_play_frame:
            negative_play_frames += 1
            if pr.buttons["play"].visible and pr.buttons["play"].enabled:
                false_play_enabled += 1
                failures.append(UiFailureRecord(fid, "FALSE_PLAY_ENABLED", "Play button falsely predicted as visible and enabled on a negative play frame"))

        # OCR
        gt_ocr_map = {o.field_id: o for o in gt.ocr_fields}
        pr_ocr_map = {o.field_id: o for o in pr.ocr_fields}
        if set(gt_ocr_map.keys()) != set(pr_ocr_map.keys()):
            raise ValueError(f"OCR fields mismatch for {fid}")

        for oid, gt_o in gt_ocr_map.items():
            pr_o = pr_ocr_map[oid]
            if pr_o.confidence < config.ocr_confidence_threshold:
                if pr_o.text != "UNKNOWN":
                    low_confidence_ocr_non_unknown += 1
                    failures.append(UiFailureRecord(fid, "LOW_CONFIDENCE_OCR_NON_UNKNOWN", f"Field {oid} has conf {pr_o.confidence} < {config.ocr_confidence_threshold} but text {pr_o.text!r} != 'UNKNOWN'"))
            if gt_o.critical:
                critical_ocr_total += 1
                if gt_o.expected_text == pr_o.text:
                    critical_ocr_correct += 1
                else:
                    failures.append(UiFailureRecord(fid, "CRITICAL_OCR_MISMATCH", f"Field {oid} expected {gt_o.expected_text!r}, got {pr_o.text!r}"))
        
        # Turn
        if gt.expected_turn_owner is not None:
            turn_total += 1
            if pr.turn_owner == gt.expected_turn_owner:
                turn_exact += 1
            else:
                failures.append(UiFailureRecord(fid, "TURN_MISMATCH", f"Expected {gt.expected_turn_owner}, got {pr.turn_owner}"))
        
        if pr.turn_owner == "SELF" and gt.expected_turn_owner != "SELF":
            false_my_turn += 1
            failures.append(UiFailureRecord(fid, "FALSE_MY_TURN", f"Falsely claimed turn ownership. Expected: {gt.expected_turn_owner}"))
        
        if gt.critical_transition:
            critical_turn_total += 1
            if pr.turn_owner is not None:
                if pr.turn_observed_frames < 4 or pr.turn_matching_frames < 3 or not pr.turn_latest_frame_matches:
                    critical_consensus_violations += 1
                    failures.append(UiFailureRecord(fid, "CRITICAL_CONSENSUS_VIOLATION", f"Critical transition output {pr.turn_owner} without reaching consensus. Obs:{pr.turn_observed_frames} Match:{pr.turn_matching_frames} Latest:{pr.turn_latest_frame_matches}"))

    latencies.sort()
    n_lat = len(latencies)
    if n_lat > 0:
        l_mean = sum(latencies) / n_lat
        l_p50 = latencies[int(n_lat * 0.5)]
        l_p95 = latencies[int(n_lat * 0.95)]
        l_max = latencies[-1]
    else:
        l_mean = l_p50 = l_p95 = l_max = None

    metrics = UiMetrics(
        test_frames=len(test_frame_ids),
        test_sessions=test_sessions,
        test_sequences=test_sequences,
        unique_test_image_sha256=unique_sha256,
        button_state_total=button_state_total,
        button_state_correct=button_state_correct,
        button_exact_accuracy=(button_state_correct / button_state_total) if button_state_total > 0 else None,
        negative_play_frames=negative_play_frames,
        false_play_enabled=false_play_enabled,
        critical_ocr_total=critical_ocr_total,
        critical_ocr_correct=critical_ocr_correct,
        critical_ocr_exact_accuracy=(critical_ocr_correct / critical_ocr_total) if critical_ocr_total > 0 else None,
        low_confidence_ocr_non_unknown=low_confidence_ocr_non_unknown,
        turn_total=turn_total,
        turn_exact=turn_exact,
        turn_exact_accuracy=(turn_exact / turn_total) if turn_total > 0 else None,
        false_my_turn=false_my_turn,
        critical_turn_total=critical_turn_total,
        critical_consensus_violations=critical_consensus_violations,
        latency_mean=l_mean,
        latency_p50=l_p50,
        latency_p95=l_p95,
        latency_max=l_max
    )

    failures.sort(key=lambda f: (f.frame_id, f.reason_code))

    sc = bundle.predictions[0].source_commit if bundle.predictions else ""
    csha = bundle.predictions[0].config_sha256 if bundle.predictions else ""

    # Gate logic
    is_insufficient = (
        not bundle.locked or
        metrics.test_frames < config.min_test_frames or
        metrics.negative_play_frames < config.min_negative_play_frames or
        metrics.test_sessions < config.min_test_sessions or
        metrics.test_sequences < config.min_test_sequences or
        metrics.button_exact_accuracy is None or
        metrics.critical_ocr_total == 0 or
        metrics.critical_ocr_exact_accuracy is None or
        metrics.turn_total == 0
    )

    is_fail = (
        failures or
        metrics.false_play_enabled > 0 or
        metrics.low_confidence_ocr_non_unknown > 0 or
        metrics.false_my_turn > 0 or
        metrics.critical_consensus_violations > 0 or
        (metrics.button_exact_accuracy is not None and metrics.button_exact_accuracy < config.min_button_exact_accuracy) or
        (metrics.critical_ocr_exact_accuracy is not None and metrics.critical_ocr_exact_accuracy < config.min_critical_ocr_exact_accuracy) or
        metrics.unique_test_image_sha256 != metrics.test_frames
    )

    if is_fail:
        status = UiEvaluationStatus.FAIL
    elif is_insufficient:
        status = UiEvaluationStatus.INSUFFICIENT_DATA
    else:
        status = UiEvaluationStatus.PASS

    return UiEvaluationResult(
        status=status.value,
        metrics=metrics,
        failures=failures,
        source_commit=sc,
        config_sha256=csha
    )


def write_ui_evaluation_result(result: UiEvaluationResult, output_dir: str) -> None:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    metrics_dict = {
        k: (v if v is not None else None)
        for k, v in result.metrics.__dict__.items()
    }

    manifest = {
        "status": result.status,
        "source_commit": result.source_commit,
        "config_sha256": result.config_sha256
    }

    meta = {
        "timestamp": time.time(),
        "output_dir": str(out)
    }

    def _write_json(obj: Any, filename: str) -> None:
        fd, temp_path = tempfile.mkstemp(dir=out, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                json.dump(obj, f, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
                f.write("\n")
            os.replace(temp_path, out / filename)
        except Exception:
            os.unlink(temp_path)
            raise

    def _write_jsonl(rows: list[Any], filename: str) -> None:
        fd, temp_path = tempfile.mkstemp(dir=out, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                for r in rows:
                    json.dump(r, f, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
                    f.write("\n")
            os.replace(temp_path, out / filename)
        except Exception:
            os.unlink(temp_path)
            raise

    _write_json(metrics_dict, "metrics.json")
    _write_jsonl([f.__dict__ for f in result.failures], "failures.jsonl")
    _write_json(manifest, "evaluated_manifest.json")
    _write_json(meta, "run_metadata.json")
