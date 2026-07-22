# Dataset Inventory and QA 0.1.0

Status: implementation complete, dataset gate blocked. This evidence does not authorize training or a module status change.

Environment:

- Windows / Python 3.11
- Baseline: `gemini-data-01-baseline-v2` (`27caa12`)
- Scope: issue #5 DATA-01
- Inputs: three committed submissions under `data/submissions/`

Implemented:

- deterministic raw-image inventory with SHA-256 and 64-bit pHash;
- exact/near duplicate grouping;
- capture-boundary and duplicate-component split;
- YOLO annotation validation and deterministic second-review selection;
- coverage, split, duplicate, review and run manifests;
- fail-safe leakage validation and 14 synthetic tests.

Observed result:

- 36 images decoded successfully;
- zero exact duplicates and one transitive near-duplicate component;
- zero leakage because the full component stays in train;
- no valid val/test split can be produced from current inputs;
- all 36 source images lack production bbox annotations.

Conclusion: the tooling is ready for additional reviewed data, but the current dataset is not ready for model training or perception acceptance.
