# Agent Bundle

Cập nhật: 2026-06-25

Thư mục này được tạo để gửi nhanh cho agent khác khi cần xem bối cảnh và làm việc tiếp mà không phải tự dò toàn repo.

## Mở file nào trước

1. `docs/AGENT_HANDOFF_VI.md`
2. `docs/PROJECT_BOARD_VI.md`
3. `docs/GOOGLE_SHEET_TRACKER_VI.md`
4. `tracker/00_Overview.csv`
5. `tracker/01_Task_Board.csv`
6. `tracker/06_Build_Plan.csv`
7. `tracker/07_Runtime_Flow.csv`
8. `tracker/08_Image_Index.csv`

## Có gì trong đây

- `docs/`: các tài liệu cốt lõi để hiểu dự án, kiến trúc, cấu hình agent và cách dùng sheet
- `tracker/`: bản CSV của các tab Google Sheet đã seed gần nhất
- `LOCAL_GIT_STATUS.txt`: snapshot `git status` tại thời điểm gom bundle
- `RECENT_COMMITS.txt`: 5 commit gần nhất trên branch hiện tại

## Trạng thái GitHub

GitHub đang chứa bản đã push gần nhất ở commit `bd6b6c6`.

Tình trạng hiện tại:

- branch local đang ở `main`
- lần push gần nhất đã đưa lên:
  - `Free API Agent` đọc token từ env
  - `AGENT_HANDOFF_VI.md`
  - tracker CSV mới
  - image intake/index tools và test mới
  - `agent_handoff_bundle`
- file `index.html` trong bundle là phần tổng hợp local mới nhất sau lần push đó

Vì vậy:

- nếu agent khác xem GitHub, họ sẽ thấy gần như toàn bộ bức tranh mới
- nếu cần đúng bản handoff 1-file HTML này, hãy lấy trực tiếp từ bundle local hoặc push thêm lần nữa

## Lưu ý khi chia sẻ

- `tracker/08_Image_Index.csv` có cột `original_source_path`, có thể chứa đường dẫn local của máy hiện tại
- nếu bạn gửi ra ngoài phạm vi làm việc nội bộ, nên cân nhắc redaction trước
- nếu muốn đồng bộ Google Sheet lại, script seed có thể ghi đè các tab chuẩn

## Link Google Sheet chung

`https://docs.google.com/spreadsheets/d/1pQ8eU043r1phOG67BsO9gDmUK2TKjVAZPSz6MccJ_vc/edit?gid=0#gid=0`
