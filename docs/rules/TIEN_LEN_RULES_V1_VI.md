# Luật Tiến Lên V1 - Lock Candidate

Trạng thái: `CANDIDATE`, chưa `LOCKED`.

File này ghi rõ hành vi mà `bot.rules` đang thực thi để chủ repo review trước khi khóa.
Không đổi ma trận luật trong PR khác nếu chưa có issue và approval.

## Combo được hỗ trợ

- Lẻ, đôi, sám, sảnh từ 3 lá trở lên.
- Tứ quý.
- Ba đôi thông và bốn đôi thông.
- Sảnh và đôi thông không chứa rank 2.
- Card trong một combo không được trùng.

## So sánh cùng loại

- Lẻ, đôi và sám so theo lá cao nhất với thứ tự rank/suit contract.
- Sảnh phải cùng số lá và so lá cuối cao nhất.
- Tứ quý, ba đôi thông và bốn đôi thông so bộ có lá cuối cao hơn.

## Ma trận chặt đang dùng cho candidate

- Ba đôi thông, tứ quý hoặc bốn đôi thông chặt được một 2 hoặc đôi 2.
- Tứ quý hoặc bốn đôi thông chặt được ba đôi thông.
- Bốn đôi thông chặt được tứ quý.
- Bộ cùng loại mạnh hơn chặt bộ cùng loại theo quy tắc so sánh.
- Không dùng bomb để chặt combo thường khác loại ngoài các trường hợp trên.

## Mở ván

Rules API hỗ trợ `must_include_three_spades=True`: mọi legal opening combo phải chứa `3S`.
Typed `TableState` hiện chưa có cờ xác nhận đây là ván đầu, nên runtime chưa tự bật rule này.
Không suy đoán ván đầu từ hand; orchestration contract phải bổ sung evidence rõ trước khi nối.

## Chính sách LocalAgent v1

- Không phải lượt mình: `WAIT`.
- State/card/target không hợp lệ: `WAIT`.
- Lead: chọn legal combo nhỏ nhất; hiện ưu tiên lá lẻ nhỏ để giữ hành vi deterministic cũ.
- Response: ưu tiên cùng loại nhỏ nhất đủ thắng; chỉ dùng bomb khi cần cross-type.
- Không có response hợp lệ: `PASS`.
- Mọi PLAY được kiểm tra lại bằng `is_legal_play` trước khi trả ra ngoài.

## Chưa khóa

- Cần chủ repo xác nhận lại việc ba đôi thông có chặt được đôi 2 trong biến thể đang chơi.
- Luật bốn đôi thông đánh/chặt không theo vòng thuộc orchestrator turn policy, chưa tự động hóa.
- Cần fixture gameplay thực cho opening, pass vòng, reset vòng và win transition.
