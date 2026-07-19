# Yêu cầu thực thi dành cho Kimi

## 1. Vai trò và mục tiêu

Bạn là agent triển khai task `DATA-01` cho dự án Tiến Lên Bot. Mục tiêu là xây pipeline kiểm kê, chống leakage, chia tập và QA annotation trước khi train. Không train model trong task này và không chỉnh logic bot hiện hữu.

Source of truth:

1. `AGENTS.md`
2. `docs/MASTER_EXECUTION_PLAN_VI.md`
3. `.github/module-registry.json`
4. GitHub issue `#5`
5. `agent_handoff_bundle/TRAINING_GUIDE_VI.md`
6. `kimi_handoff_bundle/SCOPE_POLICY.json`

Nếu các tài liệu mâu thuẫn, dừng và ghi vào `KIMI_DATA_01_OUTPUT/BLOCKERS.md`. Không tự chọn kiến trúc mới.

## 2. Thiết lập bắt buộc

```powershell
git clone https://github.com/weijinn97-ai/tienlen-bot.git tienlen-bot-kimi
cd tienlen-bot-kimi
git checkout kimi-data-01-baseline
git switch -c agent/kimi-data-01
py -3 -m unittest discover -s tests
py -3 tools/check_module_governance.py
```

Baseline phải đạt `84/84` test. Nếu khác, không sửa test cũ để làm xanh; ghi blocker và báo chủ repo.

## 3. Quy tắc phạm vi

Mặc định mọi file đều bị cấm sửa. Chỉ được **tạo mới**:

- `tools/build_dataset_inventory.py`
- `tests/test_dataset_inventory.py`
- `data/dataset_inventory/**`
- `docs/acceptance/dataset/0.1.0/**`
- `KIMI_DATA_01_OUTPUT/**`

Không được sửa, đổi tên hoặc xóa bất kỳ file đã tồn tại tại baseline. Đặc biệt cấm sửa:

- `contracts/**`
- `bot/**`
- `configs/**`
- `.github/**`
- mọi test hiện hữu
- `data/submissions/**`
- `data/yolo_bootstrap/**`
- `data/templates/**`
- `AGENTS.md` và tài liệu kế hoạch hiện hữu

Không được dùng `git add -A`. Chỉ stage từng file mới thuộc whitelist. Không push trực tiếp `main`, không force-push, không tự merge PR.

## 4. Deliverable code

Tạo `tools/build_dataset_inventory.py` với CLI deterministic, chạy được trên Windows PowerShell:

```powershell
py -3 tools/build_dataset_inventory.py `
  --repo-root . `
  --output data/dataset_inventory
```

CLI phải:

1. Chỉ đọc ảnh trong `data/submissions/**/raw/` và annotation liên quan; không ghi vào nguồn.
2. Hỗ trợ tối thiểu `.png`, `.jpg`, `.jpeg`, `.webp` không phân biệt hoa thường.
3. Tính SHA-256 theo bytes gốc.
4. Tính perceptual hash 64-bit deterministic từ ảnh grayscale; ghi dạng 16 ký tự hex.
5. Đọc width/height, báo file hỏng nhưng không làm mất toàn bộ báo cáo.
6. Nhóm duplicate exact theo SHA-256 và near-duplicate theo khoảng cách Hamming pHash có threshold CLI rõ ràng.
7. Suy ra `submission/session/match/round/zone` từ manifest nếu có; nếu không đủ dữ liệu phải ghi `UNKNOWN`, tuyệt đối không đoán.
8. Tìm annotation theo đường dẫn/quy ước hiện có và ghi trạng thái `PRESENT`, `MISSING`, `INVALID` hoặc `NOT_REQUIRED`.
9. Chia train/val/test theo group session/match/round, không chia ngẫu nhiên từng ảnh.
10. Giữ mọi duplicate group trong cùng một split.
11. Dùng seed cố định, cùng input phải cho output byte-for-byte giống nhau.
12. Không cài thêm package; ưu tiên thư viện chuẩn và dependency đã có (`cv2`, `numpy`).

## 5. File đầu ra bắt buộc

Trong `data/dataset_inventory/`:

- `inventory.csv`
- `split_manifest.csv`
- `duplicate_groups.csv`
- `annotation_review.csv`
- `coverage_report.json`
- `run_manifest.json`

`inventory.csv` tối thiểu có các cột:

```text
asset_id,relative_path,submission,session_id,match_id,round_id,zone,sha256,phash64,width,height,annotation_path,annotation_status,error
```

`split_manifest.csv` tối thiểu có:

