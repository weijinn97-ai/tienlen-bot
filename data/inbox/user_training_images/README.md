# User Training Images Inbox

## Thư mục nhận ảnh

- `raw/fullscreen/`: ảnh chụp nguyên màn hình game. Đây là loại ưu tiên.
- `raw/my_hand/`: ảnh đã crop chỉ chứa 13 lá hoặc phần bài trên tay của bot.
- `raw/table_plays/`: ảnh đã crop chỉ chứa bài đối thủ/bot vừa đánh ra giữa bàn.
- `raw/buttons_ui/`: ảnh tập trung vào nút Đánh, Bỏ Lượt và trạng thái enabled/disabled.

Nếu ảnh của bạn là screenshot nguyên màn hình có cả bài trên tay và bài giữa bàn, hãy đặt vào `raw/fullscreen/`, không cần tự tách.

Yêu cầu:

- giữ nguyên ảnh, không crop hoặc chỉnh sửa
- chấp nhận `.png`, `.jpg`, `.jpeg`
- có thể dùng tên file bất kỳ, nhưng không trùng nhau
- nếu có nhiều độ phân giải, vẫn đặt chung; pipeline sẽ phân loại sau

Không cần tự vẽ bbox. Không cần điền metadata nếu việc đó bất tiện.

## Quy tắc label sẽ dùng

- Bài trên tay được gắn zone `MY_HAND`.
- Bài đang được chọn/nhô lên được gắn zone `SELECTED`.
- Bài vừa đánh giữa bàn được gắn zone `TABLE_PLAY`.
- Mỗi object vẫn dùng card code chuẩn như `3S`, `10D`, `AH`, `2H`.
- Dataset split và augmentation của `MY_HAND` và `TABLE_PLAY` được đánh giá riêng; không dùng kết quả tốt ở hand để suy ra model đã nhận đúng bài giữa bàn.

Khi đã chép ảnh xong, chỉ cần báo: `đã gửi xong ảnh`. Agent sẽ kiểm kê riêng từng zone, loại ảnh trùng, tạo batch và báo số lượng trước khi bắt đầu label/train.
