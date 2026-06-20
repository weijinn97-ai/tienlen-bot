# Hướng Dẫn Theo Dõi Online Bằng Google Sheets

Tài liệu này dùng cho link sheet bạn đang theo dõi:

- [Google Sheet theo dõi dự án](https://docs.google.com/spreadsheets/d/1pQ8eU043r1phOG67BsO9gDmUK2TKjVAZPSz6MccJ_vc/edit?gid=0#gid=0)

## Mục tiêu

Sheet này nên trở thành nơi theo dõi online chung cho:

- tiến độ dự án
- ghi chú của agent
- yêu cầu chỉnh sửa
- báo cáo hằng ngày
- quyết định quan trọng

## Lưu ý hiện tại

Trong môi trường Codex hiện tại, sheet này đang yêu cầu quyền truy cập nên mình không thể ghi trực tiếp vào nó từ đây.

Mình đã chuẩn bị sẵn bộ file import ở:

- [docs/google_sheet_seed](/D:/tienlenOPus/tienlen-bot/docs/google_sheet_seed)

Bạn chỉ cần import các file CSV đó vào Google Sheet là có thể dùng ngay.

## Cấu trúc nên có trong Google Sheet

Tạo hoặc import các tab sau:

1. `00_Overview`
2. `01_Task_Board`
3. `02_Agent_Notes`
4. `03_Change_Requests`
5. `04_Daily_Status`
6. `05_Decisions`

## File import đã có sẵn

- [00_Overview.csv](/D:/tienlenOPus/tienlen-bot/docs/google_sheet_seed/00_Overview.csv)
- [01_Task_Board.csv](/D:/tienlenOPus/tienlen-bot/docs/google_sheet_seed/01_Task_Board.csv)
- [02_Agent_Notes.csv](/D:/tienlenOPus/tienlen-bot/docs/google_sheet_seed/02_Agent_Notes.csv)
- [03_Change_Requests.csv](/D:/tienlenOPus/tienlen-bot/docs/google_sheet_seed/03_Change_Requests.csv)
- [04_Daily_Status.csv](/D:/tienlenOPus/tienlen-bot/docs/google_sheet_seed/04_Daily_Status.csv)
- [05_Decisions.csv](/D:/tienlenOPus/tienlen-bot/docs/google_sheet_seed/05_Decisions.csv)

## Cách import nhanh

1. Mở Google Sheet của bạn.
2. Tạo tab mới hoặc xóa nội dung tab cũ nếu muốn thay thế.
3. Chọn `File -> Import`.
4. Upload từng file CSV trong `docs/google_sheet_seed`.
5. Chọn import vào sheet mới hoặc tab mới.
6. Đổi tên tab đúng như tên file nếu cần.

## Cách share để nhiều agent cùng xem và cập nhật

Khuyến nghị an toàn:

- Bạn là `Owner`.
- Những người hoặc tài khoản thật sự cần sửa thì cho quyền `Editor`.
- Những người chỉ cần xem thì cho quyền `Viewer`.
- Không nên để `Anyone with the link = Editor` nếu sheet quan trọng.

Nếu vẫn muốn ai có link cũng có thể ghi chú trực tiếp:

- chỉ nên dùng khi sheet này không chứa dữ liệu nhạy cảm
- nên bảo vệ các tab quan trọng như `00_Overview` và header của `01_Task_Board`

## Cách bảo vệ để tránh bị sửa nhầm

Nên khóa hoặc protect:

- tab `00_Overview`
- hàng tiêu đề của tất cả tab
- các cột ID như `Task_ID`, `Request_ID`, `Decision_ID`

Nên cho phép chỉnh sửa tự do hơn ở:

- `02_Agent_Notes`
- `03_Change_Requests`
- `04_Daily_Status`

## Quy tắc làm việc cho nhiều agent

Mỗi agent nên theo flow này:

1. Xem `00_Overview` để biết dự án đang ở giai đoạn nào.
2. Xem `01_Task_Board` để biết phần nào đang làm, phần nào làm tiếp.
3. Nếu có phát hiện, ghi vào `02_Agent_Notes`.
4. Nếu muốn đề nghị sửa, thêm một dòng mới vào `03_Change_Requests`.
5. Nếu đã chốt thay đổi quan trọng, thêm vào `05_Decisions`.

## Cách dùng từng tab

### `00_Overview`

Dùng để nhìn tổng quan:

- milestone hiện tại
- tình trạng chung
- bước tiếp theo khuyến nghị

### `01_Task_Board`

Dùng để quản lý task chính:

- mã task
- đang ở trạng thái nào
- đã có gì
- còn phải làm gì tiếp

### `02_Agent_Notes`

Dùng cho agent ghi chú:

- phát hiện mới
- vấn đề cần nhắc
- ý tưởng nhanh

### `03_Change_Requests`

Dùng khi cần yêu cầu chỉnh sửa:

- ai yêu cầu
- task nào liên quan
- mức ưu tiên
- ai đang xử lý

### `04_Daily_Status`

Dùng để báo cáo ngắn theo ngày:

- hôm nay đã làm gì
- đang làm gì
- tiếp theo là gì
- có blocker không

### `05_Decisions`

Dùng để lưu các quyết định quan trọng để sau này không quên:

- đã chốt kiến trúc gì
- vì sao chốt như vậy
- ảnh hưởng đến phần nào

## Nếu muốn agent tự ghi online từ code

Hiện tại phần này chưa thể tự động từ môi trường hiện tại chỉ bằng link sheet.

Nếu bạn muốn các agent hoặc script tự ghi vào Google Sheet thật sự, cần thêm một trong các cách sau:

1. Chia sẻ sheet cho một `Google service account` rồi cung cấp credential JSON.
2. Tạo một `Google Apps Script Web App` để nhận dữ liệu ghi vào sheet.
3. Dùng một connector Google Sheets có quyền ghi trực tiếp trong môi trường agent.

Nếu bạn chọn một trong 3 cách này, mình có thể làm tiếp phần tự động hóa để bot hoặc agent cập nhật sheet online theo code.
