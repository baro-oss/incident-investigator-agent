# CLAUDE.md — Chỉ thị vận hành cho dự án

> File này được nạp tự động đầu mỗi session. **Đọc kỹ trước khi làm bất cứ việc gì.** Bộ tài liệu thiết kế đầy đủ nằm trong thư mục `docs/` (`docs/README.md`, `docs/01`–`docs/09`). File này là các chỉ thị BẮT BUỘC tuân thủ, không phải gợi ý.

## Dự án là gì (1 dòng)

Agent điều tra sự cố microservice: nhận triệu chứng → engine domain-agnostic tự điều tra (loop adaptive, tool-calling) → verdict neo bằng chứng → push Telegram. Demo trên 2 kịch bản synthetic.

## Quy tắc số 1: ĐỪNG over-engineer. Đây là MVP 5 ngày.

Bạn (Claude) sẽ có xu hướng tự thêm thứ "chuyên nghiệp hơn". **KHÔNG.** Mỗi thứ dưới đây đã được cân nhắc và CỐ Ý loại khỏi bản thi. Nếu thấy mình định làm bất kỳ cái nào, DỪNG và hỏi người dùng trước:

- ❌ KHÔNG Postgres / MySQL / vector DB → **dùng SQLite**.
- ❌ KHÔNG LangGraph / framework agent → **tự viết loop** trên tool-calling SDK.
- ❌ KHÔNG multi-agent → **single agent**.
- ❌ KHÔNG Langfuse / LangSmith / OpenTelemetry → **trace structured ghi SQLite**.
- ❌ KHÔNG Kafka / message broker → **background task asyncio**.
- ❌ KHÔNG sinh GB data thật → **vài nghìn dòng/kịch bản**; muốn thể hiện quy mô thì cho tool báo `total_count` lớn giả lập.
- ❌ KHÔNG build UI service registry (CRUD) → catalog là **file/bảng tĩnh**.
- ❌ KHÔNG build adapter cho nhiều nguồn alert / nhiều kênh báo → **một intake mapper ví dụ + một kênh Telegram**.
- ❌ KHÔNG MCP hóa nhiều tool → **đúng 1 tool bọc MCP** để demo hot-plug.

Tất cả những cái trên thuộc **roadmap** (xem bảng trong `docs/01-roadmap.md`). Vai trò của chúng là *câu chuyện pitch*, KHÔNG phải code. Nếu người dùng yêu cầu rõ ràng một trong số đó thì làm; còn lại mặc định KHÔNG.

## Stack đã chốt (không đổi nếu không có lệnh rõ)

Python · tự viết agent loop · SQLite (WAL) · Telegram bot API · MCP client gọi từ trong loop · async = background task.

## Bốn nguyên tắc kiến trúc (mọi quyết định code phải tuân)

1. **LLM không bao giờ thấy dữ liệu thô.** Tool gom nhóm/aggregate bằng SQL, chỉ trả Observation đã chưng cất (summary + aggregates + ≤5 samples + total_count). Nếu định trả raw rows cho LLM → SAI, đưa logic gom vào tool.
2. **Một đường ranh (seam).** Engine chỉ thấy `list[Tool]` đồng nhất (name, description, input_schema, run→Observation). Engine KHÔNG được biết "log"/"SQLite"/"MCP" là gì.
3. **Lõi deterministic, agent chỉ điều phối.** Tính toán nằm trong tool; LLM chỉ chọn tool + quyết điểm dừng.
4. **Async từ biên nhận; một nguồn structured, nhiều renderer.** Observation/verdict/trace đều structured, render ra text chỉ ở biên tiêu thụ.

## Yêu cầu thiết kế code (để dễ mở rộng sau — KHÔNG phải build thêm gì)

- `InvestigationState` là **dataclass thuần dữ liệu**, tách khỏi logic.
- Mỗi bước loop là **hàm pure** nhận-state-trả-state: `decide_next_action(state)`, `run_tool(action)`, `update_state(state, obs)`. (Để lên LangGraph sau = bọc mỗi hàm thành node, không viết lại.)
- Giả thuyết và bằng chứng **liên kết nhau** trong state (không phải hai list rời) — verdict và đánh giá đều dựa vào liên kết này.

## Những điểm dễ làm sai (đọc file tương ứng trong docs/ trước khi code)

- **Observation:** summary đặt ĐẦU, mang đúng signal bước kế cần (không chung chung). Tool TỰ diễn giải ("gấp 9 lần baseline"), không trả mảng số thô. → `docs/04`, `docs/06`.
- **Loop:** adaptive (mỗi bước quyết 1 hành động), KHÔNG plan-ahead. Đưa state đã tổng hợp, KHÔNG đưa lịch sử thô mỗi lượt. → `docs/05`.
- **Dừng:** model tầm trung hay dừng SỚM → buộc kiểm "đã loại trừ giả thuyết cạnh tranh chưa". Có step budget + phát hiện lặp. → `docs/05`.
- **Verdict:** neo bằng chứng (không claim trần), độ tin theo LOẠI bằng chứng (không %), "chưa đủ bằng chứng" là hợp lệ, phân biệt lỗi-gốc/lỗi-lan. → `docs/05`.
- **Trace đứt:** `trace_request` PHẢI báo cáo chỗ mất dấu; khi đứt thì bắc cầu bằng tương quan thời gian + HẠ độ tin + gắn cờ suy đoán. Tool im lặng về chỗ đứt = agent bịa. → `docs/06`, `docs/07`.
- **Kịch bản 2:** phải gieo **tín hiệu âm tính** (metric gateway KHÔNG lệch) — dễ quên. → `docs/07`.
- **Output:** mọi nhánh kết thúc (thành công/timeout/lỗi) đều phải gửi MỘT tin Telegram, không chết im lặng. → `docs/08`.

## Ranh giới fintech (an toàn — bắt buộc)

Chỉ synthetic data, tool READ-ONLY, không PII, không kết nối hệ thống thật. Tool không được có thao tác ghi/xóa/sửa lên bất kỳ nguồn nào.

## Quy trình làm việc qua nhiều session

1. Đầu session: đọc file này + `BUILD_STATE.md` để biết đã làm tới đâu.
2. Bám `docs/03-plan-5-ngay.md` — làm theo cổng kiểm từng ngày, KHÔNG nhảy cóc.
3. Cuối session: cập nhật `BUILD_STATE.md` (đã xong gì, đang dở gì, quyết định lệch so với tài liệu nếu có).
4. Cái lõi không được vỡ: **engine chạy 2 kịch bản end-to-end + push Telegram**. Ưu tiên nó trên mọi thứ "đẹp để có".
5. Nếu một quyết định trong tài liệu hóa ra sai lúc code: được phép điều chỉnh CHI TIẾT (schema thêm field, tách tool), nhưng giữ KHUNG (4 nguyên tắc, đường ranh, stack). Lệch khung phải hỏi người dùng.

## Cấu trúc thư mục

```
.
├── CLAUDE.md          (file này — chỉ thị, tự nạp)
├── AGENTS.md          (bản sao cho Cowork)
├── BUILD_STATE.md     (trạng thái build — cập nhật mỗi session)
└── docs/              (tài liệu thiết kế chi tiết)
    ├── README.md      (mục lục + tổng quan)
    ├── 01-roadmap.md
    ├── 02-architecture.md
    ├── 03-plan-5-ngay.md
    ├── 04-hop-dong-tool-va-observation.md
    ├── 05-engine.md
    ├── 06-tool-layer.md
    ├── 07-synthetic-data-va-kich-ban.md
    ├── 08-vong-tu-chu-va-output.md
    └── 09-trace-va-storage.md
```
