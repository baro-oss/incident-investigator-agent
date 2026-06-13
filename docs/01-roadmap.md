# 01 — Roadmap & Tầm nhìn

## Tầm nhìn sản phẩm

Không phải "một agent phân tích log", mà là **một engine điều tra domain-agnostic** — demo trên một vertical (on-call/incident), nhưng kiến trúc để mở rộng sang mọi domain mà câu hỏi "có gì đó bất thường, tại sao?" xuất hiện:

- **Tech:** điều tra sự cố (log · metric · deploy) — vertical demo.
- **Giao dịch/tài chính:** sụt doanh thu, bất thường fraud, lệch đối soát.
- **Vận hành/CSKH:** đột biến khiếu nại, đột biến ticket.
- **Business:** một KPI tụt không rõ lý do.

Đổi domain = viết một **tool pack** mới. Code engine không đổi.

## Bốn cạnh pluggable (engine bất biến ở giữa)

```
        INTAKE                                      OUTPUT
   (mọi nguồn alert) ──┐                    ┌── (mọi kênh báo)
   Datadog, Grafana,   │                    │    Telegram, email,
   Sentry, cron, ...   │   ┌────────────┐   │    Teams, ...
                       └──▶│            │◀──┘
                           │   ENGINE   │
                       ┌──▶│ (bất biến) │◀──┐
   TOOL                │   └────────────┘   │   MODEL
   (mọi nguồn dữ liệu) ─┘                    └── (tầm trung → mạnh)
   logs, metrics,                                swappable, không
   deploys, MCP, ...                             đụng kiến trúc
```

Mỗi cạnh thêm/đổi bằng cách thêm adapter cùng interface. Đây là cốt lõi câu chuyện platform.

## Ranh giới MVP vs Roadmap

Nguyên tắc vàng: **làm chết một vertical end-to-end, chứng minh tính tổng quát bằng kiến trúc — KHÔNG build platform trong 5 ngày.**

| Build trong cuộc thi | Để roadmap (kể bằng lời + mock) |
|----------------------|----------------------------------|
| Engine + hợp đồng tool trừu tượng | UI service registry (CRUD) |
| 5 tool nội bộ trên SQLite synthetic | DB thật + lịch sử điều tra |
| 1 tool bọc MCP (hot-plug demo) | MCP hóa toàn bộ tool |
| Telegram adapter | Email / Teams adapter |
| Intake schema tổng quát + 1 mapper ví dụ | Adapter cho N nguồn alert thật |
| 2 kịch bản chống hardcode | Phát hiện bất thường real-time |
| Working memory 1 phiên | Long-term memory xuyên phiên |
| Tool nạp thủ công | Lọc tool động khi nhiều tool |
| Single-agent, loop tự viết | Multi-agent + LangGraph |
| Trace ghi structured (JSON/SQLite) | Langfuse / OpenTelemetry |
| Service catalog file tĩnh (3-5 service) | Service mesh discovery |

**Quy tắc khi bị cám dỗ thêm tính năng:** đối chiếu bảng này. Thuộc cột phải → kể bằng lời, không code. Mọi ý hay (intake đa nguồn, UI registry, multi-agent...) đều là *vệ tinh quay quanh lõi*, sẵn sàng rơi rụng nếu hụt giờ.

## Cái lõi không được phép vỡ

> Engine điều tra chạy được **hai kịch bản** end-to-end, push Telegram, trên data có chiều sâu.

Mọi thứ khác là phụ trợ. Bảo vệ cái lõi này bằng mọi giá.

## Điểm tựa pitch

- "Khắp công ty, hễ có bất thường là có người phải query thủ công ghép dữ liệu nhiều hệ thống — agent này tự động hóa đúng vòng lặp đó."
- "Engine không phụ thuộc domain; thêm domain mới chỉ là một tool pack." → nền tảng, không phải tính năng.
- "Model tầm trung là đủ vì engine chỉ điều phối; và model là cạnh thay được — nâng cấp không đụng kiến trúc." → trả lời câu chắc chắn bị hỏi.
- "Nói MCP nên bất kỳ team nào tự viết MCP server cho hệ thống của họ là cắm vào được ngay."
- "Chẩn đoán trong một phút thay vì người trực mò nửa tiếng." → giá trị real-time đúng khung.
- "MVP single-agent loop minh bạch; vì state tách bạch + tool sau hợp đồng đồng nhất, tách multi-agent / lên LangGraph là tiến hóa tự nhiên, không viết lại."
- **Bằng chứng định lượng:** "agent tìm đúng nguyên nhân gốc ở N/10 lần trên 2 loại sự cố khác nhau, trung bình M bước." (chống hardcode + tư duy sản phẩm)
- Giải **hai** kịch bản khác nguyên nhân gốc ngay trước mắt giám khảo.

## Định nghĩa "real-time"

= **triage gần-tức-thì trong khoảng một phút**, không phải mili-giây. Hai độ trễ:
- *Phát hiện* (sự cố → alert): việc của hệ giám sát, KHÔNG phải agent. Demo dùng webhook giả lập.
- *Điều tra + báo* (trigger → Telegram): phần agent kiểm soát. Vài chục giây tới một phút là chấp nhận được cho incident response.
