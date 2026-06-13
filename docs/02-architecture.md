# 02 — Kiến trúc

## Bốn nguyên tắc xuyên suốt

Vi phạm cái nào là phải viết lại nhiều. Khi phân vân quyết định gì, quay về đây.

1. **LLM không bao giờ thấy dữ liệu thô.** Tool làm phần nặng (gom nhóm, lọc, đếm, so baseline) bằng code và chỉ trả về observation đã chưng cất (vài trăm token). Hàng GB log không bao giờ chảy vào context.
2. **Một đường ranh giới (seam) duy nhất.** Engine nói chuyện với mọi tool qua một hợp đồng đồng nhất. Engine không biết "log" hay "transaction" là gì. Thêm domain = thêm tool pack.
3. **Lõi tính toán deterministic, agent chỉ điều hướng.** Phần đúng/sai do code lo; agent lo thứ tự gọi và điểm dừng.
4. **Async từ biên nhận; một nguồn structured, nhiều renderer.** Trigger ack ngay, điều tra chạy nền. Observation/verdict/trace đều là dữ liệu có cấu trúc, render ra nhiều dạng tùy nơi tiêu thụ.

## Kiến trúc phân tầng

```
┌─────────────────────────────────────────────┐
│  ENTRY / INTAKE LAYER                         │
│  webhook (push, alert đa nguồn → chuẩn hóa)   │
│  chat/CLI (pull)                              │
└───────────────────────┬───────────────────────┘
                        │ symptom (đã chuẩn hóa)
┌───────────────────────▼───────────────────────┐
│  INVESTIGATION ENGINE  (domain-agnostic)       │
│  • investigation state: giả thuyết ↔ bằng chứng│
│  • loop adaptive: chọn tool → chạy → cập nhật  │
│  • stop logic + step budget                    │
│  • emit trace event (structured)               │
└───────────────────────┬───────────────────────┘
     ═════════ ĐƯỜNG RANH (hợp đồng tool) ═════════
                        │  name · description · schema · Observation
┌───────────────────────▼───────────────────────┐
│  TOOL LAYER                                    │
│  get_error_breakdown · get_metrics ·           │◄─đọc─┐
│  get_recent_deploys · get_dependencies ·       │      │
│  trace_request   (+1 tool bọc MCP)             │   ┌──────────────┐
└───────────────────────┬───────────────────────┘   │   SQLite     │
                        │ verdict (structured)        │  synthetic   │
┌───────────────────────▼───────────────────────┐   │  + trace     │
│  OUTPUT LAYER                                  │   │  + catalog   │
│  verdict formatter → renderer → Telegram       │   └──────────────┘
└─────────────────────────────────────────────┘
```

## Vai trò từng tầng

**Entry / Intake.** Hai cửa vào, một engine. Webhook nhận alert đa dạng → **chuẩn hóa về một `symptom`** (service, time_window, loại lỗi, mô tả) trước khi vào engine. Giữ payload gốc trong phiên để trace/tham chiếu. Webhook ack ngay, đẩy điều tra sang background. Chat/CLI là cửa pull dùng cùng engine.

**Investigation engine.** Lõi domain-agnostic. Giữ state (giả thuyết liên kết bằng chứng), chạy loop adaptive, quyết điểm dừng, phát trace event. Chi tiết ở `05`.

**Đường ranh (seam).** Mọi tool — nội bộ hay MCP — hiện ra đồng nhất với engine. Đây là chỗ tính platform sống. Chi tiết hợp đồng ở `04`.

**Tool layer.** 5 tool, mỗi tool = một câu hỏi điều tra, tự làm phần phân tích, trả Observation đã diễn giải. Chi tiết ở `06`.

**Output layer.** Verdict structured → renderer theo kênh → Telegram. Mọi nhánh kết thúc (thành công/timeout/lỗi) đều dẫn tới một tin báo. Chi tiết ở `08`.

**SQLite.** Vừa lưu (synthetic data, trace, catalog) vừa *thực thi aggregate* (GROUP BY/COUNT/lọc time window ngay trong query). Chi tiết ở `09`.

## Luồng một cuộc điều tra (end-to-end)

1. Trigger (webhook alert / câu hỏi) tới intake.
2. Intake chuẩn hóa → `symptom`. Ack ngay, giao việc cho background.
3. Engine khởi tạo state từ symptom (suy ra service + time_window).
4. Loop: engine đưa state cho LLM → LLM chọn tool → engine chạy tool (query SQLite, aggregate) → nhận Observation → cập nhật giả thuyết/bằng chứng → phát trace event → lặp tới khi dừng.
5. Tổng hợp verdict từ state (giả thuyết xếp theo độ tin, neo bằng chứng).
6. Render verdict cho Telegram → gửi.
7. Toàn bộ trace event lưu vào SQLite.

## Tính mở rộng đến từ ranh giới sạch (không phải framework)

Ba điều giúp dễ lên multi-agent / LangGraph sau này, đều là good practice bình thường, không tốn thêm giờ:

1. **State tách khỏi logic** — là dataclass thuần dữ liệu.
2. **Mỗi bước loop là hàm pure** nhận-state-trả-state (`decide_next_action`, `run_tool`, `update_state`). Lên LangGraph = bọc mỗi hàm thành một node.
3. **Tool đứng sau hợp đồng đồng nhất** — không quan tâm ai gọi (1 agent hay nhiều).

## Stack

Python · tự viết loop trên tool-calling SDK · SQLite · Telegram bot API · MCP client (gọi từ trong loop tự viết — MCP server trả tool, nạp vào cùng danh sách tool đưa cho LLM). Async: background task của framework / asyncio. Không broker, không LangGraph, không observability tool chuyên dụng cho bản thi.
