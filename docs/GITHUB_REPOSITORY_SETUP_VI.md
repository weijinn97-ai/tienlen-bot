# GitHub Repository Setup

Các file trong repo tạo guard kỹ thuật, nhưng chủ repo vẫn phải bật Ruleset/Branch Protection
trên GitHub để agent không push thẳng hoặc tự merge.

## Thiết lập bắt buộc cho `main`

Vào `Settings -> Rules -> Rulesets`, tạo branch ruleset áp dụng cho `main`:

- Require a pull request before merging.
- Required approvals: tối thiểu `1`.
- Require review from Code Owners.
- Dismiss stale approvals when new commits are pushed.
- Require approval of the most recent reviewable push.
- Require status checks: `unit-and-governance`.
- Require conversation resolution before merging.
- Block force pushes và block deletions.
- Không cho GitHub App/agent bypass; chỉ chủ repo được bypass khẩn cấp.

Tạo label do chủ repo kiểm soát:

- `locked-change-approved`: cho phép CI kiểm tra một PR thay đổi module `LOCKED`.
- `module-lock-candidate`: PR đề nghị chuyển module từ `CANDIDATE` sang `LOCKED`.
- `acceptance-evidence`: issue/PR chứa bằng chứng nghiệm thu.

## Quy trình khóa module

1. Agent hoàn thành gate và mở PR `module-lock-candidate`.
2. Chủ repo kiểm tra evidence, public API, version và consumer tests.
3. Cập nhật module registry sang `LOCKED`, version ổn định và đường dẫn evidence.
4. Merge sau CODEOWNER approval.
5. Tạo Git tag theo dạng `<module-id>-v<version>` và GitHub Release nếu có artifact.

## Quy trình mở khóa có kiểm soát

1. Mở issue mô tả lỗi/feature và compatibility impact.
2. Chủ repo duyệt scope, version bump và gắn `locked-change-approved` vào PR.
3. PR thêm regression test trước khi thay đổi implementation.
4. Chạy lại gate module và consumer modules.
5. Cập nhật registry, evidence và release notes trong cùng PR.

`CODEOWNERS` không tự chặn merge nếu branch ruleset chưa được bật. Vì vậy thiết lập GitHub
ở phần đầu là điều kiện bắt buộc, không phải bước tùy chọn.
