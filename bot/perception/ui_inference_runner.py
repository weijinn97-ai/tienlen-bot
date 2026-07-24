import json
import math
import hashlib
import os
import sys
import time
import re
import tempfile
import shutil
from dataclasses import dataclass
from typing import Any, Optional, Mapping, Tuple, Protocol, List, Dict
from pathlib import Path
from types import MappingProxyType
import cv2
import numpy as np

from contracts.interfaces import (
    Rect,
    ButtonId,
    ButtonState,
    SeatPosition,
    TurnOwnerEvidence,
    TurnPrimarySignal,
    TurnSecondarySignal,
)
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
# Hard Resource Ceilings — config may only tighten these              #
# ------------------------------------------------------------------ #

_HARD_MAX_FILE_SIZE_BYTES: int = 524288000   # 500 MB
_HARD_MAX_RECORDS: int = 1000000
_HARD_MAX_LINE_LENGTH: int = 2097152         # 2 MB
_HARD_MAX_TOTAL_INPUT_BYTES: int = 1073741824  # 1 GB
_HARD_MAX_IMAGE_PIXELS: int = 4096 * 4096
_HARD_MAX_OUTPUT_BYTES: int = 209715200      # 200 MB

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
# Immutable Dataclasses                                               #
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
class NormalizedOcrRoi:
    """OCR ROI in normalized [0.0, 1.0] coordinates."""
    x: float
    y: float
    width: float
    height: float

@dataclass(frozen=True)
class OcrFieldConfig:
    normalized_roi: NormalizedOcrRoi
    whitelist: str

