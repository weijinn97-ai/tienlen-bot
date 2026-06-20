from bot.runtime.schemas import BotBinding


BOT_BINDINGS = [
    BotBinding(
        bot_id="bot-01",
        hwnd=10001,
        adb_serial="127.0.0.1:7555",
        pid=20001,
        window_title="MEmu Player 1",
        identity_fingerprint="room-1-avatar-a",
        metadata={"priority": "high"},
    ),
    BotBinding(
        bot_id="bot-02",
        hwnd=10002,
        adb_serial="127.0.0.1:7556",
        pid=20002,
        window_title="MEmu Player 2",
        identity_fingerprint="room-2-avatar-b",
        metadata={"priority": "normal"},
    ),
]
