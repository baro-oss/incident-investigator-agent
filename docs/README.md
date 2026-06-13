# Incident Investigation Agent — Bộ tài liệu dự án

> Agent điều tra sự cố tự động cho hệ microservice. Nhận một triệu chứng (alert hoặc câu hỏi) → tự lập kế hoạch điều tra → khoanh vùng nguyên nhân gốc → push verdict ra Telegram. Lõi là một **engine điều tra domain-agnostic**; on-call/incident chỉ là tập tool đầu tiên cắm vào.

## Bối cảnh

- **Cuộc thi:** build agent nội bộ (ZaloPay, fintech). Thời hạn 5 ngày, ~4-5 tiếng/ngày. Ngày cuối dành cho quay video → **code đóng băng cuối ngày 4**.
- **Điều kiện thắng:** chấm bởi cả hội đồng kỹ thuật lẫn phiếu bầu toàn công ty → thiết kế phải cân bằng "agentic thật" (cho hội đồng) và "dễ hiểu, có khoảnh khắc wow" (cho phiếu bầu).
- **Mục tiêu thật (quan trọng hơn thắng):** xây một agent áp dụng được vào công việc thật, và đặt nền cho một **platform** điều tra mà công ty có thể đầu tư mở rộng — phục vụ cả hệ thống tech lẫn non-tech.
- **Người làm:** developer, quen khái niệm agent, đã tự build agent cơ bản. Hạ tầng (LLM API, môi trường) đã sẵn.

## Luận điểm cốt lõi

1. **Đây là agent, không phải app**, vì điều tra sự cố là cây quyết định phân nhánh theo dữ liệu vừa thấy — không liệt kê hết bằng if-else được.
2. **Model tầm trung là đủ** vì engine chỉ *điều phối*, không suy luận sâu. Mọi tính toán nặng nằm trong tool deterministic. (Và model là thành phần *thay được* — nâng cấp sau không đụng kiến trúc.)
3. **Đây là một platform có 4 cạnh pluggable, engine bất biến ở giữa:** intake (mọi nguồn alert) · tool (mọi nguồn dữ liệu, kể cả MCP) · output (mọi kênh báo) · model. Thêm bất kỳ cạnh nào = thêm adapter, không sửa engine.

## Stack đã chốt

- **Ngôn ngữ:** Python (khớp phần nặng nhất của bài — xử lý dữ liệu).
- **Agent loop:** tự viết, dựa trên tool-calling của LLM SDK. KHÔNG dùng LangGraph cho bản thi.
- **Storage:** SQLite (vừa lưu trữ vừa thực thi aggregate).
- **Kênh báo:** Telegram (một kênh; email/Teams = roadmap).
- **MCP:** bọc đúng 1 tool để demo hot-plug.

## Mục lục tài liệu

| File | Nội dung |
|------|----------|
| `01-roadmap.md` | Tầm nhìn, 4 cạnh pluggable, ranh giới MVP vs Roadmap, điểm pitch |
| `02-architecture.md` | Kiến trúc phân tầng, thành phần, đường ranh, luồng dữ liệu |
| `03-plan-5-ngay.md` | Kế hoạch theo ngày, cổng kiểm, mốc đóng băng, thứ tự cắt |
| `04-hop-dong-tool-va-observation.md` | Hợp đồng tool + observation schema (phần nền) |
| `05-engine.md` | State, vòng lặp, điều kiện dừng, verdict, đánh giá, các bẫy |
| `06-tool-layer.md` | 5 tool, độ hạt, điều tra xuyên service, MCP |
| `07-synthetic-data-va-kich-ban.md` | Schema data, 2 kịch bản, trace đứt, tín hiệu/nhiễu |
| `08-vong-tu-chu-va-output.md` | Intake, async, verdict formatter, Telegram |
| `09-trace-va-storage.md` | Trace event có cấu trúc, SQLite, ba loại log |

## Thứ tự đọc khi bắt tay

Đọc `01` → `02` để nắm toàn cảnh. Rồi build theo `03` (kế hoạch ngày), mở các file `04`–`09` đúng lúc cần ở từng ngày. Bốn nguyên tắc xuyên suốt nằm ở đầu `02` — khi phân vân quyết định gì, quay về đó.

## Ranh giới fintech (an toàn)

Toàn bộ demo chạy trên **synthetic data**, tool **read-only**, không dữ liệu thật/PII. Đây vừa là yêu cầu an toàn vừa là điểm cộng khi hội đồng hỏi về bảo mật.
