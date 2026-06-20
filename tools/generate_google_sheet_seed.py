from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "google_sheet_seed"
SHEET_LINK = "https://docs.google.com/spreadsheets/d/1pQ8eU043r1phOG67BsO9gDmUK2TKjVAZPSz6MccJ_vc/edit?gid=0#gid=0"
UPDATED_DATE = "2026-06-21"


@dataclass(frozen=True)
class SheetFile:
    filename: str
    headers: list[str]
    rows: list[list[str]]


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    sheet_files = [
        build_overview_sheet(),
        build_task_board_sheet(),
        build_agent_notes_sheet(),
        build_change_requests_sheet(),
        build_daily_status_sheet(),
        build_decisions_sheet(),
    ]

    for sheet_file in sheet_files:
        write_csv(sheet_file)

    print(f"Generated {len(sheet_files)} Google Sheets seed files in: {OUTPUT_DIR}")
    return 0


def build_overview_sheet() -> SheetFile:
    return SheetFile(
        filename="00_Overview.csv",
        headers=["Mục", "Giá trị"],
        rows=[
            ["Tên dự án", "TienLen Bot"],
            ["Link Google Sheet", SHEET_LINK],
            ["Ngày cập nhật", UPDATED_DATE],
            ["Milestone hiện tại", "M1 - Nền tảng chạy bot và bảng điều khiển"],
            [
                "Trạng thái ngắn",
                "Đã có launcher, scan giả lập, log realtime. Chưa xong capture preview, perception, decision, action thật.",
            ],
            [
                "Mục tiêu gần nhất",
                "Làm launcher tốt hơn, thêm preview ảnh live, rồi nối perception và action thật.",
            ],
            [
                "Bước tiếp theo khuyến nghị",
                "1) Graceful stop, 2) Live preview, 3) Perception pipeline, 4) State extraction, 5) Action execution",
            ],
            [
                "Ghi chú cho agent",
                "Mọi agent nên cập nhật Notes hoặc Change Requests trước khi sửa phần lớn để tránh đụng nhau.",
            ],
        ],
    )


def build_task_board_sheet() -> SheetFile:
    headers = [
        "Task_ID",
        "Nhóm",
        "Hạng_mục",
        "Trạng_thái",
        "Ưu_tiên",
        "Đã_có",
        "Cần_làm_tiếp",
        "Chủ_sở_hữu",
        "Phụ_thuộc",
        "Ghi_chú",
    ]
    rows = [
        [
            "M1.1",
            "Nền tảng",
            "Khung chạy bot",
            "Đã xong",
            "Cao",
            "Đã có supervisor, worker, frame schema, validation, ADB broker, inference scaffold",
            "Nối khung này vào vòng chơi thật",
            "",
            "",
            "",
        ],
        [
            "M1.2",
            "ADB",
            "Dọn hot path ADB",
            "Đã xong",
            "Cao",
            "ADB không còn dùng để chụp ảnh; chỉ điều khiển và health check",
            "Bổ sung action thật và retry theo loại thao tác",
            "",
            "",
            "",
        ],
        [
            "M1.3",
            "Nhận diện giả lập",
            "Quét đúng giả lập MEmu",
            "Đã xong",
            "Cao",
            "Map được vm_index, title, pid, hwnd, adb_serial, android_serial",
            "Lưu binding đã chọn vào config",
            "",
            "",
            "",
        ],
        [
            "M1.4",
            "UI",
            "Launcher cho người vận hành",
            "Đã xong",
            "Cao",
            "Có giao diện chọn giả lập, chạy dừng bot, xem log, copy binding",
            "Thêm preview ảnh và profile lưu sẵn",
            "",
            "",
            "",
        ],
        [
            "M1.5",
            "UI",
            "Log dễ đọc hơn",
            "Đang làm",
            "Vừa",
            "Log đã ưu tiên title thay vì IP, watchdog đã gọn hơn",
            "Thêm màu, lọc log, lưu log",
            "",
            "",
            "",
        ],
        [
            "M1.6",
            "UI",
            "Graceful stop",
            "Đang làm",
            "Vừa",
            "Đã có nút stop",
            "Dừng mềm để không còn exit code xấu",
            "",
            "",
            "",
        ],
        [
            "M2.1",
            "Capture",
            "Chụp ảnh thật từ giả lập",
            "Làm tiếp",
            "Cao",
            "Đã có scaffold chụp theo cửa sổ",
            "Thêm Windows Graphics Capture và live preview",
            "",
            "M1.4",
            "",
        ],
        [
            "M2.2",
            "Validation",
            "Kiểm tra snapshot đúng sai",
            "Đang làm",
            "Cao",
            "Đã có validate cơ bản",
            "Thêm rule kiểm tra bài, lượt, anchor thật",
            "",
            "M2.1",
            "",
        ],
        [
            "M2.3",
            "Perception",
            "Nhận diện màn hình game",
            "Làm tiếp",
            "Cao",
            "Đã có inference service scaffold",
            "Nối YOLO OCR thật vào từng bot",
            "",
            "M2.1",
            "",
        ],
        [
            "M2.4",
            "State",
            "Rút ra trạng thái game",
            "Làm tiếp",
            "Cao",
            "Đã có adapter đơn giản",
            "Parse trạng thái game từ kết quả nhận diện",
            "",
            "M2.3",
            "",
        ],
        [
            "M3.1",
            "Decision",
            "Bot quyết định đánh gì",
            "Làm tiếp",
            "Cao",
            "Có local agent placeholder",
            "Thay bằng luật hoặc policy Tiến Lên thật",
            "",
            "M2.4",
            "",
        ],
        [
            "M3.2",
            "Action",
            "Bot bấm chạm thật",
            "Làm tiếp",
            "Cao",
            "Action executor mới là khung",
            "Map tọa độ bài và nút bấm",
            "",
            "M2.4",
            "",
        ],
        [
            "M3.3",
            "Action",
            "Xác nhận thao tác sau khi bấm",
            "Làm tiếp",
            "Cao",
            "Kiến trúc đã chừa chỗ",
            "Xác nhận lại bằng ảnh sau mỗi action",
            "",
            "M3.2",
            "",
        ],
        [
            "M4.1",
            "Multi-bot",
            "Chạy nhiều bot thật sự",
            "Làm tiếp",
            "Cao",
            "Kiến trúc đã hỗ trợ về mặt ý tưởng",
            "Cho supervisor khởi chạy nhiều worker thật",
            "",
            "M3.3",
            "",
        ],
        [
            "M4.2",
            "Tài nguyên",
            "Quản lý tài nguyên máy",
            "Đang làm",
            "Vừa",
            "Có system monitor và limit cơ bản",
            "Thêm ngưỡng CPU RAM GPU và giảm tải thông minh",
            "",
            "M4.1",
            "",
        ],
        [
            "M4.3",
            "Recovery",
            "Tự hồi phục khi bot lỗi",
            "Làm tiếp",
            "Vừa",
            "Có circuit breaker và ý tưởng restart riêng lẻ",
            "Tự pause restart theo chính sách rõ ràng",
            "",
            "M4.1",
            "",
        ],
        [
            "M5.1",
            "Config",
            "Lưu cấu hình người dùng",
            "Làm tiếp",
            "Vừa",
            "Đã copy được binding stub",
            "Lưu bot đã chọn và cấu hình ra file",
            "",
            "M1.4",
            "",
        ],
        [
            "M5.2",
            "Test",
            "Test đầy đủ hơn",
            "Đang làm",
            "Vừa",
            "Đã có parser tests và core invariant tests",
            "Thêm UI smoke test và capture action integration test",
            "",
            "",
            "",
        ],
    ]
    return SheetFile(filename="01_Task_Board.csv", headers=headers, rows=rows)


