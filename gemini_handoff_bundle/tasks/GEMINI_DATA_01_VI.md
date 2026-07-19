# GEMINI-DATA-01

## Mục tiêu

Xây pipeline kiểm kê dataset production trước train. Không chỉnh logic bot và không train model.

## Setup duy nhất được phép

```powershell
git clone https://github.com/weijinn97-ai/tienlen-bot.git tienlen-bot-gemini
cd tienlen-bot-gemini
git checkout gemini-data-01-baseline-v2
git switch -c agent/gemini-data-01
py -3 -m unittest discover -s tests -v
py -3 tools/check_module_governance.py
powershell -ExecutionPolicy Bypass -File gemini_handoff_bundle/guard_scope.ps1
```

Baseline phải có 84 tests pass. Nếu không đúng, dừng và tạo `GEMINI_DATA_01_OUTPUT/BLOCKERS.md`. Không sửa test cũ.

## Code được tạo

Tạo `tools/build_dataset_inventory.py` với CLI:

```powershell
py -3 tools/build_dataset_inventory.py --repo-root . --output data/dataset_inventory
```

Yêu cầu:

1. Chỉ đọc `data/submissions/**/raw/`, manifest và annotation liên quan.
2. Không ghi, xóa, đổi tên hoặc tối ưu lại raw input.
3. Hỗ trợ PNG/JPG/JPEG/WEBP không phân biệt hoa thường.
4. Tính SHA-256 bytes gốc và pHash 64-bit deterministic dạng 16 hex.
5. Đọc width/height; file hỏng được báo cáo nhưng không làm crash toàn run.
6. Gom exact duplicate theo SHA-256 và near duplicate theo Hamming threshold CLI.
7. Đọc submission/session/match/round/zone từ manifest; thiếu thì ghi `UNKNOWN`, không đoán.
8. Annotation status chỉ dùng `PRESENT`, `MISSING`, `INVALID`, `NOT_REQUIRED`.
9. Split group-first theo session/match/round; duplicate luôn cùng split.
10. Seed cố định; cùng input cho report deterministic.
11. Không thêm dependency; dùng standard library, cv2 và numpy hiện có.
12. Exit code khác 0 khi schema lỗi hoặc phát hiện leakage.

## Output bắt buộc

Tạo dưới `data/dataset_inventory/`:

- `inventory.csv`
- `split_manifest.csv`
- `duplicate_groups.csv`
- `annotation_review.csv`
- `coverage_report.json`
- `run_manifest.json`

`inventory.csv`:

```text
asset_id,relative_path,submission,session_id,match_id,round_id,zone,sha256,phash64,width,height,annotation_path,annotation_status,error
```

`split_manifest.csv`:

```text
asset_id,relative_path,group_id,split,split_reason
```

Coverage report phải có ảnh valid/corrupt, duplicate groups, counts theo source/zone/split, annotation deficits, class coverage, hard-negative deficit, UNKNOWN metadata và leakage violations.

Run manifest phải có resolved baseline SHA, UTC timestamp, command, seed, threshold, input count và SHA-256 reports. Timestamp phải tách khỏi artifact cần so byte-for-byte nếu ảnh hưởng deterministic test.

## QA

- Target split 70/15/15 nhưng zero leakage ưu tiên cao hơn.
- 100% val/test annotation có `review_required=true`.
- Ít nhất 20% train annotation được chọn deterministic để second review.
- Malformed annotation phải có reason.
- Bootstrap/pseudo bbox không được gọi là production ground truth.

## Test mới

Chỉ được tạo `tests/test_dataset_inventory.py`, dùng temporary directory và synthetic images, không mạng/MEmu.

Test SHA/pHash deterministic, exact/near duplicate, group split, session leakage, UNKNOWN metadata, corrupt image, annotation statuses, review ratio, repeated output, raw unchanged và nonzero exit on leakage/schema error. Không sửa test cũ.

## Evidence

Tạo `docs/acceptance/dataset/0.1.0/`:

- `README.md`
- `commands.txt`
- `metrics.json`
- `artifacts.sha256`
- `failures.md`

Không sửa module registry; chủ repo cập nhật sau review.

## Kiểm tra trước commit và push

```powershell
powershell -ExecutionPolicy Bypass -File gemini_handoff_bundle/guard_scope.ps1
py -3 -m unittest discover -s tests -v
py -3 -m compileall -q bot contracts tools
py -3 tools/check_module_governance.py
py -3 tools/build_dataset_inventory.py --repo-root . --output data/dataset_inventory
git diff --check
git status --short
```

Chỉ stage từng path whitelist. Commit `Add deterministic dataset inventory and QA`, push branch `agent/gemini-data-01`, mở draft PR `Relates to #5`. Không merge, không dùng `Closes #5` khi review thật chưa đủ.

Lưu báo cáo tại `GEMINI_DATA_01_OUTPUT/FINAL_REPORT.md` theo template. Nếu cần ra ngoài whitelist, dừng và ghi blocker.