```text
asset_id,relative_path,group_id,split,split_reason
```

`coverage_report.json` phải thống kê:

- tổng ảnh hợp lệ/hỏng;
- số exact/near duplicate group;
- số ảnh theo submission, zone và split;
- annotation present/missing/invalid;
- class coverage nếu annotation có class;
- hard-negative deficit;
- trường metadata còn `UNKNOWN`;
- mọi leakage violation, kỳ vọng bằng 0.

`run_manifest.json` phải chứa baseline commit, UTC timestamp, command, seed, pHash threshold, input count và SHA-256 của toàn bộ file báo cáo.

## 6. QA và split

- Không overwrite hoặc xóa raw input.
- Split theo session trước, sau đó match/round; nếu metadata thiếu thì dùng duplicate group cộng submission làm boundary an toàn.
- Target mặc định `train/val/test = 70/15/15`, nhưng ưu tiên zero leakage hơn tỷ lệ đẹp.
- 100% annotation val/test phải được đưa vào `annotation_review.csv` với `review_required=true`.
- Tối thiểu 20% train annotation phải được chọn deterministic cho second review.
- Mọi annotation malformed phải có reason cụ thể.
- Không được gọi bootstrap/pseudo bbox là ground truth production.

## 7. Test bắt buộc

Tạo `tests/test_dataset_inventory.py`, dùng temporary directory và ảnh synthetic nhỏ. Không phụ thuộc MEmu hoặc mạng.

Phải test tối thiểu:

1. SHA-256 và pHash deterministic.
2. Exact duplicate được gom nhóm.
3. Near duplicate theo Hamming threshold.
4. Duplicate không bị rơi sang split khác.
5. Hai ảnh cùng session/match/round không bị leakage.
6. Metadata thiếu trả `UNKNOWN`.
7. File ảnh hỏng được báo cáo, không crash toàn run.
8. Annotation thiếu/invalid được phân loại đúng.
9. Second-review đạt 100% val/test và ít nhất 20% train.
10. Hai lần chạy cùng input tạo output nội dung giống nhau, ngoại trừ trường timestamp nếu timestamp được tách khỏi artifact deterministic.
11. Raw input không thay đổi sau khi chạy.
12. CLI trả exit code khác 0 khi phát hiện leakage hoặc schema output sai.

Không sửa/xóa test cũ. Kết quả cuối phải có ít nhất `96` test pass nếu thêm đúng 12 test mới.

## 8. Acceptance evidence

Tạo `docs/acceptance/dataset/0.1.0/` gồm:

- `README.md`: môi trường, baseline, scope, kết luận.
- `commands.txt`: toàn bộ lệnh thực tế đã chạy.
- `metrics.json`: số liệu machine-readable.
- `artifacts.sha256`: checksum báo cáo.
- `failures.md`: thiếu dữ liệu, metadata, annotation và rủi ro còn lại.

Không đổi `.github/module-registry.json`; chủ repo sẽ cập nhật sau khi review.

## 9. Lệnh kiểm tra cuối

```powershell
py -3 -m unittest discover -s tests -v
py -3 -m compileall -q bot contracts tools
py -3 tools/check_module_governance.py
py -3 tools/build_dataset_inventory.py --repo-root . --output data/dataset_inventory
powershell -ExecutionPolicy Bypass -File kimi_handoff_bundle/check_scope.ps1
git diff --check
git status --short
```

Nếu bất kỳ lệnh nào fail, không được báo hoàn thành.

## 10. Commit, PR và bàn giao

Chỉ stage file whitelist bằng đường dẫn tường minh. Commit đề xuất:

```powershell
git commit -m "Add deterministic dataset inventory and QA"
git push -u origin agent/kimi-data-01
```

Mở **draft PR**, ghi `Relates to #5`; không dùng `Closes #5` nếu chưa đủ review annotation thật. Không merge.

Tạo báo cáo cuối tại `KIMI_DATA_01_OUTPUT/FINAL_REPORT.md` theo template. Báo cáo phải có branch, commit, file thay đổi, test thật, metrics, việc chưa xong, rủi ro và exact next step.

## 11. Điều kiện phải dừng và hỏi

Dừng, không tự sửa nếu:

- cần thay contract hoặc public API hiện có;
- cần sửa raw image/annotation nguồn;
- cần thêm dependency;
- baseline test fail;
- metadata không đủ để đảm bảo zero leakage;
- phát hiện thay đổi từ agent khác trong cùng file/phạm vi;
- cần đổi module sang `CANDIDATE` hoặc `LOCKED`.
