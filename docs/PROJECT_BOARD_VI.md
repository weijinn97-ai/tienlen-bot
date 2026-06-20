# Bảng Tiến Độ Dự Án

Cập nhật: 2026-06-21

Tài liệu này là bản tiếng Việt song song với [docs/PROJECT_BOARD.md](/D:/tienlenOPus/tienlen-bot/docs/PROJECT_BOARD.md:1), viết theo kiểu dễ hiểu hơn cho người không chuyên kỹ thuật.

## Mục tiêu của dự án

Chúng ta đang xây một bot Tiến Lên chạy trên giả lập MEmu sao cho:

- mỗi bot gắn đúng với đúng một giả lập
- bot không bị nhầm cửa sổ hoặc nhầm ADB
- khi một bot lỗi thì không kéo sập toàn bộ hệ thống
- có thể nhìn log và biết bot đang làm gì
- về sau có thể mở rộng nhiều bot cùng lúc

## Hiện tại chúng ta đang ở đâu?

Mốc hiện tại: `M1 - Nền tảng chạy bot và bảng điều khiển`

Hiểu đơn giản là:

- đã có bộ khung để quản lý bot
- đã có cách nhận diện đúng giả lập đang chạy
- đã có launcher để bấm chạy bot
- đã có log để theo dõi bot
- nhưng bot vẫn chưa “đánh bài thật”

## Cách đọc trạng thái

- `Đã xong`: đã làm xong và đã test tại máy local
- `Đang làm`: đã có phần nền, nhưng vẫn cần hoàn thiện thêm
- `Làm tiếp`: là phần nên ưu tiên làm ngay sau đây
- `Đang chờ`: bị chặn bởi quyết định hoặc phụ thuộc khác

## Giải thích nhanh vài từ kỹ thuật

- `ADB`: kênh để máy tính bấm/chạm điều khiển giả lập Android
- `HWND`: mã nhận diện cửa sổ trong Windows
- `PID`: mã tiến trình đang chạy
- `Capture`: chụp hình từ cửa sổ giả lập
- `Perception`: nhận diện xem trên màn hình đang có gì
- `Decision`: bot quyết định nên làm gì
- `Action`: bot thực hiện thao tác bấm/chạm

## Bảng tiến độ dễ hiểu

| Mã | Hạng mục | Trạng thái | Mức quan trọng | Hiện đã có gì | Cần làm tiếp |
|---|---|---|---|---|---|
| M1.1 | Khung chạy bot | Đã xong | Cao | Đã có supervisor, worker, frame schema, validate, ADB broker, inference scaffold | Nối khung này vào vòng chơi thật |
| M1.2 | Dọn hot path ADB | Đã xong | Cao | ADB không còn dùng để chụp ảnh nữa, chỉ dùng điều khiển và health check | Bổ sung action thật và retry tốt hơn |
| M1.3 | Quét đúng giả lập MEmu | Đã xong | Cao | Đã map được `vm_index / title / pid / hwnd / adb_serial / android_serial` | Lưu kết quả chọn vào file config |
| M1.4 | Launcher cho người vận hành | Đã xong | Cao | Có giao diện chọn giả lập, chạy/dừng bot, xem log, copy binding | Thêm preview ảnh và profile lưu sẵn |
| M1.5 | Log dễ đọc hơn | Đang làm | Vừa | Log đã ưu tiên `title` thay vì IP, watchdog đã gọn hơn | Thêm màu, lọc log, lưu log ra file |
| M1.6 | Dừng bot cho đẹp | Đang làm | Vừa | Có thể bấm stop bot | Làm stop mềm để không ra exit code xấu |
| M2.1 | Chụp ảnh thật từ giả lập | Làm tiếp | Cao | Đã có scaffold chụp theo cửa sổ | Thêm backend chụp ảnh chuẩn để xem preview/live frame |
| M2.2 | Kiểm tra snapshot đúng/sai | Đang làm | Cao | Đã có validate cơ bản | Thêm rule kiểm tra bài, lượt, anchor thật từ game |
| M2.3 | Nhận diện màn hình game | Làm tiếp | Cao | Đã có service inference dạng khung | Nối YOLO/OCR thật vào từng bot |
| M2.4 | Rút ra trạng thái game | Làm tiếp | Cao | Đã có adapter đơn giản | Parse trạng thái thật từ kết quả nhận diện |
| M3.1 | Bot quyết định đánh gì | Làm tiếp | Cao | Có local agent dạng placeholder | Thay bằng luật/chính sách Tiến Lên thật |
| M3.2 | Bot bấm/chạm thật | Làm tiếp | Cao | Action executor mới là khung | Map tọa độ lá bài/nút bấm và thực thi thật |
| M3.3 | Xác nhận thao tác sau khi bấm | Làm tiếp | Cao | Kiến trúc đã chừa chỗ | Sau mỗi thao tác, xác nhận lại bằng hình ảnh |
| M4.1 | Chạy nhiều bot thật sự | Làm tiếp | Cao | Kiến trúc hỗ trợ về mặt ý tưởng | Cho supervisor khởi chạy nhiều worker thật |
| M4.2 | Quản lý tài nguyên máy | Đang làm | Vừa | Có system monitor và limit cơ bản | Thêm ngưỡng CPU/RAM/GPU và giảm tải thông minh |
| M4.3 | Tự hồi phục khi bot lỗi | Làm tiếp | Vừa | Có circuit breaker và ý tưởng restart riêng lẻ | Tự pause/restart theo chính sách rõ ràng |
| M5.1 | Lưu cấu hình người dùng | Làm tiếp | Vừa | Đã copy được binding stub | Lưu bot đã chọn và cấu hình vào file |
| M5.2 | Test đầy đủ hơn | Đang làm | Vừa | Đã có test parser và core invariants | Thêm test GUI và test capture/action |

