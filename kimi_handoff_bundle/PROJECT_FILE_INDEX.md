# Project File Index

Chỉ mục source tại baseline `kimi-data-01-baseline`. Kimi phải tự chạy `rg --files` sau khi clone để xác nhận.

## Governance and root

```text
.github/CODEOWNERS
.github/module-registry.json
.github/pull_request_template.md
.github/workflows/quality-gate.yml
AGENTS.md
CLAUDE.md
CONTRIBUTING.md
FULL_GITHUB_HANDOFF_VI.md
README.md
launch_bot_ui.cmd
requirements-perception.txt
requirements-runtime.txt
```

## Production code

```text
bot/actions/__init__.py
bot/actions/action_pipeline.py
bot/actions/adb_broker.py
bot/actions/adb_controller.py
bot/actions/verification.py
bot/agent/action_executor.py
bot/agent/decision_orchestrator.py
bot/agent/free_api_agent.py
bot/agent/game_state_adapter.py
bot/agent/local_agent.py
bot/capture/__init__.py
bot/capture/capture_worker.py
bot/capture/windows_capture.py
bot/discovery/__init__.py
bot/discovery/adb_discovery.py
bot/inference/__init__.py
bot/inference/inference_service.py
bot/perception/__init__.py
bot/perception/buttons.py
bot/perception/fan_cards.py
bot/perception/ocr.py
bot/perception/table_state.py
bot/perception/turn_owner.py
bot/perception/yolo_cards.py
bot/rules/__init__.py
bot/rules/tien_len.py
bot/runtime/__init__.py
bot/runtime/bot_supervisor.py
bot/runtime/bot_worker.py
bot/runtime/schemas.py
bot/runtime/validation.py
bot/stability/__init__.py
bot/stability/system_monitor.py
bot/stability/watchdog.py
bot/ui/__init__.py
bot/ui/launcher_app.py
```

## Contracts and configuration

```text
contracts/__init__.py
contracts/interfaces.py
configs/agent_config.py
configs/dataset.yaml
configs/multi_bot_bindings.example.py
```

## Tests

```text
tests/test_action_pipeline.py
tests/test_action_verification.py
tests/test_adb_broker.py
tests/test_adb_discovery.py
tests/test_bot_worker_typed_state.py
tests/test_capture_viewport.py
tests/test_contract_interfaces.py
tests/test_fan_cards.py
tests/test_free_api_agent.py
tests/test_google_sheet_seed_public.py
tests/test_image_index_export.py
tests/test_live_gameplay_perception.py
tests/test_local_agent.py
tests/test_model_perception.py
tests/test_module_governance.py
tests/test_ocr.py
tests/test_runtime_validation.py
tests/test_supervisor.py
tests/test_table_state.py
tests/test_tien_len_rules.py
tests/test_turn_owner.py
```

## Existing tools

```text
tools/__init__.py
tools/build_bootstrap_yolo_dataset.py
tools/check_module_governance.py
tools/evaluate_fan_card_fallback.py
tools/export_image_index_csv.py
tools/extract_live_button_templates.py
tools/generate_google_sheet_seed.py
tools/import_user_screenshots.py
tools/launch_bot_ui.py
tools/run_action_verify_smoke.py
tools/run_bot_session.py
tools/run_live_soak.py
tools/scan_memu_adb.py
tools/seed_google_sheet_public.py
```

## Key documentation

```text
docs/MASTER_EXECUTION_PLAN_VI.md
docs/LIVE_VALIDATION_2026-07-13.md
docs/TRAINING_WORKFLOW.md
docs/rules/TIEN_LEN_RULES_V1_VI.md
docs/epics/EPIC_01_CONTRACTS_AND_BASELINES.md
docs/epics/EPIC_02A_DATA_BOOTSTRAP_AUTOMATION.md
docs/epics/EPIC_02B_TURN_OWNER_AND_UI_SIGNALS.md
docs/epics/EPIC_03_TABLE_STATE_AND_CONSENSUS.md
docs/epics/EPIC_04_ACTION_VERIFY_AND_CONTROL.md
docs/acceptance/perception-ui/0.2.0/
docs/acceptance/rules-decision/0.2.0/
agent_handoff_bundle/TRAINING_GUIDE_VI.md
agent_handoff_bundle/WORK_COMPLETION_CHECKLIST_VI.md
```

## Dataset layout

```text
data/inbox/user_training_images/
data/submissions/2026-06-21_memu_hand_screenshots/
data/submissions/2026-07-13_live_vm203_gameplay/
data/submissions/2026-07-13_live_vm203_gameplay_round2/
data/templates/buttons/1280x720/
data/yolo_bootstrap/images/{train,val,test}/
data/yolo_bootstrap/labels/{train,val,test}/
```

Mỗi submission hiện có `README.md`, `manifest.csv` và `raw/`. Không sửa các file này. Tool mới phải khám phá file động thay vì hard-code danh sách trên.
