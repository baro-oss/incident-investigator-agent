# 06 — Tool Layer

> Nguyên tắc xuyên suốt: **mỗi tool là một câu hỏi điều tra, tự làm hết phần phân tích, trả về kết luận đã diễn giải kèm số liệu đỡ.**

## Quyết định lớn nhất: độ hạt của tool

Sai theo cả hai hướng:
- **Quá rộng** (một tool `query_anything` nhận SQL tự do): đẩy gánh nặng suy luận về model — đúng chỗ model tầm trung yếu, mất tính deterministic.
- **Quá hẹp** (hai chục tool tí xíu): model loạn khi định tuyến, chọn sai. Đây là nguyên nhân số một làm model tầm trung đi sai.

**Điểm cân bằng:** mỗi tool tương ứng một *câu hỏi điều tra con người hay đặt*, không phải một thao tác kỹ thuật. "Lỗi đang tập trung ở đâu" là một tool; "SELECT count(*) GROUP BY" là chi tiết *trong* tool.

## Năm tool (đủ cho 2 kịch bản, không thừa thiếu)

| Tool | Câu hỏi điều tra | Trả về (Observation summary) |
|------|------------------|------------------------------|
| `get_error_breakdown` | Lỗi đang tập trung ở đâu? | "87% lỗi là Timeout ở /pay, tăng từ 14:05" — thường gọi **đầu tiên** để khoanh vùng |
| `get_metrics` | Chỉ số có lệch baseline không, từ lúc nào? | "latency p99 tăng từ 200ms→1.8s lúc 14:05, gấp 9 baseline" — **so baseline nằm trong tool** |
| `get_recent_deploys` | Có gì thay đổi quanh mốc sự cố? | "deploy v2.3.1 lúc 14:03" |
| `get_dependencies` | Service này phụ thuộc ai? | đồ thị **một tầng** (gọi trực tiếp ai) — đọc từ service catalog |
| `trace_request` | Một request lỗi đi qua những service nào? | lần theo trace_id; **báo cáo chỗ đứt** nếu mất dấu |

## Thứ tự không mã hóa cứng, nhưng description gợi ý thứ tự tự nhiên

Không bảo agent "gọi A trước B". Nhưng description tốt khiến agent tự đi từ rộng (breakdown khoanh vùng) → hẹp (drill bucket lớn nhất) → nguyên nhân (deploy/dependency). **Cách mô tả tool = cách dẫn dắt mà không ép buộc.** Lại một lý do description là nơi đáng đổ công nhất.

## Cặp tool điều tra xuyên service (kịch bản 2 sống hay chết)

- `get_dependencies` trả **một tầng** (không phải cả cây) → agent đi *từng bước* ngược dòng, mỗi bước là quyết định nhỏ (đúng tinh thần adaptive). Trả cả cây sâu = nhồi context + tước mạch điều tra từng bước.
- `trace_request` là tool "đắt giá" cho khoảnh khắc wow — lần request lỗi xuyên service, phát hiện "gateway chỉ là nơi lỗi *lộ ra*, gốc ở provider".

## Xử lý trace đứt (trace id có nhưng đứt quãng)

Thực tế: service có trace id theo request, nhưng một số đoạn code log không có context → mất trace. **Biến điểm yếu thành thiết kế:**

- `trace_request` báo cáo trung thực độ phủ: "lần được qua 4 service, mất dấu ở X (log không có trace id)".
- Khi mất dấu, agent **chuyển chiến lược dự phòng**: bắc cầu bằng *tương quan thời gian + dependency* ("mất trace ở X, nhưng X gọi Y, log Y có lỗi cùng khoảng → nhiều khả năng request đi tiếp xuống Y").
- **Hạ độ tin tương ứng:** liên kết dựng từ trace id = bằng chứng *chắc*; dựng từ tương quan thời gian khi đứt = *yếu hơn* → verdict phải hạ mức tin và nói rõ là suy đoán.
- **Bẫy:** đừng để agent lấp khoảng đứt bằng phỏng đoán mà không gắn cờ (hallucinated causal link). Tool im lặng về chỗ đứt = agent không biết để hạ độ tin = bịa. → Tool BẮT BUỘC báo cáo chỗ đứt.

## Observation cho từng tool — điểm cần canh

Áp schema `04`, nhưng: **summary phải mang đúng signal bước kế cần**, không chung chung. Chất lượng điều tra phần lớn quyết ở khâu viết summary của tool, không phải ở engine.

**Bẫy:** tool trả về thứ model phải *diễn giải thêm* mới dùng được (vd mảng số metric thô). Tool phải *tự kết luận*: "tăng gấp 9 lần baseline". Quy tắc: **tool làm xong phần phân tích, model chỉ nhận kết luận để định hướng.** Mỗi khi định trả dữ liệu thô "để model tự hiểu" → đó là dấu hiệu phần việc đó nên nằm trong tool.

## MCP trong tool layer

- Bọc đúng **một** tool qua MCP để demo hot-plug. Còn lại function nội bộ.
- **Chọn tool nào:** một tool *bổ trợ* (KHÔNG phải `get_error_breakdown` — tool cốt lõi), để nếu MCP trục trặc lúc demo thì không gãy mạch chính. Rủi ro cô lập.
- Lý tưởng: chọn tool kể được câu chuyện "cắm thêm nguồn dữ liệu mới mà engine chưa từng biết → agent tự nhận ra và dùng".
- MCP client gọi từ trong loop tự viết; MCP server trả tool → nạp vào cùng `list[Tool]`. Tự-viết-loop và MCP sống chung thoải mái.
