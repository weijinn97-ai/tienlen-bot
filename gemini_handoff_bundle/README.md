# Gemini Controlled Handoff

Repository: `https://github.com/weijinn97-ai/tienlen-bot`

Đây là source of truth dành cho Google Gemini. Đọc theo thứ tự:

1. `AGENTS.md`
2. `docs/MASTER_EXECUTION_PLAN_VI.md`
3. `.github/module-registry.json`
4. `gemini_handoff_bundle/GEMINI_MASTER_PLAN_VI.md`
5. `gemini_handoff_bundle/ACTIVE_TASK.json`
6. File instruction được ghi trong `ACTIVE_TASK.json`

Định danh cố định cho task đang mở:

- Clone directory: `tienlen-bot-gemini`
- Baseline tag: `gemini-data-01-baseline`
- Branch: `agent/gemini-data-01`
- Output directory: `GEMINI_DATA_01_OUTPUT/`
- GitHub issue: `#5 DATA-01`

## Nguyên tắc quan trọng nhất

Gemini không được tự chạy toàn bộ master plan trong một branch. Chỉ `ACTIVE_TASK.json` cấp quyền. Sau mỗi PR, chủ repo/Codex review và phát hành baseline/active task mới. Task catalog chỉ là roadmap, không phải quyền chỉnh sửa.

Trước commit và trước push bắt buộc chạy:

```powershell
powershell -ExecutionPolicy Bypass -File gemini_handoff_bundle/guard_scope.ps1
py -3 -m unittest discover -s tests -v
py -3 tools/check_module_governance.py
git diff --check
```

Nếu guard fail, Gemini phải dừng. Không được sửa guard, policy, test cũ hoặc file ngoài scope để làm lệnh pass.
