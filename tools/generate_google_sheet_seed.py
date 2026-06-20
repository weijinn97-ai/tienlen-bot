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
        build_detailed_plan_sheet(),
        build_runtime_flow_sheet(),
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
            ["Tab nên xem nếu cần plan chi tiết", "06_Build_Plan và 07_Runtime_Flow"],
            [
                "Ghi chú cho agent",
                "Mọi agent nên cập nhật Notes hoặc Change Requests trước khi sửa phần lớn để tránh đụng nhau.",
            ],
        ],
    )


def build_task_board_sheet() -> SheetFile:
    return SheetFile(
        filename="01_Task_Board.csv",
        headers=[
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
        ],
        rows=[
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
        ],
    )


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


def build_detailed_plan_sheet() -> SheetFile:
    return SheetFile(
        filename="06_Build_Plan.csv",
        headers=[
            "Pha",
            "Step_ID",
            "Hạng_mục",
            "Mục_tiêu",
            "Đầu_vào",
            "Đầu_ra",
            "Phụ_thuộc",
            "Ưu_tiên",
            "Trạng_thái",
            "Cách_kiểm_tra",
            "Nhóm_có_thể_làm",
        ],
        rows=[
            [
                "P0",
                "BP0",
                "Khóa nguyên tắc và tracking",
                "Chốt rule kiến trúc, rule nhiều agent, bảng theo dõi và cách làm việc chung",
                "CLAUDE.md, project board, Google Sheet",
                "Toàn đội làm cùng một hướng, ít đụng nhau",
                "",
                "Cao",
                "Đã xong",
                "CLAUDE.md có rule riêng cho dự án; Sheet có tab overview, task board, notes",
                "A, E",
            ],
            [
                "P1",
                "BP1",
                "Launcher vận hành tốt",
                "Người dùng chọn đúng giả lập, chạy bot, dừng bot, đọc log dễ hiểu",
                "Launcher hiện tại, scan MEmu/ADB, log panel",
                "Launcher ổn định cho 1 bot và người dùng non-tech dùng được",
                "BP0",
                "Cao",
                "Đang làm",
                "Chạy launcher, chọn đúng title giả lập, start/stop không lỗi xấu, log đọc được",
                "A",
            ],
            [
                "P1",
                "BP2",
                "Lưu cấu hình người dùng",
                "Nhớ instance đã chọn và profile bot để lần sau mở lên dùng nhanh",
                "Binding stub, config path",
                "Có file config lưu instance hoặc profile đã chọn",
                "BP1",
                "Vừa",
                "Làm tiếp",
                "Tắt mở launcher vẫn thấy cấu hình đã lưu",
                "A",
            ],
            [
                "P2",
                "BP3",
                "Capture production backend",
                "Lấy ảnh thật từ đúng cửa sổ giả lập bằng Windows-side capture",
                "HWND binding, capture scaffold",
                "Live frame ổn định, không dùng adb screencap",
                "BP1",
                "Cao",
                "Làm tiếp",
                "Launcher hiện preview live; frame rate đổi theo state; không có ảnh trung gian trên đĩa",
                "B",
            ],
            [
                "P2",
                "BP4",
                "Identity recheck trên ảnh",
                "Đảm bảo bot vẫn đang nhìn đúng giả lập sau khi capture chạy live",
                "Frame capture, window title, fingerprint vùng name/avatar/room",
                "Cảnh báo hoặc pause khi identity sai",
                "BP3",
                "Cao",
                "Làm tiếp",
                "Che, đổi hoặc lệch cửa sổ phải bị phát hiện; bot không tiếp tục trong trạng thái mơ hồ",
                "B, E",
            ],
            [
                "P3",
                "BP5",
                "Perception pipeline",
                "Nhận diện lá bài, nút bấm, text, lượt chơi từ frame",
                "Capture live, ROI, inference scaffold",
                "Kết quả detect hoặc OCR có bot_id và frame_id rõ ràng",
                "BP3",
                "Cao",
                "Làm tiếp",
                "Một frame mẫu trả ra object detect hoặc OCR đúng contract",
                "C",
            ],
            [
                "P3",
                "BP6",
                "State extraction",
                "Chuyển kết quả nhận diện thành trạng thái game mà bot hiểu được",
                "Output từ perception",
                "Game state chuẩn hóa: bài trên tay, bài trên bàn, lượt, nút khả dụng",
                "BP5",
                "Cao",
                "Làm tiếp",
                "Nhiều snapshot mẫu parse ra state đúng như màn hình thật",
                "C",
            ],
            [
                "P3",
                "BP7",
                "Snapshot validator và consensus",
                "Không cho bot quyết định từ frame lỗi hoặc state vô lý",
                "Game state, frame history",
                "State chỉ được tin khi ổn định qua 2-3 frame và pass validator",
                "BP6",
                "Cao",
                "Đang làm",
                "Frame lỗi bị loại; duplicate card, anchor sai, state nhảy vô lý đều bị chặn",
                "C, E",
            ],
            [
                "P4",
                "BP8",
                "Action execution thật",
                "Bot biết bấm lá bài, nút đánh, nút bỏ lượt đúng vị trí",
                "ADB broker, layout mapping, validated state",
                "Tap hoặc swipe đúng, có retry hợp lý, không burst ADB",
                "BP6",
                "Cao",
                "Làm tiếp",
                "Gửi lệnh qua ADB broker và thấy thao tác đúng trên giả lập",
                "D",
            ],
            [
                "P4",
                "BP9",
                "Xác nhận sau thao tác",
                "Sau mỗi action phải nhìn lại ảnh để biết thao tác có thành công hay chưa",
                "Action result, new frame",
                "Không bấm lặp mù; biết pass hoặc fail từng action",
                "BP8",
                "Cao",
                "Làm tiếp",
                "Sau tap, ảnh mới phản ánh thay đổi mong đợi hoặc báo fail rõ ràng",
                "D, B",
            ],
            [
                "P5",
                "BP10",
                "Decision engine Tiến Lên",
                "Bot chọn nước đi hợp lệ và hợp lý theo luật hoặc chiến lược",
                "Validated game state",
                "Danh sách action hợp lệ và action được chọn",
                "BP7",
                "Cao",
                "Làm tiếp",
                "Nhiều state mẫu cho ra quyết định hợp lệ, không crash, không đánh sai luật",
                "C, D",
            ],
            [
                "P5",
                "BP11",
                "Single-bot end-to-end",
                "Một bot hoàn chỉnh nhìn màn hình, hiểu game, quyết định và bấm thật",
                "BP3 đến BP10",
                "Bot chơi được một phiên hoàn chỉnh ở mức demo",
                "BP9, BP10",
                "Cao",
                "Làm tiếp",
                "Chạy một session thật có log đầy đủ và không cần thao tác tay giữa chừng",
                "A, B, C, D",
            ],
            [
                "P6",
                "BP12",
                "Multi-bot supervision",
                "Supervisor khởi chạy nhiều worker thật mà không lẫn identity",
                "Single-bot flow ổn định",
                "Nhiều bot chạy riêng process, restart hoặc pause tách biệt",
                "BP11",
                "Cao",
                "Làm tiếp",
                "2-3 bot chạy đồng thời, bot lỗi không kéo bot khác chết theo",
                "E",
            ],
            [
                "P6",
                "BP13",
                "Resource control và recovery",
                "Giữ hệ thống không sập khi CPU, RAM, GPU hoặc ADB bị quá tải",
                "Supervisor, monitor, broker, watchdog",
                "Admission control, circuit breaker, restart policy rõ ràng",
                "BP12",
                "Vừa",
                "Làm tiếp",
                "Khi quá tải thì bot ưu tiên thấp giảm nhịp hoặc pause thay vì toàn cụm crash",
                "E",
            ],
            [
                "P7",
                "BP14",
                "Hardening và release nội bộ",
                "Củng cố test, docs, preset và cách vận hành thực tế",
                "Tất cả phần trước",
                "Bản dùng nội bộ ổn định hơn cho nhiều agent và người vận hành",
                "BP12, BP13",
                "Vừa",
                "Làm tiếp",
                "Có test cốt lõi, docs cập nhật, tracker cập nhật, launcher đủ rõ để bàn giao nội bộ",
                "A, E",
            ],
        ],
    )


