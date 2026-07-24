import json
import math
import hashlib
import os
import sys
import time
import re
import tempfile
from dataclasses import dataclass
from typing import Any, Optional, Mapping, Tuple, Protocol, List, Dict
from pathlib import Path
from types import MappingProxyType
import cv2
import numpy as np

from contracts.interfaces import Rect, ButtonId, ButtonState, SeatPosition
from bot.perception.turn_owner import (
    TurnOwnerDetection,
    TurnOwnerConsensusResult,
    NormalizedRect,
    HighlightDetection,
    CardCountDelta,
)
from bot.perception.ocr import OcrText
from bot.perception.ui_evaluation import (
    UiPredictionRecord,
    UiFailureRecord,
    UiPredictedButtonState,
    UiPredictedOcrField,
)

# ------------------------------------------------------------------ #
# Protocols / Interfaces                                              #
# ------------------------------------------------------------------ #

class ButtonDetectorAdapter(Protocol):
    def detect(self, frame: np.ndarray) -> Tuple[ButtonState, ...]:
        ...

class OcrAdapter(Protocol):
    def recognize(self, frame: np.ndarray, roi: Rect, *, whitelist: str = "") -> OcrText:
        ...

class HybridTurnDetectorAdapter(Protocol):
    def detect(
        self,
        frame: np.ndarray,
        *,
        previous_card_counts: Mapping[SeatPosition, int],
        current_card_counts: Mapping[SeatPosition, int],
    ) -> TurnOwnerDetection:
        ...

class TurnConsensusAdapter(Protocol):
    def observe(self, bot_id: str, detection: TurnOwnerDetection) -> TurnOwnerConsensusResult:
        ...
    def reset(self, bot_id: str) -> None:
        ...

# ------------------------------------------------------------------ #
# Immutable Dataclasses                                             #
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class UiInferenceFrameRecord:
    frame_id: str
    relative_path: str
    sha256: str
    session_id: str
    sequence_id: str
    frame_index: int
    capture_ts_ms: int
    player_card_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "player_card_counts", MappingProxyType(dict(self.player_card_counts)))

@dataclass(frozen=True)
class UiInferenceSource:
    dataset_id: str
    viewport: Mapping[str, int]
    frame_index: Tuple[UiInferenceFrameRecord, ...]
    input_sha256: Mapping[str, str]
    source_dir: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "viewport", MappingProxyType(dict(self.viewport)))
        object.__setattr__(self, "frame_index", tuple(self.frame_index))
        object.__setattr__(self, "input_sha256", MappingProxyType(dict(self.input_sha256)))

@dataclass(frozen=True)
class OcrFieldConfig:
    roi: Rect
    whitelist: str

@dataclass(frozen=True)
class ButtonTemplateConfig:
    filename: str
    search_roi: NormalizedRect
    threshold: float
    sha256: str
    image: np.ndarray
    button_id: ButtonId
    label: str
    is_enabled: bool

@dataclass(frozen=True)
class UiInferenceConfig:
    schema_version: int
    viewport: Mapping[str, int]
    ocr_minimum_confidence: float
    ocr_fields: Mapping[str, OcrFieldConfig]
    button_template_dir: str
    button_templates: Mapping[str, ButtonTemplateConfig]
    consensus_history_size: int
    consensus_required_matches: int
    resource_limits: Mapping[str, Any]
    source_commit: str
    config_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "viewport", MappingProxyType(dict(self.viewport)))
        object.__setattr__(self, "ocr_fields", MappingProxyType(dict(self.ocr_fields)))
        object.__setattr__(self, "button_templates", MappingProxyType(dict(self.button_templates)))
        object.__setattr__(self, "resource_limits", MappingProxyType(dict(self.resource_limits)))

@dataclass(frozen=True)
class UiInferenceResult:
    predictions: Tuple[UiPredictionRecord, ...]
    failures: Tuple[UiFailureRecord, ...]
    source_commit: str
    config_sha256: str
    dataset_id: str
    input_sha256: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "predictions", tuple(self.predictions))
        object.__setattr__(self, "failures", tuple(self.failures))
        object.__setattr__(self, "input_sha256", MappingProxyType(dict(self.input_sha256)))

