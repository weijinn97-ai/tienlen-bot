# Hướng dẫn cài đặt và vận hành Bot Tiến Lên trên Windows

Để bot Tiến Lên có thể hoạt động ổn định và độc lập trên hệ điều hành Windows 10 hoặc 11, bạn cần thực hiện các bước cài đặt môi trường và cấu hình sau đây.

## 1. Cài đặt Python và Môi trường ảo

Bot được phát triển bằng Python, vì vậy bạn cần cài đặt Python trên hệ thống của mình.

1.  **Tải và cài đặt Python:**
    *   Tru cập trang web chính thức của Python: [https://www.python.org/downloads/windows/](https://www.python.org/downloads/windows/)
    *   Tải xuống phiên bản Python 3.8 trở lên (khuyến nghị phiên bản ổn định mới nhất, ví dụ: Python 3.10 hoặc 3.11).
    *   Trong quá trình cài đặt, **rất quan trọng** là bạn phải chọn tùy chọn "Add Python to PATH" (hoặc "Add Python X.Y to PATH") để có thể chạy Python từ Command Prompt hoặc PowerShell.

2.  **Tạo và kích hoạt môi trường ảo (Virtual Environment):**
    Môi trường ảo giúp quản lý các thư viện Python của dự án một cách độc lập, tránh xung đột với các dự án Python khác.
    *   Mở Command Prompt (CMD) hoặc PowerShell.
    *   Điều hướng đến thư mục gốc của dự án `tienlen-bot`:
        ```bash
        cd path/to/your/tienlen-bot
        ```
    *   Tạo môi trường ảo:
        ```bash
        python -m venv venv
        ```
    *   Kích hoạt môi trường ảo:
        ```bash
        # Trên Windows CMD
        .\venv\Scripts\activate
        
        # Trên Windows PowerShell
        .\venv\Scripts\Activate.ps1
        ```
        (Bạn sẽ thấy `(venv)` xuất hiện ở đầu dòng lệnh, cho biết môi trường ảo đã được kích hoạt).

3.  **Cài đặt các thư viện Python cần thiết:**
    Sau khi kích hoạt môi trường ảo, cài đặt các thư viện Python mà bot sử dụng:
    ```bash
    pip install numpy opencv-python mss psutil pywin32 requests ultralytics
    ```
    *   `numpy`: Thư viện tính toán số học.
    *   `opencv-python`: Xử lý hình ảnh và video.
    *   `mss`: Chụp màn hình nhanh chóng trên Windows.
    *   `psutil`: Giám sát tài nguyên hệ thống và tiến trình.
    *   `pywin32`: Cung cấp quyền truy cập vào các API của Windows (được sử dụng bởi `windows_capture.py`).
    *   `requests`: Thực hiện các yêu cầu HTTP cho Free API Agent.
    *   `ultralytics`: Thư viện chính cho YOLOv8.

## 2. Cài đặt và cấu hình ADB (Android Debug Bridge)

ADB là công cụ cần thiết để bot có thể giao tiếp và điều khiển trình giả lập MEmu.

1.  **Tải xuống Platform-Tools (bao gồm ADB):**
    *   Tru cập trang web chính thức của Android Developers: [https://developer.android.com/tools/releases/platform-tools](https://developer.android.com/tools/releases/platform-tools)
    *   Tải xuống gói "SDK Platform-Tools for Windows".
    *   Giải nén file ZIP vào một thư mục dễ nhớ, ví dụ: `C:\platform-tools`.

2.  **Thêm ADB vào biến môi trường PATH (tùy chọn nhưng khuyến nghị):**
    Việc này giúp bạn có thể chạy lệnh `adb` từ bất kỳ đâu trong Command Prompt.
    *   Tìm kiếm "Edit the system environment variables" trong Windows Search và mở nó.
    *   Nhấp vào "Environment Variables..." ở dưới cùng.
    *   Trong phần "System variables", tìm biến `Path`, chọn và nhấp "Edit...".
    *   Nhấp "New" và thêm đường dẫn đến thư mục `platform-tools` của bạn (ví dụ: `C:\platform-tools`).
    *   Nhấp "OK" trên tất cả các cửa sổ để lưu thay đổi.
    *   Khởi động lại Command Prompt/PowerShell để thay đổi có hiệu lực.

3.  **Kiểm tra kết nối ADB:**
    *   Mở Command Prompt/PowerShell và chạy lệnh:
        ```bash
        adb devices
        ```
    *   Nếu ADB được cài đặt đúng, bạn sẽ thấy danh sách các thiết bị Android đang kết nối. Ban đầu có thể là trống.

## 3. Cấu hình Trình giả lập MEmu

MEmu là trình giả lập Android mà bot sẽ tương tác. Đảm bảo MEmu được cấu hình đúng cách.

1.  **Cài đặt MEmu:**
    *   Tải xuống và cài đặt MEmu từ trang web chính thức: [https://www.memuplay.com/](https://www.memuplay.com/)
    *   Cài đặt game Tiến Lên vào MEmu.

2.  **Bật chế độ gỡ lỗi USB (USB Debugging):**
    *   Mở MEmu, vào **Settings** (trong Android) -> **About tablet** (hoặc **About phone**).
    *   Nhấp liên tục vào "Build number" (hoặc "Số bản dựng") khoảng 7 lần cho đến khi bạn thấy thông báo "You are now a developer!" (hoặc "Bạn đã là nhà phát triển!").
    *   Quay lại **Settings**, bạn sẽ thấy mục "Developer options" (hoặc "Tùy chọn nhà phát triển").
    *   Vào "Developer options" và bật "USB debugging" (hoặc "Gỡ lỗi USB").

3.  **Kết nối MEmu với ADB:**
    *   Mở Command Prompt/PowerShell (trong môi trường ảo đã kích hoạt).
    *   Chạy lệnh để kết nối ADB với MEmu. MEmu thường chạy trên cổng 7555 (hoặc một cổng khác, bạn có thể kiểm tra trong cài đặt MEmu).
        ```bash
        adb connect 127.0.0.1:7555
        ```
    *   Sau đó, kiểm tra lại các thiết bị:
        ```bash
        adb devices
        ```
        Bạn sẽ thấy `127.0.0.1:7555 device` xuất hiện trong danh sách.

4.  **Cấu hình độ phân giải MEmu (Khuyến nghị):**
    Để đảm bảo nhận diện hình ảnh chính xác, nên đặt độ phân giải của MEmu ở một giá trị cố định và phù hợp với dữ liệu huấn luyện YOLOv8. Ví dụ: 1280x720 hoặc 1920x1080.
    *   Trong MEmu, vào **Settings** -> **Engine** -> **Resolution**.
    *   Chọn độ phân giải mong muốn và khởi động lại MEmu.

## 4. Vận hành Bot

Sau khi đã cài đặt môi trường, bạn có thể chạy bot.

1.  **Cấu hình Agent:**
    *   Mở file `configs/agent_config.py`.
    *   Giữ `USE_LOCAL_AGENT = True` để dùng agent cục bộ mặc định, hoặc đặt biến môi trường `TIENLEN_USE_LOCAL_AGENT=false` để chuyển sang agent API.
    *   Nếu sử dụng Free API Agent, hãy đặt biến môi trường `TIENLEN_FREE_API_KEY` và `TIENLEN_FREE_API_ENDPOINT`. Có thể đặt thêm `TIENLEN_FREE_API_MODEL` nếu cần.

2.  **Chạy Bot:**
    *   Đảm bảo MEmu đang chạy và game Tiến Lên đang ở màn hình chơi.
    *   Trong Command Prompt/PowerShell (với môi trường ảo đã kích hoạt), điều hướng đến thư mục gốc của dự án `tienlen-bot`.
    *   Chạy file `main.py` (file này sẽ là điểm khởi đầu chính của bot, sẽ được phát triển sau):
        ```bash
        python main.py
        ```

## 5. Khắc phục sự cố (Troubleshooting)

*   **`ModuleNotFoundError`:** Đảm bảo bạn đã kích hoạt môi trường ảo và cài đặt tất cả các thư viện cần thiết bằng `pip install -r requirements.txt` (file `requirements.txt` sẽ được tạo sau).
*   **ADB không kết nối:**
    *   Kiểm tra xem ADB đã được thêm vào PATH chưa.
    *   Đảm bảo MEmu đang chạy và chế độ gỡ lỗi USB đã được bật.
    *   Thử khởi động lại MEmu và chạy lại `adb connect 127.0.0.1:7555`.
    *   Đảm bảo không có tường lửa nào chặn cổng 7555.
*   **Bot không nhận diện được cửa sổ MEmu:**
    *   Kiểm tra chính xác tên cửa sổ của MEmu. Bạn có thể dùng các công cụ như `Spy++` (trong Visual Studio) hoặc `AutoIt Window Info` để lấy tên chính xác.
    *   Cập nhật tên cửa sổ trong code (ví dụ: trong `bot/capture/windows_capture.py`).
*   **Hiệu suất thấp:**
    *   Đảm bảo MEmu được cấp đủ tài nguyên (CPU, RAM) trong cài đặt của nó.
    *   Giảm độ phân giải của MEmu.
    *   Đóng các ứng dụng không cần thiết trên máy tính của bạn.
    *   Nếu sử dụng Free API Agent, độ trễ có thể do API. Cân nhắc chuyển sang Local Agent hoặc tối ưu hóa prompt.

Với hướng dẫn này, bạn sẽ có thể thiết lập môi trường và chạy bot Tiến Lên trên hệ thống Windows của mình một cách hiệu quả.))