def build_runtime_flow_sheet() -> SheetFile:
    return SheetFile(
        filename="07_Runtime_Flow.csv",
        headers=[
            "Thứ_tự",
            "Khối",
            "Luồng",
            "Bot_làm_gì",
            "Nếu_ok",
            "Nếu_lỗi",
        ],
        rows=[
            [
                "1",
                "Scan + Bind",
                "Launcher -> Discovery -> Binding",
                "Quét MEmu, hiện title, chọn đúng instance rồi bind vm_index, title, pid, hwnd, adb_serial",
                "Cho phép start bot",
                "Không bind được duy nhất thì không cho start",
            ],
            [
                "2",
                "Start Session",
                "Launcher -> Supervisor -> BotWorker",
                "Tạo bot session riêng cho đúng binding đã chọn",
                "Bot vào vòng theo dõi hoặc chơi",
                "Log lỗi rõ binding nào fail",
            ],
            [
                "3",
                "Capture",
                "HWND -> CaptureWorker -> FrameEnvelope",
                "Chụp frame đúng cửa sổ Windows, gắn bot_id, frame_id, timestamp",
                "Đẩy latest frame sang perception",
                "Timeout hoặc sai identity thì pause hoặc retry có kiểm soát",
            ],
            [
                "4",
                "Identity Check",
                "Frame -> Validator",
                "Kiểm tra title hoặc fingerprint để chắc vẫn đúng giả lập",
                "Cho frame đi tiếp",
                "Loại frame và cảnh báo drift identity",
            ],
            [
                "5",
                "Perception",
                "Frame -> InferenceService",
                "Detect card, button, text từ ROI cần thiết",
                "Trả kết quả gắn đúng bot_id và frame_id",
                "Log detect fail hoặc hạ tần suất nếu backlog",
            ],
            [
                "6",
                "State Extraction",
                "Detection -> GameState",
                "Biến kết quả nhận diện thành state game chuẩn hóa",
                "Có state để validator và decision dùng",
                "State vô lý thì reject snapshot",
            ],
            [
                "7",
                "Consensus",
                "GameState x 2-3 frame",
                "Chỉ tin state khi ổn định qua nhiều frame liên tiếp",
                "Mở cửa cho decision",
                "Tiếp tục chờ frame mới, không hành động mù",
            ],
            [
                "8",
                "Decision",
                "Validated State -> Agent",
                "Chọn action hợp lệ theo luật hoặc chiến lược Tiến Lên",
                "Tạo action plan cụ thể",
                "Nếu chưa chắc thì pass hoặc chờ an toàn tùy policy",
            ],
            [
                "9",
                "Act",
                "Action Plan -> AdbBroker -> Emulator",
                "Gửi tap, swipe, text qua đúng serial với queue riêng từng thiết bị",
                "Thao tác được thực hiện",
                "Retry có giới hạn, không burst ADB",
            ],
            [
                "10",
                "Post-Action Verify",
                "Action -> Capture -> Validator",
                "Nhìn lại màn hình sau thao tác để xác nhận kết quả",
                "Cập nhật state mới",
                "Fail thì log rõ, có thể retry hoặc pause theo chính sách",
            ],
            [
                "11",
                "Recovery",
                "Watchdog -> CircuitBreaker -> Supervisor",
                "Theo dõi timeout capture, ADB, window và tài nguyên hệ thống",
                "Bot khỏe tiếp tục chạy bình thường",
                "Pause hoặc restart riêng bot lỗi, không restart cả cụm",
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