# ------------------------------------------------------------------ #
# Internal Helpers                                                  #
# ------------------------------------------------------------------ #

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

def _load_jsonl(path: Path, max_records: int = 500000, max_line_len: int = 1048576) -> list[Any]:
    res = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                if idx >= max_records:
                    raise ValueError(f"Too many lines in {path.name} (exceeded {max_records} limit)")
                if len(line) > max_line_len:
                    raise ValueError(f"Line {idx + 1} in {path.name} exceeds max length of {max_line_len}")
                line_stripped = line.strip()
                if not line_stripped:
                    raise ValueError(f"Line {idx + 1} in {path.name} is blank or whitespace-only")
                obj = json.loads(
                    line_stripped,
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

def _is_safe_id(val: str) -> bool:
    if not val or len(val) > 128:
        return False
    return bool(re.match(r"^[A-Za-z0-9._-]+$", val))

def _is_valid_hex(val: str, length: int) -> bool:
    if len(val) != length:
        return False
    return all(c in "0123456789abcdef" for c in val)

def _validate_path(rel_path: str, base: Path, resolved_paths: dict[str, str]) -> Path:
    if not rel_path:
        raise ValueError("Empty path path")
    # Strict POSIX checks
    if "\\" in rel_path:
        raise ValueError(f"Backslashes not allowed: {rel_path}")
    if rel_path.startswith("/") or rel_path.startswith("./") or "/../" in rel_path or rel_path.endswith("/..") or rel_path.startswith("../"):
        raise ValueError(f"Traversal characters not allowed: {rel_path}")

    parts = rel_path.split("/")
    if any(p == ".." or p == "." for p in parts):
        raise ValueError(f"Relative path segment escape not allowed: {rel_path}")

    full_path = Path(base / rel_path).resolve()
    try:
        full_path.relative_to(base.resolve())
    except ValueError:
        raise ValueError(f"Escape path detected: {rel_path}")

    canonical = str(full_path).lower()
    if canonical in resolved_paths and resolved_paths[canonical] != rel_path:
        raise ValueError(f"Path collision detected: {rel_path} and {resolved_paths[canonical]}")
    resolved_paths[canonical] = rel_path
    return full_path

def _check_forbidden_keys(data: Any) -> None:
    forbidden = {"ground_truth", "label", "reviewer"}
    if isinstance(data, dict):
        for k, v in data.items():
            k_str = str(k).lower()
            if any(f in k_str for f in forbidden) or k_str.startswith("expected_"):
                raise ValueError(f"Forbidden key detected: {k}")
            _check_forbidden_keys(v)
    elif isinstance(data, list) or isinstance(data, tuple):
        for item in data:
            _check_forbidden_keys(item)
    elif isinstance(data, str):
        val_lower = data.lower()
        if any(f in val_lower for f in forbidden) or val_lower.startswith("expected_"):
            raise ValueError(f"Forbidden value detected: {data}")

# ------------------------------------------------------------------ #
# Public Loader API                                                 #
# ------------------------------------------------------------------ #

def load_ui_inference_source(source_dir: str | Path) -> UiInferenceSource:
    base = Path(source_dir).resolve()
    source_json_path = base / "source.json"
    if not source_json_path.exists():
        raise ValueError("Missing source.json")

    source_json_bytes = source_json_path.read_bytes()
    source_sha = hashlib.sha256(source_json_bytes).hexdigest()

    b = _load_json(source_json_path)
    _check_forbidden_keys(b)

    _require_keys(b, {"schema_version", "dataset_id", "viewport", "frame_index", "frame_index_sha256"}, "source.json")
    if _require_type(b["schema_version"], int, "schema_version") != 1:
        raise ValueError("Unsupported schema_version")

    dataset_id = _require_type(b["dataset_id"], str, "dataset_id")
    if not _is_safe_id(dataset_id):
        raise ValueError("Invalid dataset_id")

    vp_raw = _require_type(b["viewport"], dict, "viewport")
    _require_keys(vp_raw, {"width", "height"}, "viewport")
    vp = {
        "width": _require_type(vp_raw["width"], int, "viewport.width"),
        "height": _require_type(vp_raw["height"], int, "viewport.height")
    }
    if vp["width"] <= 0 or vp["height"] <= 0:
        raise ValueError("Viewport dimensions must be positive")

    frame_index_rel = _require_type(b["frame_index"], str, "frame_index")
    frame_index_sha_expected = _require_type(b["frame_index_sha256"], str, "frame_index_sha256")
    if not _is_valid_hex(frame_index_sha_expected, 64):
        raise ValueError("Invalid frame_index_sha256 format")

    resolved_paths: dict[str, str] = {}
    frame_index_path = _validate_path(frame_index_rel, base, resolved_paths)

    frame_index_bytes = frame_index_path.read_bytes()
    frame_index_sha_actual = hashlib.sha256(frame_index_bytes).hexdigest()
    if frame_index_sha_actual != frame_index_sha_expected:
        raise ValueError(f"Checksum mismatch for frame index: expected {frame_index_sha_expected}, got {frame_index_sha_actual}")

    input_sha256 = {
        "source.json": source_sha,
        frame_index_rel: frame_index_sha_actual
    }

    raw_records = _load_jsonl(frame_index_path)
    _check_forbidden_keys(raw_records)

    frame_index = []
    seen_frame_ids = set()
    seen_image_shas = set()
    last_seq_idx: dict[Tuple[str, str], int] = {}
    last_seq_ts: dict[Tuple[str, str], int] = {}
    active_sequences: dict[str, str] = {}

    for row in raw_records:
        _require_keys(row, {"frame_id", "relative_path", "sha256", "session_id", "sequence_id", "frame_index", "capture_ts_ms", "player_card_counts"}, "frame_index row")

        fid = _require_type(row["frame_id"], str, "frame_id")
        if not _is_safe_id(fid):
            raise ValueError("Invalid frame_id")
        if fid in seen_frame_ids:
            raise ValueError(f"Duplicate frame_id in index: {fid}")
        seen_frame_ids.add(fid)

        rel_path = _require_type(row["relative_path"], str, "relative_path")
        if rel_path in input_sha256:
            raise ValueError(f"Duplicate or aliased image path: {rel_path}")

        full_path = _validate_path(rel_path, base, resolved_paths)
        if not full_path.exists():
            raise ValueError(f"Image path does not exist: {rel_path}")

        sha = _require_type(row["sha256"], str, "sha256")
        if not _is_valid_hex(sha, 64):
            raise ValueError("Invalid image sha256")
        if sha in seen_image_shas:
            raise ValueError(f"Duplicate image hash detected: {sha}")
        seen_image_shas.add(sha)

        # Verify image checksum
        img_bytes = full_path.read_bytes()
        actual_img_sha = hashlib.sha256(img_bytes).hexdigest()
        if actual_img_sha != sha:
            raise ValueError(f"Checksum mismatch for image {rel_path}")

        # Verify image shape/viewport
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Corrupt or invalid image {rel_path}")
        h, w = img.shape[:2]
        if w != vp["width"] or h != vp["height"]:
            raise ValueError(f"Image dimensions mismatch for {rel_path}: {w}x{h} != {vp['width']}x{vp['height']}")

        input_sha256[rel_path] = sha

        sid = _require_type(row["session_id"], str, "session_id")
        seqid = _require_type(row["sequence_id"], str, "sequence_id")
        if not _is_safe_id(sid) or not _is_safe_id(seqid):
            raise ValueError("Invalid session_id or sequence_id")

        # Sequence interleaving check
        if sid in active_sequences:
            if active_sequences[sid] != seqid:
                seen_sequences_in_session = set(k[1] for k in last_seq_idx.keys() if k[0] == sid)
                if seqid in seen_sequences_in_session:
                    raise ValueError(f"Interleaved sequence detected: {seqid} in session {sid}")
        active_sequences[sid] = seqid

        f_idx = _require_type(row["frame_index"], int, "frame_index")
        if f_idx < 0:
            raise ValueError("frame_index must be nonnegative")

        ts = _require_type(row["capture_ts_ms"], int, "capture_ts_ms")
        if ts < 0:
            raise ValueError("capture_ts_ms must be nonnegative")

        seq_key = (sid, seqid)
        if seq_key in last_seq_idx:
            if f_idx <= last_seq_idx[seq_key]:
                raise ValueError("frame_index must be strictly increasing per sequence")
            if ts <= last_seq_ts[seq_key]:
                raise ValueError("capture_ts_ms must be strictly increasing per sequence")
        last_seq_idx[seq_key] = f_idx
        last_seq_ts[seq_key] = ts

        # Validate card counts
        cc_raw = _require_type(row["player_card_counts"], dict, "player_card_counts")
        _require_keys(cc_raw, {"SELF", "LEFT", "TOP", "RIGHT"}, "player_card_counts")
        cc = {}
        for pos_str, count in cc_raw.items():
            if type(count) is not int or type(count) is bool:
                raise ValueError(f"Card count for {pos_str} must be exactly int")
            if not 0 <= count <= 13:
                raise ValueError(f"Card count for {pos_str} must be in [0, 13]")
            cc[pos_str] = count

        frame_index.append(UiInferenceFrameRecord(
            frame_id=fid,
            relative_path=rel_path,
            sha256=sha,
            session_id=sid,
            sequence_id=seqid,
            frame_index=f_idx,
            capture_ts_ms=ts,
            player_card_counts=cc
        ))

    return UiInferenceSource(
        dataset_id=dataset_id,
        viewport=MappingProxyType(vp),
        frame_index=tuple(frame_index),
        input_sha256=MappingProxyType(input_sha256),
        source_dir=str(base)
    )


def load_ui_inference_config(config_path: str | Path) -> UiInferenceConfig:
    p = Path(config_path).resolve()
    if not p.exists():
        raise ValueError("Missing config file")

    config_bytes = p.read_bytes()
    config_dict = _load_json(p)
    _check_forbidden_keys(config_dict)

    _require_keys(config_dict, {
        "schema_version",
        "viewport",
        "ocr_minimum_confidence",
        "ocr_fields",
        "button_template_dir",
        "button_templates",
        "consensus",
        "resource_limits",
        "source_commit"
    }, "config.json")

    if _require_type(config_dict["schema_version"], int, "schema_version") != 1:
        raise ValueError("Unsupported schema_version in config")

    vp_raw = _require_type(config_dict["viewport"], dict, "viewport")
    _require_keys(vp_raw, {"width", "height"}, "viewport")
    vp = {
        "width": _require_type(vp_raw["width"], int, "viewport.width"),
        "height": _require_type(vp_raw["height"], int, "viewport.height")
    }
    if vp["width"] <= 0 or vp["height"] <= 0:
        raise ValueError("Viewport dimensions must be positive")

    ocr_min_conf = _require_finite_float(config_dict["ocr_minimum_confidence"], "ocr_minimum_confidence")
    if not 0.0 <= ocr_min_conf <= 1.0:
        raise ValueError("ocr_minimum_confidence out of bounds [0.0, 1.0]")

    # Validate OCR fields
    ocr_fields_raw = _require_type(config_dict["ocr_fields"], dict, "ocr_fields")
    ocr_fields = {}
    for oid, o_cfg in ocr_fields_raw.items():
        if not _is_safe_id(oid):
            raise ValueError(f"Invalid OCR field ID: {oid}")
        _require_keys(o_cfg, {"roi", "whitelist"}, f"ocr_fields.{oid}")
        roi_raw = _require_type(o_cfg["roi"], dict, f"ocr_fields.{oid}.roi")
        _require_keys(roi_raw, {"x", "y", "width", "height"}, f"ocr_fields.{oid}.roi")
        roi = Rect(
            x=_require_type(roi_raw["x"], int, f"ocr_fields.{oid}.roi.x"),
            y=_require_type(roi_raw["y"], int, f"ocr_fields.{oid}.roi.y"),
            width=_require_type(roi_raw["width"], int, f"ocr_fields.{oid}.roi.width"),
            height=_require_type(roi_raw["height"], int, f"ocr_fields.{oid}.roi.height")
        )
        if roi.x < 0 or roi.y < 0 or roi.width <= 0 or roi.height <= 0:
            raise ValueError(f"OCR ROI dimensions must be positive/nonnegative in {oid}")
        if roi.x + roi.width > vp["width"] or roi.y + roi.height > vp["height"]:
            raise ValueError(f"OCR ROI fits outside the viewport in {oid}")

        whitelist = _require_type(o_cfg["whitelist"], str, f"ocr_fields.{oid}.whitelist")
        ocr_fields[oid] = OcrFieldConfig(roi=roi, whitelist=whitelist)

    # Validate Button templates
    btn_dir_rel = _require_type(config_dict["button_template_dir"], str, "button_template_dir")
    resolved_paths: dict[str, str] = {}
    btn_dir_path = _validate_path(btn_dir_rel, p.parent, resolved_paths)

    btn_templates_raw = _require_type(config_dict["button_templates"], dict, "button_templates")
    button_templates = {}
    for bid_str, b_cfg in btn_templates_raw.items():
        if bid_str.startswith("play"):
            bid = ButtonId.PLAY
            label = "Đánh"
            is_enabled = "disabled" not in bid_str.lower() and "disabled" not in b_cfg.get("filename", "").lower()
        elif bid_str.startswith("pass"):
            bid = ButtonId.PASS
            label = "Bỏ Lượt"
            is_enabled = "disabled" not in bid_str.lower() and "disabled" not in b_cfg.get("filename", "").lower()
        else:
            raise ValueError(f"Unknown or unsupported button ID: {bid_str}")

        _require_keys(b_cfg, {"filename", "search_roi", "threshold", "sha256"}, f"button_templates.{bid_str}")
        filename = _require_type(b_cfg["filename"], str, f"button_templates.{bid_str}.filename")
        if "\\" in filename or "/" in filename:
            raise ValueError(f"Button filename path traversal not allowed: {filename}")

        tmpl_file = btn_dir_path / filename
        if not tmpl_file.exists():
            raise ValueError(f"Button template file not found: {filename}")

        expected_tmpl_sha = _require_type(b_cfg["sha256"], str, f"button_templates.{bid_str}.sha256")
        if not _is_valid_hex(expected_tmpl_sha, 64):
            raise ValueError(f"Invalid template sha256 format for {bid_str}")

        tmpl_bytes = tmpl_file.read_bytes()
        actual_tmpl_sha = hashlib.sha256(tmpl_bytes).hexdigest()
        if actual_tmpl_sha != expected_tmpl_sha:
            raise ValueError(f"Template checksum mismatch for {bid_str}")

        arr = np.frombuffer(tmpl_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Corrupt button template image for {bid_str}")

        roi_raw = _require_type(b_cfg["search_roi"], dict, f"button_templates.{bid_str}.search_roi")
        _require_keys(roi_raw, {"x", "y", "width", "height"}, f"button_templates.{bid_str}.search_roi")
        search_roi = NormalizedRect(
            x=_require_finite_float(roi_raw["x"], f"button_templates.{bid_str}.search_roi.x"),
            y=_require_finite_float(roi_raw["y"], f"button_templates.{bid_str}.search_roi.y"),
            width=_require_finite_float(roi_raw["width"], f"button_templates.{bid_str}.search_roi.width"),
            height=_require_finite_float(roi_raw["height"], f"button_templates.{bid_str}.search_roi.height")
        )
        if not (0.0 <= search_roi.x <= 1.0) or not (0.0 <= search_roi.y <= 1.0) or not (0.0 < search_roi.width <= 1.0) or not (0.0 < search_roi.height <= 1.0):
            raise ValueError(f"search_roi bounds invalid for {bid_str}")
        if search_roi.x + search_roi.width > 1.0 or search_roi.y + search_roi.height > 1.0:
            raise ValueError(f"search_roi fits outside normalized frame in {bid_str}")

        threshold = _require_finite_float(b_cfg["threshold"], f"button_templates.{bid_str}.threshold")
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Button template threshold out of bounds in {bid_str}")

        button_templates[bid_str] = ButtonTemplateConfig(
            filename=filename,
            search_roi=search_roi,
            threshold=threshold,
            sha256=expected_tmpl_sha,
            image=img,
            button_id=bid,
            label=label,
            is_enabled=is_enabled
        )

    # Validate consensus
    consensus_raw = _require_type(config_dict["consensus"], dict, "consensus")
    _require_keys(consensus_raw, {"history_size", "required_matches"}, "consensus")
    consensus_history_size = _require_type(consensus_raw["history_size"], int, "consensus.history_size")
    consensus_required_matches = _require_type(consensus_raw["required_matches"], int, "consensus.required_matches")
    if consensus_history_size != 4 or consensus_required_matches != 3:
        raise ValueError("Consensus history_size must be 4 and required_matches must be 3 exactly")

    # Resource limits
    limits_raw = _require_type(config_dict["resource_limits"], dict, "resource_limits")
    _require_keys(limits_raw, {"max_file_size_bytes", "max_records", "max_line_length"}, "resource_limits")
    resource_limits = {
        "max_file_size_bytes": _require_type(limits_raw["max_file_size_bytes"], int, "resource_limits.max_file_size_bytes"),
        "max_records": _require_type(limits_raw["max_records"], int, "resource_limits.max_records"),
        "max_line_length": _require_type(limits_raw["max_line_length"], int, "resource_limits.max_line_length")
    }
    if resource_limits["max_file_size_bytes"] <= 0 or resource_limits["max_records"] <= 0 or resource_limits["max_line_length"] <= 0:
        raise ValueError("Resource limits must be positive integers")

    source_commit = _require_type(config_dict["source_commit"], str, "source_commit")
    if not _is_valid_hex(source_commit, 40):
        raise ValueError("Invalid source_commit format in config")

    serializable = {
        "schema_version": config_dict["schema_version"],
        "viewport": vp,
        "ocr_minimum_confidence": ocr_min_conf,
        "ocr_fields": {
            oid: {
                "roi": {"x": o_cfg.roi.x, "y": o_cfg.roi.y, "width": o_cfg.roi.width, "height": o_cfg.roi.height},
                "whitelist": o_cfg.whitelist
            } for oid, o_cfg in ocr_fields.items()
        },
        "button_template_dir": btn_dir_rel,
        "button_templates": {
            bid_str: {
                "filename": b_cfg.filename,
                "search_roi": {"x": b_cfg.search_roi.x, "y": b_cfg.search_roi.y, "width": b_cfg.search_roi.width, "height": b_cfg.search_roi.height},
                "threshold": b_cfg.threshold,
                "sha256": b_cfg.sha256
            } for bid_str, b_cfg in button_templates.items()
        },
        "consensus": {
            "history_size": consensus_history_size,
            "required_matches": consensus_required_matches
        },
        "resource_limits": resource_limits,
        "source_commit": source_commit
    }
    config_sha = hashlib.sha256(json.dumps(serializable, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode("utf-8")).hexdigest()

    return UiInferenceConfig(
        schema_version=1,
        viewport=MappingProxyType(vp),
        ocr_minimum_confidence=ocr_min_conf,
        ocr_fields=MappingProxyType(ocr_fields),
        button_template_dir=btn_dir_rel,
        button_templates=MappingProxyType(button_templates),
        consensus_history_size=consensus_history_size,
        consensus_required_matches=consensus_required_matches,
        resource_limits=MappingProxyType(resource_limits),
        source_commit=source_commit,
        config_sha256=config_sha
    )

# ------------------------------------------------------------------ #
# Public Inference Engine                                            #
# ------------------------------------------------------------------ #

def run_ui_inference(
    source: UiInferenceSource,
    adapters: Any,
    config: UiInferenceConfig,
    clock: Optional[Any] = None
) -> UiInferenceResult:
    if clock is None:
        clock = time.monotonic

    predictions = []
    failures = []
    bot_id = "bot"

    adapters.turn_consensus.reset(bot_id)

    last_session_id = None
    last_sequence_id = None
    previous_card_counts = None

    for rec in source.frame_index:
        fid = rec.frame_id

        if rec.session_id != last_session_id or rec.sequence_id != last_sequence_id:
            adapters.turn_consensus.reset(bot_id)
            previous_card_counts = None

        last_session_id = rec.session_id
        last_sequence_id = rec.sequence_id

        rel_path = rec.relative_path
        img_path = Path(source.source_dir) / rel_path

        try:
            img_bytes = img_path.read_bytes()
            arr = np.frombuffer(img_bytes, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError("cv2.imdecode returned None")
        except Exception as e:
            failures.append(UiFailureRecord(fid, "IMAGE_LOAD_ERROR", f"Failed to load frame image: {e}"))
            predictions.append(UiPredictionRecord(
                frame_id=fid,
                buttons=MappingProxyType({
                    "play": UiPredictedButtonState(visible=False, enabled=False, confidence=0.0),
                    "pass": UiPredictedButtonState(visible=False, enabled=False, confidence=0.0)
                }),
                ocr_fields=tuple(UiPredictedOcrField(oid, "UNKNOWN", 0.0) for oid in config.ocr_fields.keys()),
                turn_owner=None,
                turn_observed_frames=1,
                turn_matching_frames=0,
                turn_latest_frame_matches=False,
                latency_ms=0.0,
                source_commit=config.source_commit,
                config_sha256=config.config_sha256
            ))
            adapters.turn_consensus.reset(bot_id)
            previous_card_counts = None
            continue

        t0 = clock()

        # 1. Run Button detection
        buttons = {}
        try:
            detected_buttons = adapters.button_detector.detect(frame)
            detected_map = {b.button_id: b for b in detected_buttons}
            for bid_str in ("play", "pass"):
                bid = ButtonId.PLAY if bid_str == "play" else ButtonId.PASS
                if bid in detected_map:
                    b_state = detected_map[bid]
                    visible = b_state.confidence >= config.button_templates[bid_str].threshold
                    enabled = b_state.is_enabled if visible else False
                    confidence = float(b_state.confidence)
                else:
                    visible = False
                    enabled = False
                    confidence = 0.0

                buttons[bid_str] = UiPredictedButtonState(
                    visible=visible,
                    enabled=enabled,
                    confidence=confidence
                )
        except Exception as e:
            failures.append(UiFailureRecord(fid, "BUTTON_DETECTOR_ERROR", f"Button detection failed: {e}"))
            for bid_str in ("play", "pass"):
                buttons[bid_str] = UiPredictedButtonState(visible=False, enabled=False, confidence=0.0)

        # 2. Run OCR detection
        ocr_fields = []
        try:
            for oid, o_cfg in config.ocr_fields.items():
                ocr_res = adapters.ocr_detector.recognize(frame, o_cfg.roi, whitelist=o_cfg.whitelist)
                text = ocr_res.text
                confidence = float(ocr_res.confidence)
                if confidence < config.ocr_minimum_confidence:
                    text = "UNKNOWN"
                ocr_fields.append(UiPredictedOcrField(
                    field_id=oid,
                    text=text,
                    confidence=confidence
                ))
        except Exception as e:
            failures.append(UiFailureRecord(fid, "OCR_DETECTOR_ERROR", f"OCR detection failed: {e}"))
            ocr_fields = [UiPredictedOcrField(oid, "UNKNOWN", 0.0) for oid in config.ocr_fields.keys()]

        # 3. Run Turn ownership detection & consensus
        current_card_counts = {}
        for pos_str, val in rec.player_card_counts.items():
            pos = getattr(SeatPosition, pos_str)
            current_card_counts[pos] = val

        turn_owner = None
        obs = 1
        mat = 0
        latest_match = False

        if previous_card_counts is None:
            detection = TurnOwnerDetection(
                turn_owner=None,
                evidence=None,
                primary=HighlightDetection(None, 0.0, None, {}),
                secondary=CardCountDelta(None, None, 0.0)
            )
        else:
            try:
                detection = adapters.turn_detector.detect(
                    frame,
                    previous_card_counts=previous_card_counts,
                    current_card_counts=current_card_counts
                )
            except Exception as e:
                failures.append(UiFailureRecord(fid, "TURN_DETECTOR_ERROR", f"Turn detection failed: {e}"))
                detection = TurnOwnerDetection(
                    turn_owner=None,
                    evidence=None,
                    primary=HighlightDetection(None, 0.0, None, {}),
                    secondary=CardCountDelta(None, None, 0.0)
                )

        try:
            consensus_result = adapters.turn_consensus.observe(bot_id, detection)
            if consensus_result.turn_owner is not None:
                turn_owner = consensus_result.turn_owner.name
            obs = consensus_result.observed_frames
            mat = consensus_result.matching_frames
            latest_match = (detection.turn_owner == consensus_result.turn_owner)
        except Exception as e:
            failures.append(UiFailureRecord(fid, "CONSENSUS_ERROR", f"Consensus observe failed: {e}"))
            adapters.turn_consensus.reset(bot_id)

        previous_card_counts = current_card_counts

        t1 = clock()
        latency = round((t1 - t0) * 1000.0, 6)
        if latency < 0.0 or not math.isfinite(latency):
            latency = 0.0

        predictions.append(UiPredictionRecord(
            frame_id=fid,
            buttons=MappingProxyType(buttons),
            ocr_fields=tuple(ocr_fields),
            turn_owner=turn_owner,
            turn_observed_frames=obs,
            turn_matching_frames=mat,
            turn_latest_frame_matches=latest_match,
            latency_ms=latency,
            source_commit=config.source_commit,
            config_sha256=config.config_sha256
        ))

    return UiInferenceResult(
        predictions=tuple(predictions),
        failures=tuple(failures),
        source_commit=config.source_commit,
        config_sha256=config.config_sha256,
        dataset_id=source.dataset_id,
        input_sha256=source.input_sha256
    )

# ------------------------------------------------------------------ #
# Public Writer API                                                 #
# ------------------------------------------------------------------ #

def write_ui_inference_result(result: UiInferenceResult, output_dir: str | Path) -> None:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    pred_lines = []
    for pr in result.predictions:
        row = {
            "frame_id": pr.frame_id,
            "buttons": {
                name: {
                    "visible": b.visible,
                    "enabled": b.enabled,
                    "confidence": b.confidence
                } for name, b in pr.buttons.items()
            },
            "ocr_fields": [
                {
                    "field_id": o.field_id,
                    "text": o.text,
                    "confidence": o.confidence
                } for o in pr.ocr_fields
            ],
            "turn_owner": pr.turn_owner,
            "turn_observed_frames": pr.turn_observed_frames,
            "turn_matching_frames": pr.turn_matching_frames,
            "turn_latest_frame_matches": pr.turn_latest_frame_matches,
            "latency_ms": pr.latency_ms,
            "source_commit": pr.source_commit,
            "config_sha256": pr.config_sha256
        }
        pred_lines.append(json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False))
    pred_bytes = ("\n".join(pred_lines) + "\n").encode("utf-8")
    pred_sha = hashlib.sha256(pred_bytes).hexdigest()

    fail_lines = []
    for f in result.failures:
        row = {
            "frame_id": f.frame_id,
            "reason_code": f.reason_code,
            "details": f.details
        }
        fail_lines.append(json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False))
    fail_bytes = ("\n".join(fail_lines) + "\n").encode("utf-8")
    fail_sha = hashlib.sha256(fail_bytes).hexdigest()

    manifest = {
        "dataset_id": result.dataset_id,
        "config_sha256": result.config_sha256,
        "source_commit": result.source_commit,
        "input_sha256": dict(result.input_sha256),
        "output_sha256": {
            "predictions.jsonl": pred_sha,
            "failures.jsonl": fail_sha
        }
    }
    manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")

    def _write_atomic(filename: str, data: bytes) -> None:
        target = out / filename
        fd, tmp_path = tempfile.mkstemp(dir=str(out), prefix=f"{filename}_tmp")
        os.close(fd)
        tmp = Path(tmp_path)
        try:
            tmp.write_bytes(data)
            if target.exists():
                os.remove(target)
            os.rename(tmp, target)
        except Exception as e:
            if tmp.exists():
                os.remove(tmp)
            raise e

    _write_atomic("predictions.jsonl", pred_bytes)
    _write_atomic("failures.jsonl", fail_bytes)
    _write_atomic("inference_manifest.json", manifest_bytes)
