# 09 — Trace & Storage

## Ba loại "log" — đừng gộp

| Loại | Là gì | Xử lý bằng |
|------|-------|-----------|
| 1. Synthetic log của service | *Đối tượng* agent điều tra (data giả lập) | Bảng SQLite (xem `07`) |
| 2. Trace quyết định của agent | Mỗi bước agent nghĩ/gọi/nhận gì | Structured event (phần này) |
| 3. Log vận hành của app | Request đến, exception, thời gian chạy | `logging` chuẩn của Python |

Giữ riêng để lúc debug không lẫn: loại 3 trả lời "app có khỏe không", loại 2 trả lời "agent điều tra ra sao".

## Trace quyết định = chuỗi structured event (KHÔNG phải text)

**Quyết định cốt lõi** (quyết định luôn "dùng gì"): cùng trace phục vụ 4 nơi tiêu thụ có nhu cầu khác nhau:

- **Debug** (lúc dev) — đọc chi tiết.
- **Demo** — render/stream đẹp theo thời gian thực ("agent đang suy nghĩ").
- **Đánh giá** — *parse* để chấm đúng/sai so root cause cài sẵn (`05`).
- **Audit/pitch** — artifact đính kèm.

Một đống `print`/text phục vụ tốt đúng một nơi (đọc bằng mắt), phản bội ba nơi kia. → Trace phải là **chuỗi event có cấu trúc**: mỗi event = loại (chọn-tool / chạy-tool / cập-nhật-giả-thuyết / kết-luận) · nội dung · timestamp · số bước.

Đây *chính là* nguyên tắc "một nguồn structured, nhiều renderer" áp lại lần nữa (sau observation, verdict).

## Dùng gì để xử lý — KHÔNG cần công cụ đặc biệt

Khi trace đã structured:
- **Lưu:** mỗi phiên là một danh sách event → bảng SQLite (hoặc file JSON). Không cần gì hơn.
- **Demo:** đọc chuỗi event → render/stream từng bước.
- **Đánh giá:** script chấm parse chuỗi event, tìm event "kết-luận", so root cause.
- **Debug:** render chính chuỗi đó ra console người-đọc-được.

Một nguồn, bốn cách dùng.

## KHÔNG dùng observability tool chuyên dụng cho bản thi

Langfuse / LangSmith / OpenTelemetry-for-LLM giải vấn đề thật — nhưng của hệ production (hàng nghìn phiên, nhiều người debug, dashboard). Với 2 kịch bản, dựng Langfuse tốn nửa ngày setup để giải vấn đề bạn chưa có. Tự ghi structured event ra SQLite là đủ và nhanh hơn. → **Roadmap.**

**Điểm cộng:** vì trace structured và tách khỏi logic, nó **map thẳng** vào event của LangSmith/OTel sau này — chỉ thêm một renderer đẩy event sang, không viết lại. Lại là tính mở rộng đến từ ranh giới sạch.

## SQLite — storage cho cả MVP

Một cơ chế lưu trữ duy nhất phục vụ cả ba loại dữ liệu. Một file, không server, không config.

- **Vừa lưu vừa thực thi aggregate:** GROUP BY / COUNT / lọc time window ngay trong query → tool trả số đã gom mà không kéo dòng thô ra tầng app. Kiến trúc "tool làm phần nặng" được SQLite đỡ tự nhiên. **Nó là nơi *thực thi* aggregate, không chỉ nơi chứa.**

### Quyết định khi dùng

- **Tách bảng theo 3 mục đích:** bảng synthetic log/metric/deploy · bảng trace event · service catalog (bảng hoặc file). Trộn vào = lúc debug lẫn.
- **Index cột tra cứu nhiều:** `timestamp`, `service`, `trace_id`, `error_type`. Thiếu index → aggregate chậm → hỏng mục tiêu real-time. Việc một dòng `CREATE INDEX` nhưng dễ quên.
- **Bật WAL** để né lock khi nhiều phiên cùng ghi trace (test bắn nhiều trigger song song). MVP gần như không thành vấn đề, nhưng biết để không bất ngờ.

### Câu trả lời "scale thì sao" (cho pitch)

"MVP dùng SQLite; lên nhiều phiên đồng thời thì chuyển Postgres, mọi tool query giữ nguyên vì đứng sau cùng một interface." → Tính mở rộng nhờ ranh giới sạch.
