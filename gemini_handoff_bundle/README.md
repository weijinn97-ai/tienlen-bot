# Gemini Controlled Handoff

Repository: `https://github.com/weijinn97-ai/tienlen-bot`

Day la source of truth danh cho Google Gemini. Doc theo dung thu tu:

1. `AGENTS.md`
2. `docs/MASTER_EXECUTION_PLAN_VI.md`
3. `.github/module-registry.json`
4. `gemini_handoff_bundle/GEMINI_MASTER_PLAN_VI.md`
5. `gemini_handoff_bundle/ACTIVE_TASK.json`
6. File instruction duoc ghi trong `ACTIVE_TASK.json`

## Active task

- Task: `GEMINI-PERCEPTION-UI-01B`
- Clone directory: `tienlen-bot-gemini`
- Baseline tag: `gemini-perception-ui-01b-baseline`
- Branch: `agent/gemini-perception-ui-01b`
- Output directory: `GEMINI_PERCEPTION_UI_01B_OUTPUT/`
- GitHub issue: `#8 PERCEPTION-UI-01`

Task nay chi xay read-only inference runner de tao `predictions.jsonl` tu frame
replay. Khong sua evaluator 01A, detector hien huu, action, ADB, raw data hoac
model weights. Khong duoc claim production-ready.

## Quy tac cap quyen

Gemini khong duoc tu chay toan bo master plan. Chi `ACTIVE_TASK.json` cap quyen
path va thao tac. Task catalog chi la roadmap, khong phai whitelist. Neu can mot
path bi cam, dung va ghi blocker; khong tu mo rong scope.

Truoc commit va truoc push bat buoc chay:

```powershell
powershell -ExecutionPolicy Bypass -File gemini_handoff_bundle/guard_scope.ps1
py -3 -m unittest discover -s tests -v
py -3 -m compileall -q bot contracts tools
py -3 tools/check_module_governance.py
git diff --check
```

Neu bat ky gate nao fail, Gemini phai dung. Khong sua guard, policy, test cu hoac
file ngoai scope de lam gate pass.