def build_agent_notes_sheet() -> SheetFile:
    return SheetFile(
        filename="02_Agent_Notes.csv",
        headers=[
            "Timestamp",
            "Agent",
            "Task_ID",
            "Tiêu_đề",
            "Ghi_chú",
            "Mức_độ",
            "Cần_phản_hồi",
            "Người_tạo",
        ],
        rows=[],
    )


def build_change_requests_sheet() -> SheetFile:
    return SheetFile(
        filename="03_Change_Requests.csv",
        headers=[
            "Request_ID",
            "Ngày",
            "Người_yêu_cầu",
            "Task_ID_liên_quan",
            "Tiêu_đề",
            "Mô_tả",
            "Ưu_tiên",
            "Trạng_thái",
            "Người_xử_lý",
            "Kết_quả",
        ],
        rows=[],
    )


def build_daily_status_sheet() -> SheetFile:
    return SheetFile(
        filename="04_Daily_Status.csv",
        headers=[
            "Ngày",
            "Milestone",
            "Tóm_tắt_hôm_nay",
            "Đã_xong",
            "Đang_làm",
            "Tiếp_theo",
            "Blocker",
            "Người_cập_nhật",
        ],
        rows=[
            [
                UPDATED_DATE,
                "M1 - Nền tảng chạy bot và bảng điều khiển",
                "Đã có launcher, scan giả lập, log realtime, project board song ngữ",
                "Launcher UI, discovery tools, project board, board tiếng Việt",
                "Log readability, graceful stop",
                "Live preview capture rồi perception pipeline",
                "",
                "Codex",
            ]
        ],
    )


def build_decisions_sheet() -> SheetFile:
    return SheetFile(
        filename="05_Decisions.csv",
        headers=[
            "Decision_ID",
            "Ngày",
            "Chủ_đề",
            "Quyết_định",
            "Lý_do",
            "Ảnh_hưởng",
            "Người_chốt",
        ],
        rows=[
            [
                "D-001",
                UPDATED_DATE,
                "Kiến trúc bot",
                "Một bot bằng một process độc lập, chia sẻ inference service và ADB broker",
                "Ổn định hơn, tránh kéo sập toàn cụm khi một bot lỗi",
                "Tất cả agent nên bám theo kiến trúc actor-based này",
                "User + Codex",
            ],
            [
                "D-002",
                UPDATED_DATE,
                "Định danh giả lập",
                "Ưu tiên title, vm_index, pid, hwnd và adb_serial; không map theo vị trí cửa sổ",
                "Giảm nhầm bot với nhầm giả lập",
                "Mọi binding và log nên dùng title làm định danh chính",
                "User + Codex",
            ],
        ],
    )


def write_csv(sheet_file: SheetFile) -> None:
    output_path = OUTPUT_DIR / sheet_file.filename
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(sheet_file.headers)
        writer.writerows(sheet_file.rows)


if __name__ == "__main__":
    raise SystemExit(main())
