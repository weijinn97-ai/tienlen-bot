#!/usr/bin/env python3
"""CLI tool for perception UI evaluation."""

import argparse
import sys
from pathlib import Path

from bot.perception.ui_evaluation import (
    load_ui_evaluation_bundle,
    evaluate_ui_predictions,
    write_ui_evaluation_result,
    UiEvaluationConfig,
    UiEvaluationStatus,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate perception UI predictions")
    parser.add_argument("--bundle", required=True, help="Path to input bundle directory")
    parser.add_argument("--output", required=True, help="Path to output directory")
    args = parser.parse_args()

    out_dir = Path(args.output).resolve()
    bundle_dir = Path(args.bundle).resolve()

    # Output directory cannot be inside input bundle (overlap/self-reference is invalid)
    try:
        # pathlib is_relative_to is Python 3.9+
        if hasattr(out_dir, "is_relative_to"):
            if out_dir.is_relative_to(bundle_dir):
                print(f"Error: Output directory {out_dir} cannot be inside input bundle {bundle_dir}")
                sys.exit(3)
        else:
            if bundle_dir in out_dir.parents:
                print(f"Error: Output directory {out_dir} cannot be inside input bundle {bundle_dir}")
                sys.exit(3)
    except Exception:
        pass

    try:
        bundle = load_ui_evaluation_bundle(args.bundle)
    except ValueError as e:
        print(f"Error loading bundle: {e}")
        sys.exit(3)
    except Exception as e:
        print(f"Unexpected error loading bundle: {e}")
        sys.exit(3)

    try:
        config = UiEvaluationConfig()
        result = evaluate_ui_predictions(bundle, config)
    except Exception as e:
        print(f"Error during evaluation: {e}")
        sys.exit(3)

    try:
        write_ui_evaluation_result(result, args.output)
    except Exception as e:
        print(f"Error writing output: {e}")
        sys.exit(3)

    if result.status == UiEvaluationStatus.PASS.value:
        print("Evaluation PASS")
        sys.exit(0)
    elif result.status == UiEvaluationStatus.FAIL.value:
        print("Evaluation FAIL")
        sys.exit(1)
    elif result.status == UiEvaluationStatus.INSUFFICIENT_DATA.value:
        print("Evaluation INSUFFICIENT_DATA")
        sys.exit(2)
    else:
        print(f"Evaluation {result.status}")
        sys.exit(3)


if __name__ == "__main__":
    main()
