# Project Tree at Baseline `kimi-data-01-baseline`

```text
tienlen-bot-kimi/
|-- .github/                 # CI, CODEOWNERS, governance registry; forbidden
|-- agent_handoff_bundle/    # Existing general/training handoff; read-only
|-- bot/
|   |-- actions/             # Guarded tap and verification; forbidden
|   |-- agent/               # Decision orchestration; forbidden
|   |-- capture/             # Windows/MEmu capture; forbidden
|   |-- discovery/           # ADB/VM identity; forbidden
|   |-- inference/           # Inference service; forbidden
|   |-- perception/          # Cards/button/OCR/turn; forbidden for DATA-01
|   |-- rules/               # Tien Len rules candidate; forbidden
|   |-- runtime/             # Worker/supervisor; forbidden
|   |-- stability/           # Watchdog/monitor; forbidden
|   `-- ui/                  # Operator launcher; forbidden
|-- configs/                 # Runtime/dataset configs; forbidden
|-- contracts/               # Shared typed contracts candidate; forbidden
|-- data/
|   |-- inbox/               # User drop area; read-only
|   |-- submissions/         # Raw submitted images/manifests; strictly read-only
|   |-- templates/           # Button templates; read-only
|   |-- yolo_bootstrap/      # Bootstrap images/labels; read-only
|   `-- dataset_inventory/   # Kimi may create generated reports here
|-- docs/
|   |-- acceptance/          # Kimi may add only dataset/0.1.0 evidence
|   |-- epics/               # Read-only
|   |-- rules/               # Read-only
|   `-- MASTER_EXECUTION_PLAN_VI.md
|-- tests/
|   |-- test_action_*.py
|   |-- test_capture_viewport.py
|   |-- test_contract_interfaces.py
|   |-- test_*perception*.py
|   |-- test_tien_len_rules.py
|   |-- test_turn_owner.py
|   `-- test_dataset_inventory.py  # Kimi may create this file only
|-- tools/
|   |-- check_module_governance.py
|   |-- import_user_screenshots.py
|   |-- build_bootstrap_yolo_dataset.py
|   `-- build_dataset_inventory.py # Kimi may create this file only
|-- kimi_handoff_bundle/      # This instruction bundle; read-only
|-- KIMI_DATA_01_OUTPUT/      # Fixed Kimi report directory
|-- AGENTS.md
|-- FULL_GITHUB_HANDOFF_VI.md
|-- README.md
|-- requirements-perception.txt
`-- requirements-runtime.txt
```

Các ảnh nhị phân không được liệt kê từng file trong tree để tránh tài liệu quá lớn. Nguồn ảnh hợp lệ phải được tool tự khám phá dưới `data/submissions/**/raw/` và ghi đầy đủ vào `inventory.csv`.

Trạng thái baseline:

- `MOD-CONTRACTS`: `CANDIDATE 0.1.0`
- `MOD-DISCOVERY-CAPTURE`: `CANDIDATE 0.1.0`
- `MOD-PERCEPTION`: `IN_PROGRESS 0.2.0`
- `MOD-STATE`: `CANDIDATE 0.1.0`
- `MOD-RULES-DECISION`: `CANDIDATE 0.2.0`
- `MOD-ACTIONS`: `CANDIDATE 0.1.0`
- `MOD-RUNTIME`: `IN_PROGRESS 0.1.0`
- Full suite: `84/84` pass

DATA-01 tạo inventory và QA, không được tự nâng bất kỳ trạng thái nào.
