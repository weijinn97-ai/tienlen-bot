# Hướng dẫn cài đặt và vận hành Multi-Bot trên Windows

Để chạy nhiều bot Tiến Lên song song trên cùng một hệ thống Windows, bạn cần cấu hình nhiều instance của trình giả lập MEmu và đảm bảo mỗi bot instance có thể tương tác độc lập với một MEmu instance cụ thể. Hướng dẫn này sẽ trình bày các bước cần thiết.

## 1. Chuẩn bị nhiều Instance MEmu

Để chạy nhiều bot, bạn cần có nhiều instance của MEmu. Mỗi instance sẽ chạy một game Tiến Lên độc lập.

1.  **Mở Multi-MEmu:** Mở ứng dụng "Multi-MEmu" (thường được cài đặt cùng với MEmu).
2.  **Tạo hoặc Clone Instance:**
    *   **Clone:** Cách dễ nhất là nhân bản (clone) một instance MEmu đã có sẵn game Tiến Lên và đã được cấu hình (ví dụ: độ phân giải, USB Debugging). Chọn instance bạn muốn nhân bản, sau đó nhấp vào "Clone".
    *   **Tạo mới:** Nếu bạn muốn cấu hình từ đầu, nhấp vào "New" và làm theo hướng dẫn để tạo một instance Android mới, sau đó cài đặt game Tiến Lên và cấu hình USB Debugging như đã hướng dẫn trong `WINDOWS_SETUP_GUIDE.md`.
3.  **Khởi động các Instance:** Khởi động tất cả các instance MEmu mà bạn muốn chạy bot.

## 2. Xác định Device ID của từng Instance MEmu (ADB)

Mỗi instance MEmu sẽ có một Device ID (hoặc địa chỉ IP:Port) riêng biệt mà ADB sử dụng để kết nối.

1.  **Mở Command Prompt/PowerShell:** Mở một cửa sổ Command Prompt hoặc PowerShell.
2.  **Liệt kê thiết bị ADB:** Chạy lệnh sau để xem danh sách các thiết bị ADB đang kết nối:
    ```bash
    adb devices
    ```
3.  **Xác định Device ID:** Bạn sẽ thấy danh sách các thiết bị, ví dụ:
    ```
    List of devices attached
    127.0.0.1:7555    device
    127.0.0.1:7556    device
    127.0.0.1:7557    device
    ```
    Trong ví dụ này, `127.0.0.1:7555`, `127.0.0.1:7556`, `127.0.0.1:7557` là các Device ID của từng instance MEmu. Ghi lại các ID này.

## 3. Xác định Tên cửa sổ và Index của từng Instance MEmu

Mỗi instance MEmu cũng sẽ có một cửa sổ riêng trên Windows. Mặc dù chúng có thể có cùng tên cơ bản (ví dụ: "MEmu"), chúng ta có thể phân biệt chúng bằng thứ tự xuất hiện (index).

1.  **Xác định tên cửa sổ cơ bản:** Tên cửa sổ mặc định của MEmu thường là "MEmu" hoặc "MEmu App Player". Nếu bạn đã đổi tên instance trong Multi-MEmu, tên cửa sổ có thể khác (ví dụ: "MEmu_1", "MEmu_2").
2.  **Sử dụng `windows_capture.py` để kiểm tra:** Bạn có thể tạm thời sửa đổi file `bot/capture/windows_capture.py` để liệt kê các cửa sổ hoặc chạy đoạn code ví dụ trong file đó để xác định tên cửa sổ chính xác và thứ tự của chúng.
    *   Chạy `python bot/capture/windows_capture.py` và quan sát tên cửa sổ hiển thị. Nếu bạn có nhiều cửa sổ MEmu, chúng sẽ được liệt kê theo một thứ tự nhất định.
    *   `window_index` trong `WindowsCapture` class sẽ cho phép bạn chọn cửa sổ thứ `index` (bắt đầu từ 0) có chứa `window_name`.

## 4. Cấu hình và chạy nhiều Bot Instance

Để chạy nhiều bot, bạn sẽ cần khởi tạo nhiều tiến trình bot Python, mỗi tiến trình được cấu hình để tương tác với một instance MEmu cụ thể.

