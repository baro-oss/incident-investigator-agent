# 04 — Hợp đồng tool & Observation schema

> Phần nền. Engine, tool, data đều bám vào đây. Chốt phần này trước khi viết bất cứ thứ gì.

## Hợp đồng tool

Mọi tool — nội bộ hay MCP — hiện ra với engine dưới **một** hình dạng đồng nhất:

- `name` — định danh tool.
- `description` — **LLM đọc cái này để định tuyến.** Đây là nơi đáng đổ công nhất. Phải sắc, phân biệt rõ khi nào dùng tool nào. Chọn-sai-tool gần như luôn do description mơ hồ, không phải model kém.
- `input_schema` — JSON schema cho tham số.
- `run(params) -> Observation` — một callable.

**Quyết định:** dùng callable (không kế thừa class) để tool nội bộ (query SQLite) và tool MCP (gọi server) đều bọc được thành cùng kiểu. Engine chỉ thấy `list[Tool]` đồng nhất → MCP cắm vào không phá engine.

## Observation schema

Quyết định quan trọng nhất của phần này: cân bằng giữa **gọn** (chống overload context) và **giàu** (đủ cho engine quyết định). Năm thành phần:

- `summary` — 1-2 câu, **tool tự diễn giải** kết quả. LLM đọc đầu tiên, thường đủ để quyết bước tiếp. *Phải mang đúng signal bước kế cần*, không chung chung. Tốt: "87% lỗi là Timeout ở /pay, bắt đầu tăng lúc 14:05". Tệ: "tìm thấy nhiều lỗi".
- `aggregates` — số liệu đã gom nhóm (vd `{"TimeoutException": 14203}`). Phần "đã chưng cất" thay cho log thô.
- `samples` — vài mẫu đại diện, **trần cứng** (vd 3-5). Để LLM "nhìn tận mắt" một ví dụ, không bao giờ là toàn bộ.
- `total_count` + `truncated` — tổng thật trước khi cắt + cờ còn-dữ-liệu-bị-cắt. Cho LLM biết *quy mô thật* mà không thấy hết ("14203 lỗi, đang xem 5 mẫu, còn cắt"). Thiếu cặp này → model đánh giá sai mức nghiêm trọng.
- `metadata` — time_window, service, tool đã chạy. Để engine ghép bằng chứng không lẫn.

## Ba quyết định cốt lõi

1. **Summary đặt lên đầu.** Model tầm trung định tuyến tốt hơn khi câu chốt nằm ngay đầu observation thay vì phải tự suy từ đống số.
2. **Tổng-số-thật tách khỏi mẫu.** Model hiểu quy mô mà không cần thấy hết dữ liệu.
3. **Observation là dữ liệu có cấu trúc, KHÔNG phải string.** Lợi ích: (a) kiểm soát chính xác cái gì serialize vào context, (b) tách "dữ liệu điều tra" khỏi "cách trình bày", (c) tái dùng một observation cho prompt LLM + trace demo + verdict — một nguồn, nhiều nơi tiêu thụ.

## Render cho LLM

Chỉ ở *biên* (ngay trước khi gọi LLM) mới serialize observation thành text, qua một hàm `render_for_llm(obs) -> str`.

**Bẫy:** đừng đổ cả dataclass ra JSON thô — JSON lồng nhiều ngoặc làm model tầm trung khó đọc và tốn token. Render thành đoạn text gọn: summary lên đầu, rồi aggregates dạng liệt kê ngắn. Tách hàm render này ra cũng đúng tinh thần ranh-giới-sạch (đổi cách trình bày không đụng dữ liệu).

## Mở rộng cho trace đứt (xem thêm `06`, `07`)

Khi tool liên quan tới trace (`trace_request`), Observation cần thêm tín hiệu **độ hoàn chỉnh của trace** — báo cáo trung thực "lần được qua N service, mất dấu ở X". Họ hàng với `total_count`/`truncated`: tool không được im lặng về chỗ đứt, nếu không agent tưởng đã thấy toàn bộ đường đi và chốt sai.
