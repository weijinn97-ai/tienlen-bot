# Agent Operating Guide

Đây là điểm bắt đầu bắt buộc cho mọi agent làm việc trên `weijinn97-ai/tienlen-bot`.

## 1. Source of truth

Đọc theo đúng thứ tự:

1. `AGENTS.md`
2. `docs/MASTER_EXECUTION_PLAN_VI.md`
3. `.github/module-registry.json`
4. Epic hoặc issue được giao
5. Contract và test của module liên quan

Nếu tài liệu cũ mâu thuẫn với danh sách trên, dừng và báo chủ repo. Không tự chọn một
kiến trúc khác.

## 2. Quy tắc làm việc

- Một agent chỉ claim một task/module tại một thời điểm.
- Mỗi task dùng một branch và một PR; không push trực tiếp vào `main`.
- Chỉ sửa các file nằm trong `In scope` của issue.
- Không sửa module `LOCKED` nếu PR chưa có nhãn `locked-change-approved`.
- Không sửa contract để làm code mới dễ pass hơn. Mọi contract change cần issue riêng.
- Không commit secret, raw dataset lớn, model weight hoặc log có thông tin nhạy cảm.
- Không gọi module hoàn tất chỉ vì unit test pass; phải đủ acceptance evidence.
- Khi state hoặc perception không chắc chắn, kết quả bắt buộc là `WAIT`/fail-safe.

## 3. Trạng thái module

- `PLANNED`: mới có phạm vi và tiêu chí.
- `IN_PROGRESS`: đang triển khai, chưa dùng làm dependency ổn định.
- `CANDIDATE`: code đã có và test cơ bản pass, đang chờ nghiệm thu đầy đủ.
- `LOCKED`: đã nghiệm thu, có version và bằng chứng; agent khác không được tự sửa.
- `DEPRECATED`: còn tương thích tạm thời nhưng không dùng cho phát triển mới.

Chỉ chủ repo được chuyển `CANDIDATE` sang `LOCKED`. PR khóa module phải có:

- toàn bộ gate trong `docs/MASTER_EXECUTION_PLAN_VI.md` đạt;
- evidence manifest và lệnh kiểm tra có thể chạy lại;
- public API được ghi rõ;
- version theo Semantic Versioning;
- cập nhật `.github/module-registry.json`;
- approval của CODEOWNER.

## 4. Quy tắc thay đổi module đã khóa

1. Mở issue loại `Locked module change` và mô tả lỗi hoặc nhu cầu.
2. Xác định `PATCH`, `MINOR` hay `MAJOR` version bump.
3. Ghi rõ ảnh hưởng compatibility và migration.
4. Chủ repo gắn nhãn `locked-change-approved`.
5. Agent tạo branch riêng, thêm regression test trước khi sửa.
6. PR phải chạy lại toàn bộ gate của module và module phụ thuộc.
7. Sau merge, tạo tag/module release và cập nhật evidence.

Không có nhãn phê duyệt thì CI phải từ chối thay đổi đường dẫn `LOCKED`.

## 5. Lệnh kiểm tra tối thiểu

```powershell
py -3 -m unittest discover -s tests -v
py -3 tools/check_module_governance.py
```

Ngoài hai lệnh trên, chạy đúng verification command được ghi trong issue/module gate.

## 6. Handoff bắt buộc

Trước khi hết phiên làm việc, agent phải cập nhật issue/PR với:

- branch, commit SHA và phạm vi file đã sửa;
- việc đã làm và việc chưa làm;
- lệnh test cùng kết quả thật;
- lỗi/rủi ro còn lại;
- artifact/evidence và checksum nếu có;
- bước tiếp theo đủ cụ thể để agent khác tiếp tục.

Không để trạng thái quan trọng chỉ tồn tại trong nội dung chat.
