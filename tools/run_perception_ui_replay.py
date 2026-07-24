import sys
import time
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Any

# Add repository root to python path to import bot modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.perception import (
    load_ui_inference_source,
    load_ui_inference_config,
    run_ui_inference,
    write_ui_inference_result,
    TemplateButtonDetector,
    TesseractOcr,
    HybridTurnOwnerDetector,
    HybridTurnOwnerConsensus,
    ButtonTemplate,
)

@dataclass(frozen=True)
class UiAdapters:
    button_detector: Any
    ocr_detector: Any
    turn_detector: Any
    turn_consensus: Any

# ------------------------------------------------------------------ #
# Injectable Adapter Factory                                          #
# ------------------------------------------------------------------ #

def build_real_adapters(config: Any) -> UiAdapters:
    """Build real production adapters from config. Raises on failure."""
    templates = []
    for bid_str, b_cfg in config.button_templates.items():
        # Fix H: decode template image from immutable bytes
        import numpy as np
        import cv2
        arr = np.frombuffer(b_cfg.image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        templates.append(ButtonTemplate(
            button_id=b_cfg.button_id,
            label=b_cfg.label,
            image=img,
            search_roi=b_cfg.search_roi,
            threshold=b_cfg.threshold,
            is_enabled=b_cfg.is_enabled,
        ))
    button_detector = TemplateButtonDetector(tuple(templates))
    ocr_detector = TesseractOcr(minimum_confidence=config.ocr_minimum_confidence)
    turn_detector = HybridTurnOwnerDetector()
    turn_consensus = HybridTurnOwnerConsensus(
        history_size=config.consensus_history_size,
        required_matches=config.consensus_required_matches,
    )
    return UiAdapters(
        button_detector=button_detector,
        ocr_detector=ocr_detector,
        turn_detector=turn_detector,
        turn_consensus=turn_consensus,
    )


def status_to_exit_code(failures_count: int, frames_count: int) -> int:
    if frames_count == 0:
        return 2  # NO_DATA
    if failures_count > 0:
        return 1  # DEGRADED
    return 0  # COMPLETE


def main(
    argv: Optional[list[str]] = None,
    adapter_factory: Optional[Any] = None,
) -> int:
    """
    Main entry point.

    adapter_factory: optional callable(config) -> UiAdapters used in tests.
    Returns the integer exit code (does not call sys.exit so tests can inspect it).
    """
    parser = argparse.ArgumentParser(description="Run read-only perception UI inference replay")
    parser.add_argument("--source", required=True, help="Path to source dataset directory")
    parser.add_argument("--config", required=True, help="Path to configuration JSON file")
    parser.add_argument("--output", required=True, help="Path to output directory")

    args = parser.parse_args(argv)

    # Enforce input/output overlap check
    source_p = Path(args.source).resolve()
    output_p = Path(args.output).resolve()
    config_p = Path(args.config).resolve()

    if output_p == source_p or source_p in output_p.parents or output_p in source_p.parents:
        print("STATUS=INVALID", flush=True)
        print("Error: Output directory cannot be inside or equal to the input source bundle directory", file=sys.stderr)
        return 3

    try:
        source = load_ui_inference_source(args.source)
    except Exception as e:
        print("STATUS=INVALID", flush=True)
        print(f"Error: Failed to load source: {e}", file=sys.stderr)
        return 3  # INVALID

    try:
        config = load_ui_inference_config(args.config)
    except Exception as e:
        print("STATUS=INVALID", flush=True)
        print(f"Error: Failed to load config: {e}", file=sys.stderr)
        return 3  # INVALID

    # Enforce resource limits check on source frame index length
    max_records = config.resource_limits.get("max_records", 1000000)
    if len(source.frame_index) > max_records:
        print("STATUS=INVALID", flush=True)
        print(
            f"Error: Source frame index length {len(source.frame_index)} exceeds max_records limit {max_records}",
            file=sys.stderr,
        )
        return 3  # INVALID

    # Validate source/config viewport match
    if dict(source.viewport) != dict(config.viewport):
        print("STATUS=INVALID", flush=True)
        print("Error: Source viewport does not match config viewport", file=sys.stderr)
        return 3  # INVALID

    # Set up adapters (injectable for tests, real for production)
    try:
        if adapter_factory is not None:
            adapters = adapter_factory(config)
        else:
            adapters = build_real_adapters(config)
    except Exception as e:
        print("STATUS=INVALID", flush=True)
        print(f"Error: Failed to initialize detectors: {e}", file=sys.stderr)
        return 3  # INVALID

    run_start = time.time()

    # Run inference
    try:
        res = run_ui_inference(source, adapters, config)
    except Exception as e:
        print("STATUS=INVALID", flush=True)
        print(f"Error: Inference runtime failed: {e}", file=sys.stderr)
        return 3  # INVALID

    # Write output result
    try:
        write_ui_inference_result(
            res,
            args.output,
            source_path=args.source,
            config_path=args.config,
            run_start_ts=run_start,
        )
    except Exception as e:
        print("STATUS=INVALID", flush=True)
        print(f"Error: Failed to write inference results: {e}", file=sys.stderr)
        return 3  # INVALID

    # Determine exit code
    exit_code = status_to_exit_code(len(res.failures), len(res.predictions))
    if exit_code == 0:
        print("STATUS=COMPLETE", flush=True)
        print("Inference COMPLETE")
    elif exit_code == 1:
        print("STATUS=DEGRADED", flush=True)
        print(f"Inference DEGRADED with {len(res.failures)} failures")
    elif exit_code == 2:
        print("STATUS=NO_DATA", flush=True)
        print("Inference NO_DATA")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