## Những gì hiện đã dùng được

Hiện tại bạn có thể dùng ổn các phần sau:

1. Quét giả lập MEmu đang chạy.
2. Nhìn tên giả lập để chọn đúng instance thay vì nhớ IP:port.
3. Mở launcher bằng icon/shortcut để chạy bot session.
4. Xem log realtime để biết bot còn bám đúng cửa sổ và ADB hay không.

## Những gì chưa xong

Đây là các phần lớn còn thiếu trước khi bot thực sự đánh bài:

1. Chụp ảnh màn hình game thật trong flow live.
2. Nhận diện lá bài, nút bấm, lượt chơi.
3. Hiểu trạng thái game từ ảnh.
4. Ra quyết định đánh bài thật.
5. Bấm/chạm thật và xác nhận lại bằng ảnh.

## Thứ tự nên làm tiếp

Để ít bị làm đi làm lại, nên đi theo thứ tự này:

1. `M1.6` Làm stop mềm và polish launcher.
2. `M2.1` Thêm live preview ảnh giả lập trong launcher.
3. `M2.3` Nối pipeline nhận diện YOLO/OCR.
4. `M2.4` Parse trạng thái game.
5. `M3.2` Làm thao tác bấm/chạm thật.
6. `M3.3` Xác nhận thao tác bằng ảnh.
7. `M3.1` Làm decision engine thật.
8. `M4.1` Chạy nhiều bot từ supervisor.

## Nếu nhiều agent cùng làm thì nên chia thế nào?

| Nhóm | Nên phụ trách | Có thể làm song song với |
|---|---|---|
| A | giao diện launcher, log, lưu config | B, C |
| B | chụp ảnh và preview | A, C |
| C | nhận diện và đọc trạng thái game | A, B |
| D | thao tác bấm/chạm và xác nhận | A sau khi contract capture/state ổn |
| E | supervisor multi-bot và tài nguyên | A, C sau khi contract ổn định |

## Rủi ro hiện tại

1. Session hiện giờ vẫn là session theo dõi và watchdog, chưa phải bot chơi thật.
2. Capture hiện chưa phải backend production cuối cùng.
3. Nút stop vẫn cần làm mềm hơn.
4. Tọa độ thao tác thật sẽ cần căn chỉnh theo layout giả lập.

## Demo có ý nghĩa tiếp theo nên trông như thế nào?

Một demo “tiến thêm 1 bước thật sự” nên làm được cùng lúc các việc sau:

1. Hiển thị preview ảnh live của giả lập đã chọn.
2. Nhận diện được ít nhất một thông tin ổn định trên màn hình.
3. Ghi thông tin đó vào log trong launcher.
4. Thực hiện một thao tác test an toàn và xác nhận lại bằng ảnh.

## Kết luận ngắn gọn cho người không chuyên

Hiện tại dự án đã xong phần “khung vận hành”:

- chọn đúng giả lập
- chạy bot session
- xem bot còn sống hay không
- xem log để biết bot đang bám đúng cửa sổ

Phần chưa xong là “não và mắt tay” của bot:

- mắt: nhìn màn hình và hiểu game
- não: quyết định đánh gì
- tay: bấm đúng và kiểm tra lại sau khi bấm
