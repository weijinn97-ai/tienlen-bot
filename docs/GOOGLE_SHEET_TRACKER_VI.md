# Hướng Dẫn Theo Dõi Online Bằng Google Sheets

Tài liệu này dùng cho link sheet đang theo dõi chung của dự án:

- [Google Sheet theo dõi dự án](https://docs.google.com/spreadsheets/d/1pQ8eU043r1phOG67BsO9gDmUK2TKjVAZPSz6MccJ_vc/edit?gid=0#gid=0)

## Mục tiêu

Sheet này là nơi online chung để:

- theo dõi tiến độ dự án
- ghi chú của agent
- gom yêu cầu chỉnh sửa
- cập nhật báo cáo ngắn hằng ngày
- lưu các quyết định quan trọng
- xem roadmap build bot và luồng chạy thực tế

## Trạng thái hiện tại

Hiện tại sheet đã mở quyền public edit và có thể seed trực tiếp từ máy Windows này bằng browser automation.

Mẫu dữ liệu chuẩn nằm trong:

- [docs/google_sheet_seed](/D:/tienlenOPus/tienlen-bot/docs/google_sheet_seed)

## Cách seed trực tiếp vào Google Sheet

Nếu link sheet vẫn mở quyền chỉnh sửa, có thể dùng script này:

```bash
py -3 -m pip install playwright
py -3 tools/seed_google_sheet_public.py --sheet-url "https://docs.google.com/spreadsheets/d/1pQ8eU043r1phOG67BsO9gDmUK2TKjVAZPSz6MccJ_vc/edit?gid=0"
```

Nếu muốn nhìn thấy browser khi chạy:

```bash
py -3 tools/seed_google_sheet_public.py --headful
```

Script sẽ:

1. mở Google Sheet
2. tạo hoặc cập nhật các tab chuẩn
3. xóa nội dung cũ trong từng tab chuẩn
4. dán lại dữ liệu seed mới nhất từ repo

## Cấu trúc tab chuẩn

Các tab chuẩn hiện tại là:

1. `00_Overview`
2. `01_Task_Board`
3. `02_Agent_Notes`
4. `03_Change_Requests`
5. `04_Daily_Status`
6. `05_Decisions`
7. `06_Build_Plan`
8. `07_Runtime_Flow`

## Ý nghĩa từng tab bằng tiếng Việt

### `00_Overview`

Dùng để nhìn tổng quan:

- dự án đang ở milestone nào
- trạng thái ngắn hiện tại
- bước tiếp theo nên ưu tiên
- nên mở tab nào nếu muốn xem plan chi tiết

### `01_Task_Board`

Dùng để quản lý việc chính:

- task nào đã xong
- task nào đang làm
- task nào làm tiếp
- còn thiếu gì

### `02_Agent_Notes`

Dùng để agent ghi chú nhanh:

- phát hiện mới
- cảnh báo
- ý tưởng
- điểm cần người khác biết trước khi sửa

### `03_Change_Requests`

Dùng để yêu cầu chỉnh sửa:

- ai yêu cầu
- yêu cầu gì
- liên quan task nào
- mức ưu tiên ra sao

### `04_Daily_Status`

Dùng để báo cáo theo ngày:

- hôm nay đã làm gì
- đang làm gì
- tiếp theo là gì
- có bị kẹt không

### `05_Decisions`

Dùng để lưu quyết định đã chốt:

- chốt kiến trúc gì
- vì sao chốt như vậy
- ảnh hưởng đến phần nào

### `06_Build_Plan`

Đây là tab quan trọng nếu muốn biết rõ cách build bot từ đầu đến cuối.

Tab này trả lời:

- chúng ta đang ở pha nào
- bước tiếp theo là gì
- đầu vào và đầu ra của từng bước
- phụ thuộc giữa các bước
- cách kiểm tra xem bước đó đã xong chưa
- nhóm agent nào có thể làm song song

### `07_Runtime_Flow`

Đây là tab dạng sơ đồ luồng chạy của bot trong thực tế.

Tab này trả lời:

- bot bắt đầu từ scan và bind như thế nào
- frame đi từ capture sang nhận diện ra sao
- lúc nào được phép quyết định
- lúc nào được phép bấm
- sau khi bấm thì xác nhận lại thế nào
- khi lỗi thì recovery ra sao

## Quy tắc dùng cho nhiều agent

Nên theo flow đơn giản này:

1. đọc `00_Overview` trước để biết bối cảnh
2. xem `06_Build_Plan` để biết roadmap build bot
3. xem `07_Runtime_Flow` để biết luồng chạy thực tế
4. xem `01_Task_Board` để biết đang ưu tiên việc gì
5. trước khi sửa lớn, thêm một dòng vào `02_Agent_Notes`
6. nếu muốn đề xuất thay đổi, thêm một dòng vào `03_Change_Requests`
7. khi đã chốt hướng đi, ghi vào `05_Decisions`

## Khuyến nghị an toàn

Vì link đang là public edit:

- không để dữ liệu nhạy cảm trong sheet
- nên khóa hàng tiêu đề của các tab chính
- nên protect tab `00_Overview`
- nên cân nhắc đổi từ public edit sang share theo email khi quy trình đã ổn định

## Khi nào nên chạy seed lại

Nên chạy lại script seed khi:

- muốn reset bố cục bảng chuẩn
- muốn đồng bộ sheet với dữ liệu seed mới trong repo
- có nhiều sửa thử nghiệm làm bảng bị rối

Không nên chạy seed lại nếu:

- người khác đang cập nhật trực tiếp trên các tab chuẩn
- bạn muốn giữ nguyên nội dung thủ công hiện có trong các tab đó

Vì script hiện tại sẽ ghi đè nội dung trên các tab chuẩn của nó.