@dataclass(frozen=True)
class ButtonTemplateConfig:
    filename: str
    search_roi: NormalizedRect
    threshold: float
    sha256: str
    image_bytes: bytes   # immutable bytes — never expose mutable ndarray
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

    def decode_template_image(self, key: str) -> np.ndarray:
        """Return a defensive read-only copy of template image; never shares mutable state."""
        btc = self.button_templates[key]
        arr = np.frombuffer(btc.image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Corrupt stored template bytes for {key}")
        img.flags.writeable = False
        return img

    def resolve_ocr_roi(self, field_id: str) -> Rect:
        """Resolve normalized OCR ROI to integer Rect for the config viewport."""
        fc = self.ocr_fields[field_id]
        nr = fc.normalized_roi
        vw = self.viewport["width"]
        vh = self.viewport["height"]
        return Rect(
            x=int(nr.x * vw),
            y=int(nr.y * vh),
            width=max(1, int(nr.width * vw)),
            height=max(1, int(nr.height * vh)),
        )

@dataclass(frozen=True)
class UiInferenceResult:
    predictions: Tuple[UiPredictionRecord, ...]
    failures: Tuple[UiFailureRecord, ...]
    source_commit: str
    config_sha256: str
    dataset_id: str
    input_sha256: Mapping[str, str]
    max_output_bytes: int = _HARD_MAX_OUTPUT_BYTES

    def __post_init__(self) -> None:
        object.__setattr__(self, "predictions", tuple(self.predictions))
        object.__setattr__(self, "failures", tuple(self.failures))
        object.__setattr__(self, "input_sha256", MappingProxyType(dict(self.input_sha256)))

# ------------------------------------------------------------------ #
# Internal Helpers                                                    #
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

def _load_jsonl(
    path: Path,
    max_records: int = _HARD_MAX_RECORDS,
    max_line_len: int = _HARD_MAX_LINE_LENGTH,
    max_file_size: int = _HARD_MAX_FILE_SIZE_BYTES,
) -> list[Any]:
    """Stream-parse JSONL enforcing per-record and per-line limits without loading full file first."""
    # Enforce ceilings
    max_records = min(max_records, _HARD_MAX_RECORDS)
    max_line_len = min(max_line_len, _HARD_MAX_LINE_LENGTH)
    max_file_size = min(max_file_size, _HARD_MAX_FILE_SIZE_BYTES)

    # File size check before opening
    try:
        file_size = path.stat().st_size
    except OSError as e:
        raise ValueError(f"Cannot stat {path.name}: {e}")
    if file_size > max_file_size:
        raise ValueError(
            f"{path.name} size {file_size} exceeds limit {max_file_size}"
        )

    res = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                if idx >= max_records:
                    raise ValueError(
                        f"Too many lines in {path.name} (exceeded {max_records} limit)"
                    )
                if len(line.encode("utf-8")) > max_line_len:
                    raise ValueError(
                        f"Line {idx + 1} in {path.name} exceeds max length of {max_line_len}"
                    )
                line_stripped = line.strip()
                if not line_stripped:
                    raise ValueError(
                        f"Line {idx + 1} in {path.name} is blank or whitespace-only"
                    )
                obj = json.loads(
                    line_stripped,
                    parse_constant=_reject_json_constant,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
                res.append(obj)
    except ValueError:
        raise
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

def _require_normalized_float(v: Any, name: str) -> float:
    """Require a finite float strictly in [0.0, 1.0]."""
    f = _require_finite_float(v, name)
    if not (0.0 <= f <= 1.0):
        raise ValueError(f"{name} must be in [0.0, 1.0], got {f}")
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

def _check_file_size(path: Path, limit: int) -> None:
    """Check file size before reading to avoid loading oversized assets."""
    try:
        size = path.stat().st_size
    except OSError as e:
        raise ValueError(f"Cannot stat {path.name}: {e}")
    if size > limit:
        raise ValueError(f"{path.name} size {size} exceeds limit {limit}")

def _safe_failure_details(msg: str) -> str:
    """
    Map an internal exception message to a stable sanitized failure detail.
    Strips absolute paths, exception reprs, object addresses, OS wording.
    Only the first 200 chars of a stable reason code phrase are returned.
    """
    # Truncate to prevent leaking long stack traces
    msg = str(msg)[:200]
    # Remove absolute path-like fragments (Windows and POSIX)
    msg = re.sub(r"[A-Za-z]:\\[^\s,\"']*", "<path>", msg)
    msg = re.sub(r"/[^\s,\"']{5,}", "<path>", msg)
    return msg

# ------------------------------------------------------------------ #
# Strict Adapter Output Validators (Fix B)                            #
# ------------------------------------------------------------------ #

def _validate_probability(value: Any, name: str) -> float:
    if type(value) is bool or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be finite in [0.0, 1.0]")
    return result


def _validate_frame_rect(value: Any, name: str, width: int, height: int) -> Rect:
    if type(value) is not Rect:
        raise ValueError(f"{name} must be exact Rect")
    if value.width <= 0 or value.height <= 0:
        raise ValueError(f"{name} must have positive dimensions")
    if (
        value.x < 0
        or value.y < 0
        or value.x + value.width > width
        or value.y + value.height > height
    ):
        raise ValueError(f"{name} must be contained in the frame")
    return value


def _validate_button_states(states: Any, vp_width: int, vp_height: int) -> Tuple[ButtonState, ...]:
    """Validate the raw output of ButtonDetectorAdapter.detect()."""
    if not isinstance(states, (list, tuple)):
        raise ValueError(
            f"ButtonDetectorAdapter.detect() must return list/tuple, got {type(states).__name__}"
        )
    validated = []
    for i, s in enumerate(states):
        if not isinstance(s, ButtonState):
            raise ValueError(
                f"Button state[{i}] must be ButtonState, got {type(s).__name__}"
            )
        if not isinstance(s.button_id, ButtonId):
            raise ValueError(f"Button state[{i}].button_id must be ButtonId")
        if type(s.label) is not str:
            raise ValueError(f"Button state[{i}].label must be exact str")
        if type(s.is_visible) is not bool:
            raise ValueError(f"Button state[{i}].is_visible must be bool")
        if type(s.is_enabled) is not bool:
            raise ValueError(f"Button state[{i}].is_enabled must be bool")
        _validate_probability(s.confidence, f"Button state[{i}].confidence")
        _validate_frame_rect(s.roi, f"Button state[{i}].roi", vp_width, vp_height)
        validated.append(s)
    return tuple(validated)


def _validate_ocr_text(
    result: Any,
    expected_roi: Rect,
    vp_width: int,
    vp_height: int,
) -> OcrText:
    """Validate the raw output of OcrAdapter.recognize()."""
    if not isinstance(result, OcrText):
        raise ValueError(
            f"OcrAdapter.recognize() must return OcrText, got {type(result).__name__}"
        )
    if type(result.text) is not str:
        raise ValueError("OcrText.text must be exact str")
    _validate_probability(result.confidence, "OcrText.confidence")
    roi = _validate_frame_rect(result.roi, "OcrText.roi", vp_width, vp_height)
    if roi != expected_roi:
        raise ValueError("OcrText.roi must equal the requested OCR ROI")
    return result


def _validate_turn_detection(
    result: Any,
    vp_width: int,
    vp_height: int,
) -> TurnOwnerDetection:
    """Validate the raw output of HybridTurnDetectorAdapter.detect()."""
    if not isinstance(result, TurnOwnerDetection):
        raise ValueError(
            f"TurnDetector.detect() must return TurnOwnerDetection, got {type(result).__name__}"
        )
    if result.turn_owner is not None and not isinstance(result.turn_owner, SeatPosition):
        raise ValueError("TurnOwnerDetection.turn_owner must be SeatPosition or None")
    if type(result.primary) is not HighlightDetection:
        raise ValueError("TurnOwnerDetection.primary must be exact HighlightDetection")
    if result.primary.owner is not None and not isinstance(result.primary.owner, SeatPosition):
        raise ValueError("HighlightDetection.owner must be SeatPosition or None")
    _validate_probability(result.primary.confidence, "HighlightDetection.confidence")
    if result.primary.owner is None:
        if result.primary.roi is not None:
            raise ValueError("HighlightDetection.roi must be None without an owner")
    else:
        _validate_frame_rect(
            result.primary.roi,
            "HighlightDetection.roi",
            vp_width,
            vp_height,
        )
    if not isinstance(result.primary.scores, Mapping):
        raise ValueError("HighlightDetection.scores must be a mapping")
    for seat, score in result.primary.scores.items():
        if not isinstance(seat, SeatPosition):
            raise ValueError("HighlightDetection score keys must be SeatPosition")
        _validate_probability(score, f"HighlightDetection.scores[{seat.name}]")

    if type(result.secondary) is not CardCountDelta:
        raise ValueError("TurnOwnerDetection.secondary must be exact CardCountDelta")
    if result.secondary.actor is not None and not isinstance(result.secondary.actor, SeatPosition):
        raise ValueError("CardCountDelta.actor must be SeatPosition or None")
    if (
        result.secondary.expected_next_owner is not None
        and not isinstance(result.secondary.expected_next_owner, SeatPosition)
    ):
        raise ValueError("CardCountDelta.expected_next_owner must be SeatPosition or None")
    _validate_probability(result.secondary.confidence, "CardCountDelta.confidence")
    if type(result.secondary.changed_by) is not int or not 0 <= result.secondary.changed_by <= 13:
        raise ValueError("CardCountDelta.changed_by must be exact int in [0, 13]")
    if (result.secondary.actor is None) != (result.secondary.expected_next_owner is None):
        raise ValueError("CardCountDelta actor and expected owner must both be set or both be null")

    if result.turn_owner is not None:
        if type(result.evidence) is not TurnOwnerEvidence:
            raise ValueError("A positive turn owner requires exact TurnOwnerEvidence")
        evidence = result.evidence
        if not isinstance(evidence.primary_signal, TurnPrimarySignal):
            raise ValueError("Turn evidence primary_signal is invalid")
        if not isinstance(evidence.secondary_signal, TurnSecondarySignal):
            raise ValueError("Turn evidence secondary_signal is invalid")
        _validate_frame_rect(
            evidence.primary_roi,
            "TurnOwnerEvidence.primary_roi",
            vp_width,
            vp_height,
        )
        _validate_probability(
            evidence.primary_confidence,
            "TurnOwnerEvidence.primary_confidence",
        )
        _validate_probability(
            evidence.secondary_confidence,
            "TurnOwnerEvidence.secondary_confidence",
        )
        if type(evidence.signals_agree) is not bool or not evidence.signals_agree:
            raise ValueError("A positive turn owner requires agreeing hybrid signals")
        if result.primary.owner != result.turn_owner:
            raise ValueError("Primary highlight owner must equal turn owner")
        if result.secondary.expected_next_owner != result.turn_owner:
            raise ValueError("Card-count expected owner must equal turn owner")
    return result


def _validate_consensus_result(
    result: Any,
    latest_detection: TurnOwnerDetection,
) -> TurnOwnerConsensusResult:
    """Validate the raw output of TurnConsensusAdapter.observe()."""
    if not isinstance(result, TurnOwnerConsensusResult):
        raise ValueError(
            f"TurnConsensus.observe() must return TurnOwnerConsensusResult, got {type(result).__name__}"
        )
    if result.turn_owner is not None and not isinstance(result.turn_owner, SeatPosition):
        raise ValueError("TurnOwnerConsensusResult.turn_owner must be SeatPosition or None")
    if (
        type(result.observed_frames) is not int
        or type(result.matching_frames) is not int
        or type(result.required_matches) is not int
    ):
        raise ValueError("TurnOwnerConsensusResult counts must be int")
    if result.required_matches != 3:
        raise ValueError("TurnOwnerConsensusResult.required_matches must be 3")
    if not (0 <= result.matching_frames <= result.observed_frames <= 4):
        raise ValueError(
            f"TurnOwnerConsensusResult counts violate 0 <= matching <= observed <= 4: "
            f"matching={result.matching_frames} observed={result.observed_frames}"
        )
    if result.turn_owner is not None:
        if result.observed_frames != 4 or result.matching_frames < 3:
            raise ValueError("A positive turn owner requires 3 of 4 consensus")
        if latest_detection.turn_owner != result.turn_owner:
            raise ValueError("Latest detection must belong to the consensus group")
    return result

# ------------------------------------------------------------------ #
# Safe Fallback Builders                                              #
# ------------------------------------------------------------------ #

def _safe_prediction(
    fid: str,
    ocr_field_ids: tuple[str, ...],
    config: "UiInferenceConfig",
    failures: list,
) -> "UiPredictionRecord":
    """Build a frame-wide safe prediction (all negative, UNKNOWN OCR, null turn)."""
    return UiPredictionRecord(
        frame_id=fid,
        buttons=MappingProxyType({
            bid.name.lower(): UiPredictedButtonState(visible=False, enabled=False, confidence=0.0)
            for bid in (ButtonId.PLAY, ButtonId.PASS)
        }),
        ocr_fields=tuple(
            UiPredictedOcrField(oid, "UNKNOWN", 0.0) for oid in ocr_field_ids
        ),
        turn_owner=None,
        turn_observed_frames=1,
        turn_matching_frames=0,
        turn_latest_frame_matches=False,
        latency_ms=0.0,
        source_commit=config.source_commit,
        config_sha256=config.config_sha256,
    )

# ------------------------------------------------------------------ #
# Public Loader API                                                   #
# ------------------------------------------------------------------ #

def load_ui_inference_source(
    source_dir: str | Path,
    *,
    resource_limits: Optional[Mapping[str, Any]] = None,
) -> "UiInferenceSource":
    base = Path(source_dir).resolve()
    source_json_path = base / "source.json"
    if not source_json_path.exists():
        raise ValueError("Missing source.json")

    # Fix C: check file size before reading
    hard_limits = {
        "max_file_size_bytes": _HARD_MAX_FILE_SIZE_BYTES,
        "max_records": _HARD_MAX_RECORDS,
        "max_line_length": _HARD_MAX_LINE_LENGTH,
        "max_total_input_bytes": _HARD_MAX_TOTAL_INPUT_BYTES,
        "max_image_pixels": _HARD_MAX_IMAGE_PIXELS,
        "max_output_bytes": _HARD_MAX_OUTPUT_BYTES,
    }
    effective_limits = dict(hard_limits)
    if resource_limits is not None:
        if not isinstance(resource_limits, Mapping):
            raise ValueError("resource_limits must be a mapping")
        if set(resource_limits) != set(hard_limits):
            raise ValueError("resource_limits must contain the exact supported keys")
        for name, ceiling in hard_limits.items():
            value = resource_limits[name]
            if type(value) is not int or value <= 0 or value > ceiling:
                raise ValueError(f"{name} must be exact positive int within its hard ceiling")
            effective_limits[name] = value

    eff_max_file = effective_limits["max_file_size_bytes"]
    eff_max_records = effective_limits["max_records"]
    eff_max_line = effective_limits["max_line_length"]

    _check_file_size(source_json_path, eff_max_file)

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

    # Fix C: check index file size before loading
    _check_file_size(frame_index_path, eff_max_file)

    frame_index_bytes = frame_index_path.read_bytes()
    frame_index_sha_actual = hashlib.sha256(frame_index_bytes).hexdigest()
    if frame_index_sha_actual != frame_index_sha_expected:
        raise ValueError(f"Checksum mismatch for frame index: expected {frame_index_sha_expected}, got {frame_index_sha_actual}")

    input_sha256 = {
        "source.json": source_sha,
        frame_index_rel: frame_index_sha_actual
    }

    # Fix C: stream JSONL with effective limits
    raw_records = _load_jsonl(
        frame_index_path,
        max_records=eff_max_records,
        max_line_len=eff_max_line,
        max_file_size=eff_max_file,
    )
    _check_forbidden_keys(raw_records)

    frame_index = []
    seen_frame_ids = set()
    seen_image_shas = set()
    last_seq_idx: dict[Tuple[str, str], int] = {}
    last_seq_ts: dict[Tuple[str, str], int] = {}
    active_sequences: dict[str, str] = {}
    total_input_bytes = source_json_path.stat().st_size + frame_index_path.stat().st_size

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

        # Fix C: check image file size before reading
        _check_file_size(full_path, eff_max_file)

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

        # Verify image shape/viewport + pixel count limit
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Corrupt or invalid image {rel_path}")
        h, w = img.shape[:2]
        if w * h > effective_limits["max_image_pixels"]:
            raise ValueError(f"Image {rel_path} exceeds pixel limit: {w * h}")
        if w != vp["width"] or h != vp["height"]:
            raise ValueError(f"Image dimensions mismatch for {rel_path}: {w}x{h} != {vp['width']}x{vp['height']}")

        total_input_bytes += len(img_bytes)
        if total_input_bytes > effective_limits["max_total_input_bytes"]:
            raise ValueError(f"Total input bytes exceeds limit: {total_input_bytes}")

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
            # Fix D: contiguous frame index validation
            prev_idx = last_seq_idx[seq_key]
            if f_idx != prev_idx + 1:
                raise ValueError(
                    f"frame_index gap detected in ({sid},{seqid}): expected {prev_idx + 1}, got {f_idx}"
                )
            if ts <= last_seq_ts[seq_key]:
                raise ValueError("capture_ts_ms must be strictly increasing per sequence")
        else:
            # First frame in sequence: index may be 0 or 1
            if f_idx not in (0, 1):
                raise ValueError(
                    f"First frame_index in sequence ({sid},{seqid}) must be 0 or 1, got {f_idx}"
                )

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


def load_ui_inference_config(config_path: str | Path) -> "UiInferenceConfig":
    p = Path(config_path).resolve()
    if not p.exists():
        raise ValueError("Missing config file")

    _check_file_size(p, _HARD_MAX_FILE_SIZE_BYTES)

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

    limits_raw = _require_type(config_dict["resource_limits"], dict, "resource_limits")
    limit_ceilings = {
        "max_file_size_bytes": _HARD_MAX_FILE_SIZE_BYTES,
        "max_records": _HARD_MAX_RECORDS,
        "max_line_length": _HARD_MAX_LINE_LENGTH,
        "max_total_input_bytes": _HARD_MAX_TOTAL_INPUT_BYTES,
        "max_image_pixels": _HARD_MAX_IMAGE_PIXELS,
        "max_output_bytes": _HARD_MAX_OUTPUT_BYTES,
    }
    _require_keys(limits_raw, set(limit_ceilings), "resource_limits")

    def _parse_limit(val: Any, name: str, hard_ceiling: int) -> int:
        if type(val) is not int:
            raise ValueError(f"{name} must be exact int, not bool or float")
        if val <= 0:
            raise ValueError(f"{name} must be positive")
        if val > hard_ceiling:
            raise ValueError(f"{name} {val} exceeds hard ceiling {hard_ceiling}")
        return val

    resource_limits = {
        name: _parse_limit(limits_raw[name], name, ceiling)
        for name, ceiling in limit_ceilings.items()
    }
    if len(config_bytes) > resource_limits["max_file_size_bytes"]:
        raise ValueError("config file exceeds max_file_size_bytes")

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

    # Fix E: Validate OCR fields using normalized [0.0, 1.0] coordinates
    ocr_fields_raw = _require_type(config_dict["ocr_fields"], dict, "ocr_fields")
    ocr_fields: dict[str, OcrFieldConfig] = {}
    for oid in list(ocr_fields_raw.keys()):  # preserve insertion order
        o_cfg = ocr_fields_raw[oid]
        if not _is_safe_id(oid):
            raise ValueError(f"Invalid OCR field ID: {oid}")
        _require_keys(o_cfg, {"roi", "whitelist"}, f"ocr_fields.{oid}")
        roi_raw = _require_type(o_cfg["roi"], dict, f"ocr_fields.{oid}.roi")
        _require_keys(roi_raw, {"x", "y", "width", "height"}, f"ocr_fields.{oid}.roi")

        nx = _require_normalized_float(roi_raw["x"], f"ocr_fields.{oid}.roi.x")
        ny = _require_normalized_float(roi_raw["y"], f"ocr_fields.{oid}.roi.y")
        nw_raw = roi_raw["width"]
        nh_raw = roi_raw["height"]

        if type(nw_raw) is bool or not isinstance(nw_raw, (int, float)):
            raise ValueError(f"ocr_fields.{oid}.roi.width must be numeric")
        nw = float(nw_raw)
        if not math.isfinite(nw) or not (0.0 < nw <= 1.0):
            raise ValueError(f"ocr_fields.{oid}.roi.width must be finite > 0.0 and <= 1.0")

        if type(nh_raw) is bool or not isinstance(nh_raw, (int, float)):
            raise ValueError(f"ocr_fields.{oid}.roi.height must be numeric")
        nh = float(nh_raw)
        if not math.isfinite(nh) or not (0.0 < nh <= 1.0):
            raise ValueError(f"ocr_fields.{oid}.roi.height must be finite > 0.0 and <= 1.0")

        # Fix E: check bounds + zero-area after resolution
        if nx + nw > 1.0:
            raise ValueError(f"OCR ROI x+width={nx+nw} exceeds normalized frame in {oid}")
        if ny + nh > 1.0:
            raise ValueError(f"OCR ROI y+height={ny+nh} exceeds normalized frame in {oid}")

        # Verify at least 1 pixel in the config viewport
        px_w = max(1, int(nw * vp["width"]))
        px_h = max(1, int(nh * vp["height"]))
        px_x = int(nx * vp["width"])
        px_y = int(ny * vp["height"])
        if px_x + px_w > vp["width"] or px_y + px_h > vp["height"]:
            raise ValueError(f"OCR ROI resolves outside viewport in {oid}")

        whitelist = _require_type(o_cfg["whitelist"], str, f"ocr_fields.{oid}.whitelist")
        ocr_fields[oid] = OcrFieldConfig(
            normalized_roi=NormalizedOcrRoi(x=nx, y=ny, width=nw, height=nh),
            whitelist=whitelist,
        )

    # Fix A: Validate Button templates — map each template_id to one ButtonId
    btn_dir_rel = _require_type(config_dict["button_template_dir"], str, "button_template_dir")
    resolved_paths: dict[str, str] = {}
    btn_dir_path = _validate_path(btn_dir_rel, p.parent, resolved_paths)

    btn_templates_raw = _require_type(config_dict["button_templates"], dict, "button_templates")
    button_templates: dict[str, ButtonTemplateConfig] = {}

    for bid_str, b_cfg in btn_templates_raw.items():
        # Fix A: Validate template identifier and determine ButtonId
        bid_lower = bid_str.lower()
        if bid_lower.startswith("play"):
            bid = ButtonId.PLAY
            label = "Đánh"
            is_enabled = "disabled" not in bid_lower
        elif bid_lower.startswith("pass"):
            bid = ButtonId.PASS
            label = "Bỏ Lượt"
            is_enabled = "disabled" not in bid_lower
        else:
            raise ValueError(f"Unknown or unsupported button template identifier: {bid_str}")

        _require_keys(b_cfg, {"filename", "search_roi", "threshold", "sha256"}, f"button_templates.{bid_str}")
        filename = _require_type(b_cfg["filename"], str, f"button_templates.{bid_str}.filename")
        if "\\" in filename or "/" in filename:
            raise ValueError(f"Button filename path traversal not allowed: {filename}")

        tmpl_file = btn_dir_path / filename
        if not tmpl_file.exists():
            raise ValueError(f"Button template file not found: {filename}")

        # Fix C: check template file size before reading
        _check_file_size(tmpl_file, resource_limits["max_file_size_bytes"])

        expected_tmpl_sha = _require_type(b_cfg["sha256"], str, f"button_templates.{bid_str}.sha256")
        if not _is_valid_hex(expected_tmpl_sha, 64):
            raise ValueError(f"Invalid template sha256 format for {bid_str}")

        tmpl_bytes = tmpl_file.read_bytes()
        actual_tmpl_sha = hashlib.sha256(tmpl_bytes).hexdigest()
        if actual_tmpl_sha != expected_tmpl_sha:
            raise ValueError(f"Template checksum mismatch for {bid_str}")

        # Verify image decodability
        arr = np.frombuffer(tmpl_bytes, dtype=np.uint8)
        img_check = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img_check is None:
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

        # Fix E: store immutable bytes, not mutable ndarray
        button_templates[bid_str] = ButtonTemplateConfig(
            filename=filename,
            search_roi=search_roi,
            threshold=threshold,
            sha256=expected_tmpl_sha,
            image_bytes=bytes(tmpl_bytes),   # immutable snapshot
            button_id=bid,
            label=label,
            is_enabled=is_enabled,
        )

    # Validate consensus
    consensus_raw = _require_type(config_dict["consensus"], dict, "consensus")
    _require_keys(consensus_raw, {"history_size", "required_matches"}, "consensus")
    consensus_history_size = _require_type(consensus_raw["history_size"], int, "consensus.history_size")
    consensus_required_matches = _require_type(consensus_raw["required_matches"], int, "consensus.required_matches")
    if consensus_history_size != 4 or consensus_required_matches != 3:
        raise ValueError("Consensus history_size must be 4 and required_matches must be 3 exactly")

    source_commit = _require_type(config_dict["source_commit"], str, "source_commit")
    if not _is_valid_hex(source_commit, 40):
        raise ValueError("Invalid source_commit format in config")

    serializable = {
        "schema_version": config_dict["schema_version"],
        "viewport": vp,
        "ocr_minimum_confidence": ocr_min_conf,
        "ocr_fields": {
            oid: {
                "roi": {
                    "x": fc.normalized_roi.x,
                    "y": fc.normalized_roi.y,
                    "width": fc.normalized_roi.width,
                    "height": fc.normalized_roi.height,
                },
                "whitelist": fc.whitelist
            } for oid, fc in ocr_fields.items()
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
# Public Inference Engine                                             #
# ------------------------------------------------------------------ #

def run_ui_inference(
    source: "UiInferenceSource",
    adapters: Any,
    config: "UiInferenceConfig",
    clock: Optional[Any] = None,
) -> "UiInferenceResult":
    if clock is None:
        clock = time.monotonic

    predictions = []
    failures = []
    bot_id = "bot"

    # Fix A: build button-id → best template config mapping
    # Multiple templates may map to same ButtonId; select highest threshold for visibility check
    # (threshold per-template is the primary config authority)
    bid_to_templates: dict[ButtonId, list[ButtonTemplateConfig]] = {}
    for tmpl in config.button_templates.values():
        bid_to_templates.setdefault(tmpl.button_id, []).append(tmpl)

    # Preserve OCR field order deterministically
    ocr_field_ids: tuple[str, ...] = tuple(config.ocr_fields.keys())

    # Fix D: Build immutable snapshot of expected checksums at inference start
    expected_checksums: dict[str, str] = dict(source.input_sha256)

    # Fix A: Verify source/config viewport match before any adapter calls
    if dict(source.viewport) != dict(config.viewport):
        raise ValueError(
            f"Source viewport {dict(source.viewport)} does not match config viewport {dict(config.viewport)}"
        )

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
        source_root = Path(source.source_dir).resolve()
        img_path = source_root / rel_path

        # Fix D: TOCTOU — re-read and revalidate checksum + dimensions at inference time
        try:
            resolved_runtime_path = _validate_path(rel_path, source_root, {})
            if resolved_runtime_path != img_path.resolve():
                raise ValueError("Frame canonical path changed after source loading")
            _check_file_size(
                resolved_runtime_path,
                config.resource_limits["max_file_size_bytes"],
            )
            runtime_bytes = resolved_runtime_path.read_bytes()
            runtime_sha = hashlib.sha256(runtime_bytes).hexdigest()
            if runtime_sha != rec.sha256:
                raise ValueError(
                    f"Frame integrity failure: checksum changed for {rel_path} "
                    f"(expected {rec.sha256}, got {runtime_sha})"
                )
            arr = np.frombuffer(runtime_bytes, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError("cv2.imdecode returned None")
            h, w = frame.shape[:2]
            if w != config.viewport["width"] or h != config.viewport["height"]:
                raise ValueError(
                    f"Frame dimensions changed: {w}x{h} != {config.viewport['width']}x{config.viewport['height']}"
                )
        except Exception as e:
            failures.append(UiFailureRecord(
                fid,
                "IMAGE_INTEGRITY_ERROR",
                _safe_failure_details(f"Frame integrity check failed: {type(e).__name__}")
            ))
            predictions.append(_safe_prediction(fid, ocr_field_ids, config, failures))
            adapters.turn_consensus.reset(bot_id)
            previous_card_counts = None
            continue

        # Fix F: Validate clock sample before measurement
        try:
            t0 = clock()
            if type(t0) is bool or not isinstance(t0, (int, float)) or not math.isfinite(float(t0)):
                raise ValueError(f"Clock returned non-finite value: {t0!r}")
            t0 = float(t0)
        except Exception as e:
            failures.append(UiFailureRecord(
                fid,
                "CLOCK_INVALID",
                "Clock sample t0 invalid"
            ))
            predictions.append(_safe_prediction(fid, ocr_field_ids, config, failures))
            adapters.turn_consensus.reset(bot_id)
            previous_card_counts = None
            continue

        vp_w = config.viewport["width"]
        vp_h = config.viewport["height"]

        # Fix A+B: Run Button detection with strict adapter-output validation
        buttons: dict[str, UiPredictedButtonState] = {}
        frame_wide_failure = False

        try:
            raw_states = adapters.button_detector.detect(frame)
            validated_states = _validate_button_states(raw_states, vp_w, vp_h)

            # Fix A: Group validated states by ButtonId; pick highest-confidence per ID
            # deterministic tie-break: sort by (confidence DESC, button_id.name ASC)
            bid_best: dict[ButtonId, ButtonState] = {}
            for s in sorted(
                validated_states,
                key=lambda x: (
                    -float(x.confidence),
                    x.button_id.name,
                    x.label,
                    x.roi.x,
                    x.roi.y,
                    x.roi.width,
                    x.roi.height,
                    x.is_visible,
                    x.is_enabled,
                ),
            ):
                if s.button_id not in bid_best:
                    bid_best[s.button_id] = s
                else:
                    existing = bid_best[s.button_id]
                    if float(s.confidence) > float(existing.confidence):
                        bid_best[s.button_id] = s

            # Fix A: Produce output keyed by ButtonId name (lowercase)
            for bid in (ButtonId.PLAY, ButtonId.PASS):
                key = bid.name.lower()
                if bid in bid_best:
                    b_state = bid_best[bid]
                    # Determine threshold: use minimum threshold among templates for this ButtonId
                    # (most permissive threshold → visible if ANY template would have matched)
                    thresholds = [
                        tmpl.threshold for tmpl in config.button_templates.values()
                        if tmpl.button_id == bid
                    ]
                    threshold = min(thresholds) if thresholds else 1.0
                    conf_f = float(b_state.confidence)
                    visible = b_state.is_visible and conf_f >= threshold
                    # Fix A: malformed state must never produce enabled button
                    # Fix A: visible=false must always imply enabled=false
                    enabled = (b_state.is_enabled and visible)
                    buttons[key] = UiPredictedButtonState(
                        visible=visible,
                        enabled=enabled,
                        confidence=conf_f,
                    )
                else:
                    # Fix A: missing ID → safe defaults
                    buttons[key] = UiPredictedButtonState(
                        visible=False,
                        enabled=False,
                        confidence=0.0,
                    )

        except Exception as e:
            failures.append(UiFailureRecord(
                fid,
                "BUTTON_DETECTOR_ERROR",
                _safe_failure_details(f"Button detection failed: {type(e).__name__}")
            ))
            frame_wide_failure = True

        # Fix B: frame-wide safe on button failure
        if frame_wide_failure:
            predictions.append(_safe_prediction(fid, ocr_field_ids, config, failures))
            adapters.turn_consensus.reset(bot_id)
            previous_card_counts = None
            continue

        # Fix B+E: Run OCR detection with normalized ROI resolution and validation
        ocr_fields_out: list[UiPredictedOcrField] = []
        ocr_failure = False
        try:
            for oid in ocr_field_ids:
                o_cfg = config.ocr_fields[oid]
                # Fix E: resolve normalized ROI to pixel Rect at runtime
                roi = config.resolve_ocr_roi(oid)
                raw_ocr = adapters.ocr_detector.recognize(frame, roi, whitelist=o_cfg.whitelist)
                valid_ocr = _validate_ocr_text(raw_ocr, roi, vp_w, vp_h)
                text = valid_ocr.text
                confidence = float(valid_ocr.confidence)
                if confidence < config.ocr_minimum_confidence:
                    text = "UNKNOWN"
                ocr_fields_out.append(UiPredictedOcrField(
                    field_id=oid,
                    text=text,
                    confidence=confidence,
                ))
        except Exception as e:
            failures.append(UiFailureRecord(
                fid,
                "OCR_DETECTOR_ERROR",
                _safe_failure_details(f"OCR detection failed: {type(e).__name__}")
            ))
            ocr_failure = True

        if ocr_failure:
            predictions.append(_safe_prediction(fid, ocr_field_ids, config, failures))
            adapters.turn_consensus.reset(bot_id)
            previous_card_counts = None
            continue

        # Fix B: Run Turn ownership detection & consensus with validation
        current_card_counts = {}
        for pos_str, val in rec.player_card_counts.items():
            pos = getattr(SeatPosition, pos_str)
            current_card_counts[pos] = val

        turn_owner = None
        obs = 1
        mat = 0
        latest_match = False
        turn_failure = False

        if previous_card_counts is None:
            detection = TurnOwnerDetection(
                turn_owner=None,
                evidence=None,
                primary=HighlightDetection(None, 0.0, None, {}),
                secondary=CardCountDelta(None, None, 0.0)
            )
        else:
            try:
                raw_detection = adapters.turn_detector.detect(
                    frame,
                    previous_card_counts=previous_card_counts,
                    current_card_counts=current_card_counts,
                )
                detection = _validate_turn_detection(raw_detection, vp_w, vp_h)
            except Exception as e:
                failures.append(UiFailureRecord(
                    fid,
                    "TURN_DETECTOR_ERROR",
                    _safe_failure_details(f"Turn detection failed: {type(e).__name__}")
                ))
                turn_failure = True

        if turn_failure:
            predictions.append(_safe_prediction(fid, ocr_field_ids, config, failures))
            adapters.turn_consensus.reset(bot_id)
            previous_card_counts = None
            continue

        consensus_failure = False
        try:
            raw_consensus = adapters.turn_consensus.observe(bot_id, detection)
            consensus_result = _validate_consensus_result(raw_consensus, detection)
            if consensus_result.turn_owner is not None:
                turn_owner = consensus_result.turn_owner.name
            obs = consensus_result.observed_frames
            mat = consensus_result.matching_frames
            latest_match = (
                consensus_result.turn_owner is not None
                and detection.turn_owner == consensus_result.turn_owner
            )
        except Exception as e:
            failures.append(UiFailureRecord(
                fid,
                "CONSENSUS_ERROR",
                _safe_failure_details(f"Consensus observe failed: {type(e).__name__}")
            ))
            consensus_failure = True

        if consensus_failure:
            predictions.append(_safe_prediction(fid, ocr_field_ids, config, failures))
            adapters.turn_consensus.reset(bot_id)
            previous_card_counts = None
            continue

        previous_card_counts = current_card_counts

        # Fix F: Validate t1 and detect regression
        try:
            t1 = clock()
            if type(t1) is bool or not isinstance(t1, (int, float)) or not math.isfinite(float(t1)):
                raise ValueError(f"Clock returned non-finite value: {t1!r}")
            t1 = float(t1)
            if t1 < t0:
                raise ValueError(f"Clock regression detected: t1={t1} < t0={t0}")
        except Exception as e:
            failures.append(UiFailureRecord(
                fid,
                "CLOCK_INVALID",
                "Clock sample t1 invalid or regressed"
            ))
            predictions.append(_safe_prediction(fid, ocr_field_ids, config, failures))
            adapters.turn_consensus.reset(bot_id)
            previous_card_counts = None
            continue

        latency = round((t1 - t0) * 1000.0, 6)

        predictions.append(UiPredictionRecord(
            frame_id=fid,
            buttons=MappingProxyType(buttons),
            ocr_fields=tuple(ocr_fields_out),
            turn_owner=turn_owner,
            turn_observed_frames=obs,
            turn_matching_frames=mat,
            turn_latest_frame_matches=latest_match,
            latency_ms=latency,
            source_commit=config.source_commit,
            config_sha256=config.config_sha256,
        ))

    return UiInferenceResult(
        predictions=tuple(predictions),
        failures=tuple(failures),
        source_commit=config.source_commit,
        config_sha256=config.config_sha256,
        dataset_id=source.dataset_id,
        input_sha256=source.input_sha256,
        max_output_bytes=config.resource_limits["max_output_bytes"],
    )

# ------------------------------------------------------------------ #
# Public Writer API                                                   #
# ------------------------------------------------------------------ #

def write_ui_inference_result(
    result: "UiInferenceResult",
    output_dir: str | Path,
    *,
    source_path: Optional[str | Path] = None,
    config_path: Optional[str | Path] = None,
    run_start_ts: Optional[float] = None,
) -> None:
    """
    Write inference results to output_dir atomically.

    Fix G: Transactional write — stage in sibling temp dir, then rename.
    Rejects output equal to or inside the source/config trees.
    Generates all artifact bytes before publishing any file.
    Produces four required files: predictions.jsonl, failures.jsonl,
    inference_manifest.json, and run_metadata.json.
    Manifest hashes match exact emitted bytes.
    run_metadata.json is excluded from deterministic hash comparisons.
    """
    out = Path(output_dir).resolve()

    # Fix G: Reject output overlap with source or config
    if source_path is not None:
        src_resolved = Path(source_path).resolve()
        if out == src_resolved or src_resolved in out.parents or out in src_resolved.parents:
            raise ValueError(
                f"Output directory cannot overlap with source path: {out} vs {src_resolved}"
            )
    if config_path is not None:
        cfg_resolved = Path(config_path).resolve()
        if out == cfg_resolved or cfg_resolved.parent == out or out == cfg_resolved.parent:
            raise ValueError(
                f"Output directory cannot overlap with config path: {out} vs {cfg_resolved}"
            )

    # Fix G: Build all artifact bytes before touching the filesystem
    pred_lines = []
    for pr in result.predictions:
        row = {
            "frame_id": pr.frame_id,
            "buttons": {
                name: {
                    "visible": b.visible,
                    "enabled": b.enabled,
                    "confidence": b.confidence,
                } for name, b in pr.buttons.items()
            },
            "ocr_fields": [
                {
                    "field_id": o.field_id,
                    "text": o.text,
                    "confidence": o.confidence,
                } for o in pr.ocr_fields
            ],
            "turn_owner": pr.turn_owner,
            "turn_observed_frames": pr.turn_observed_frames,
            "turn_matching_frames": pr.turn_matching_frames,
            "turn_latest_frame_matches": pr.turn_latest_frame_matches,
            "latency_ms": pr.latency_ms,
            "source_commit": pr.source_commit,
            "config_sha256": pr.config_sha256,
        }
        # Fix G: never allow NaN/Infinity in artifacts
        line = json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        pred_lines.append(line)
    pred_bytes = ("\n".join(pred_lines) + "\n").encode("utf-8")
    pred_sha = hashlib.sha256(pred_bytes).hexdigest()

    fail_lines = []
    for f in result.failures:
        row = {
            "frame_id": f.frame_id,
            "reason_code": f.reason_code,
            "details": f.details,
        }
        line = json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        fail_lines.append(line)
    fail_bytes = ("\n".join(fail_lines) + "\n").encode("utf-8")
    fail_sha = hashlib.sha256(fail_bytes).hexdigest()

    manifest = {
        "dataset_id": result.dataset_id,
        "config_sha256": result.config_sha256,
        "source_commit": result.source_commit,
        "input_sha256": dict(result.input_sha256),
        "output_sha256": {
            "predictions.jsonl": pred_sha,
            "failures.jsonl": fail_sha,
        }
    }
    manifest_bytes = (
        json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")

    # run_metadata.json: nondeterministic runtime info, excluded from deterministic hashes
    run_meta = {
        "schema_version": 1,
        "run_start_ts": run_start_ts if run_start_ts is not None else None,
        "total_predictions": len(result.predictions),
        "total_failures": len(result.failures),
        "note": "run_metadata.json is nondeterministic and excluded from deterministic hash comparison",
    }
    run_meta_bytes = (
        json.dumps(run_meta, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")

    # Fix G: check total output bytes before writing
    total_out = len(pred_bytes) + len(fail_bytes) + len(manifest_bytes) + len(run_meta_bytes)
    if total_out > result.max_output_bytes:
        raise ValueError(
            f"Total output bytes {total_out} exceeds limit {result.max_output_bytes}"
        )

    # Fix G: Transactional directory — stage in sibling temp, atomically rename to final
    out.parent.mkdir(parents=True, exist_ok=True)
    stage_dir = None
    try:
        # Create sibling staging directory
        stage_dir = Path(tempfile.mkdtemp(dir=str(out.parent), prefix=".stage_"))
        (stage_dir / "predictions.jsonl").write_bytes(pred_bytes)
        (stage_dir / "failures.jsonl").write_bytes(fail_bytes)
        (stage_dir / "inference_manifest.json").write_bytes(manifest_bytes)
        (stage_dir / "run_metadata.json").write_bytes(run_meta_bytes)

        # Fix G: Reject non-empty existing destination
        if out.exists():
            existing = list(out.iterdir())
            if existing:
                raise ValueError(
                    f"Output directory already exists and is non-empty: {out}"
                )
            out.rmdir()

        # Atomic publish: rename staging dir to final output dir
        os.rename(str(stage_dir), str(out))
        stage_dir = None  # successfully renamed; don't clean it up
    except Exception:
        # Fix G: On failure, remove staging dir but leave no partial final output
        if stage_dir is not None and stage_dir.exists():
            shutil.rmtree(str(stage_dir), ignore_errors=True)
        raise