1.  **Tạo file cấu hình riêng cho mỗi bot (Khuyến nghị):**
    Thay vì sửa trực tiếp `configs/agent_config.py`, bạn nên tạo các file cấu hình riêng cho mỗi bot instance, ví dụ: `configs/bot1_config.py`, `configs/bot2_config.py`.
    Trong mỗi file này, bạn sẽ định nghĩa các biến cấu hình như `MEmu_WINDOW_NAME`, `MEmu_WINDOW_INDEX`, `ADB_DEVICE_ID`.

    *Ví dụ `configs/bot1_config.py`:*
    ```python
    # configs/bot1_config.py
    MEmu_WINDOW_NAME = "MEmu"
    MEmu_WINDOW_INDEX = 0 # Instance đầu tiên
    ADB_DEVICE_ID = "127.0.0.1:7555"

    USE_LOCAL_AGENT = True
    # ... các cấu hình agent khác ...
    ```

    *Ví dụ `configs/bot2_config.py`:*
    ```python
    # configs/bot2_config.py
    MEmu_WINDOW_NAME = "MEmu"
    MEmu_WINDOW_INDEX = 1 # Instance thứ hai
    ADB_DEVICE_ID = "127.0.0.1:7556"

    USE_LOCAL_AGENT = False
    # ... các cấu hình agent khác ...
    ```

2.  **Điều chỉnh `main.py` (hoặc tạo script khởi chạy):**
    File `main.py` (hoặc một script khởi chạy khác) sẽ cần được điều chỉnh để đọc cấu hình từ các file riêng biệt và khởi tạo các đối tượng bot tương ứng.

    *Ví dụ về cách khởi chạy nhiều bot:*
    ```python
    # main.py (hoặc run_multi_bot.py)
    import subprocess
    import os

    bot_configs = [
        "configs/bot1_config.py",
        "configs/bot2_config.py",
        # Thêm các cấu hình bot khác tại đây
    ]

    processes = []
    for config_file in bot_configs:
        print(f"Starting bot with configuration: {config_file}")
        # Giả sử bạn có một script bot_instance.py nhận đường dẫn cấu hình làm đối số
        command = ["python", "bot_instance.py", config_file]
        # Chạy mỗi bot trong một tiến trình riêng biệt
        p = subprocess.Popen(command, cwd=os.getcwd())
        processes.append(p)

    for p in processes:
        p.wait() # Chờ tất cả các bot hoàn thành
    ```

    Bạn sẽ cần tạo một file `bot_instance.py` (hoặc tương tự) để đóng gói logic của một bot đơn lẻ, nhận đường dẫn cấu hình làm đối số.

3.  **Khởi chạy từng bot instance:**
    Mở một Command Prompt/PowerShell riêng cho mỗi bot instance và chạy lệnh tương ứng:
    ```bash
    # Cho Bot 1
    python main.py --config configs/bot1_config.py

    # Cho Bot 2
    python main.py --config configs/bot2_config.py
    ```
    (Đây là một ví dụ, cách truyền cấu hình có thể khác tùy thuộc vào cách bạn thiết kế `main.py`).

## 5. Cân nhắc về Tài nguyên hệ thống

Chạy nhiều instance MEmu và nhiều bot cùng lúc sẽ tiêu tốn rất nhiều tài nguyên hệ thống (CPU, RAM, GPU).

*   **CPU và RAM:** Mỗi instance MEmu yêu cầu một lượng CPU và RAM đáng kể. Hãy đảm bảo hệ thống của bạn có đủ tài nguyên để xử lý tất cả các instance mà không bị chậm hoặc crash.
*   **GPU:** Việc chụp màn hình và xử lý hình ảnh (YOLOv8) cũng sẽ sử dụng GPU. Nếu bạn có GPU mạnh, hãy tận dụng nó.
*   **Tối ưu hóa MEmu:** Trong cài đặt của MEmu, bạn có thể giảm số lượng Core CPU và RAM được cấp cho mỗi instance để tiết kiệm tài nguyên, nhưng điều này có thể ảnh hưởng đến hiệu suất của game.
*   **Tối ưu hóa Bot:** Sử dụng `LocalAgent` thay vì `FreeAPIAgent` sẽ giảm tải cho mạng và có thể giảm độ trễ, nhưng vẫn cần tài nguyên CPU/RAM cho việc xử lý cục bộ.

Việc quản lý tài nguyên là rất quan trọng để đảm bảo các bot hoạt động ổn định. Module `system_monitor.py` có thể giúp bạn theo dõi việc sử dụng tài nguyên của từng tiến trình MEmu và của toàn hệ thống để điều chỉnh phù hợp.

Với các bước trên, bạn có thể thiết lập môi trường để chạy nhiều bot Tiến Lên song song, mở ra khả năng thử nghiệm các chiến lược khác nhau hoặc tham gia nhiều bàn chơi cùng lúc.
