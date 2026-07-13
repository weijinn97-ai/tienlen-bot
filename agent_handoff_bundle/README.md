# Agent Bundle

Cập nhật: 2026-07-13

Thư mục này được tạo để gửi nhanh cho agent khác khi cần xem bối cảnh và làm việc tiếp mà không phải tự dò toàn repo.

## Mở file nào trước

1. `WORK_COMPLETION_CHECKLIST_VI.md`
2. `TRAINING_GUIDE_VI.md` nếu agent làm dữ liệu, YOLO, button hoặc OCR
3. `FULL_PROJECT_HANDOFF_VI.md`
4. `index.html`
5. `docs/AGENT_HANDOFF_VI.md`
6. `docs/PROJECT_BOARD_VI.md`
7. `docs/GOOGLE_SHEET_TRACKER_VI.md`
8. `tracker/00_Overview.csv`
9. `tracker/01_Task_Board.csv`
10. `tracker/06_Build_Plan.csv`
11. `tracker/07_Runtime_Flow.csv`
12. `tracker/08_Image_Index.csv`

## Có gì trong đây

- `docs/`: các tài liệu cốt lõi để hiểu dự án, kiến trúc, cấu hình agent và cách dùng sheet
- `tracker/`: bản CSV của các tab Google Sheet đã seed gần nhất
- `WORK_COMPLETION_CHECKLIST_VI.md`: checklist dự án rõ Completed / Scaffold / Not finished
- `TRAINING_GUIDE_VI.md`: quy trình bàn giao train hand/table/button/OCR trên VPS và cổng nghiệm thu production
- `FULL_PROJECT_HANDOFF_VI.md`: bản Markdown đầy đủ để agent mới nắm kỹ toàn cục
- `index.html`: dashboard trực quan để nhìn nhanh milestone, checklist, task board, runtime flow và validation
- `LOCAL_GIT_STATUS.txt`: snapshot `git status` tại thời điểm gom bundle
- `RECENT_COMMITS.txt`: 5 commit gần nhất trên branch hiện tại

## Trạng thái GitHub

GitHub đã được đồng bộ với batch handoff mới nhất ở thời điểm cập nhật file này.

Tình trạng hiện tại:

- branch local đang ở `main`
- batch mới nhất đã có:
  - `contracts/` cho interface và contract dự án
  - `docs/epics/` để chia việc theo 5 epic
  - `.github/ISSUE_TEMPLATE/agent_work_item.md`
  - `tests/test_contract_interfaces.py`
  - `agent_handoff_bundle/WORK_COMPLETION_CHECKLIST_VI.md`
  - `agent_handoff_bundle/index.html`
  - `agent_handoff_bundle/FULL_PROJECT_HANDOFF_VI.md`

Vì vậy:

- nếu agent khác xem GitHub, họ đã thấy đúng batch handoff / contract / epic / checklist hiện tại
- nếu muốn nắm nhanh bằng mắt, mở `index.html`
- nếu muốn giao việc không thiếu sót, mở `WORK_COMPLETION_CHECKLIST_VI.md`

## Lưu ý khi chia sẻ

- `tracker/08_Image_Index.csv` có cột `original_source_path`, có thể chứa đường dẫn local của máy hiện tại
- nếu bạn gửi ra ngoài phạm vi làm việc nội bộ, nên cân nhắc redaction trước
- nếu muốn đồng bộ Google Sheet lại, script seed có thể ghi đè các tab chuẩn

## Link Google Sheet chung

`https://docs.google.com/spreadsheets/d/1pQ8eU043r1phOG67BsO9gDmUK2TKjVAZPSz6MccJ_vc/edit?gid=0#gid=0`
