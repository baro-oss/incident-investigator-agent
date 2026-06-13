# 05 — Engine

> Phần dày nhất. Mọi quyết định xoay quanh một thiết kế nền: **state giữ giả thuyết liên kết với bằng chứng.**

## Quyết định trung tâm

Engine quản lý điều tra như một **quá trình có trạng thái, phân nhánh** — không phải một chuỗi gọi tool. Engine luôn giữ một *bức tranh giả thuyết đang tiến hóa*, mỗi bước để *thu hẹp* nó. Giữ được tư duy này thì phần còn lại tự rơi vào chỗ.

## State — giữ cái gì

`InvestigationState` (dataclass, tách khỏi logic):

- `symptom` — triệu chứng gốc (đã chuẩn hóa).
- `time_window` — cửa sổ sự cố. Mọi tool bó theo đây.
- `hypotheses` — danh sách giả thuyết, mỗi cái: nội dung · trạng thái (open/confirmed/ruled_out) · **trỏ tới các bằng chứng đỡ nó**.
- `evidence` — danh sách Observation đã thu.
- `steps_taken` / `step_budget` — vd budget = 10.

**Quyết định quan trọng nhất:** bằng chứng và giả thuyết **liên kết với nhau**, không phải hai danh sách rời. Cả verdict lẫn đánh giá đều dựa vào liên kết này. Tách rời = tự chặn đường ở khâu verdict.

## Hình dạng vòng lặp: ADAPTIVE (không plan-ahead)

Mỗi bước model chỉ nhìn state hiện tại và quyết đúng *một* hành động kế tiếp.

- **Vì sao adaptive:** bản chất điều tra là bước sau phụ thuộc kết quả bước trước (thấy 87% timeout mới biết đào tiếp hướng nào). Mỗi bước là quyết định nhỏ, đơn giản — đúng tầm model vừa phải.
- **Vì sao không plan-ahead:** vạch kế hoạch khi chưa thấy dữ liệu thì kế hoạch dễ sai ngay từ đầu, và model tầm trung không đủ giỏi để tự sửa kế hoạch giữa chừng.
- **Cái giá:** rủi ro đi lòng vòng → ngân sách bước + logic dừng kiểm soát.

## Mỗi bước model thấy gì

Đưa cho model: (a) triệu chứng gốc, (b) **tình trạng giả thuyết hiện tại** (đang theo gì, mỗi cái có bằng chứng gì), (c) bằng chứng mới nhất đã chưng cất (summary lên đầu), (d) danh sách tool + mô tả, (e) đã đi mấy bước / tổng budget. Hỏi đúng một câu: *gọi tool nào tiếp theo, hay đã đủ để kết luận?*

**Quyết định:** đưa **state đã tổng hợp**, KHÔNG đưa lại toàn bộ lịch sử thô mỗi lượt. Nối thêm output tool cũ mỗi lượt → context phình, model loãng tập trung và chậm. Giữ state gọn và tự-mô-tả để model sắc.

## Logic dừng — 4 điều kiện

Dừng khi: (1) một giả thuyết đạt mức tin "cao", HOẶC (2) model tự thấy đủ, HOẶC (3) hết step budget, HOẶC (4) timeout.

**Cân bằng sớm/muộn:** model tầm trung có xu hướng **dừng quá sớm** (vừa thấy manh mối hợp lý là muốn chốt). Đối sách: trước khi chốt, buộc agent tự kiểm "đã loại trừ các giả thuyết cạnh tranh chưa?" — buộc cân nhắc khả năng khác trước khi quả quyết.

## Các bẫy của model tầm trung + đối sách

80% thời gian debug rơi vào đây.

| Bẫy | Nguyên nhân | Đối sách |
|-----|-------------|----------|
| Chọn sai tool | Description mơ hồ | Viết description sắc (`04`) — không phải sửa engine |
| Lặp vô hạn | Gọi lại tool với tham số gần giống | Engine phát hiện lặp + nhắc "đã chạy rồi, kết quả X"; budget là chặn cứng cuối |
| Bịa nguyên nhân | Đoán root cause khi chưa đủ bằng chứng | Ràng buộc verdict-neo-bằng-chứng (dưới) |
| Đánh giá sai quy mô | Thấy 5 mẫu tưởng nhỏ | Cặp `total_count` + `truncated` (`04`) |

## Verdict (lồng vào engine, không phải bước rời)

Verdict = **trạng thái giả thuyết khi dừng, trình bày lại**. Vì state đã giữ giả thuyết-kèm-bằng-chứng, verdict gần như miễn phí — chỉ là *cách đọc lại state*:

1. **Neo bằng chứng:** mỗi giả thuyết phải trỏ ngược về Observation cụ thể đã tạo ra nó. Kết luận không gắn được bằng chứng → KHÔNG lên verdict. (Chống bịa nguyên nhân.)
2. **Độ tin theo LOẠI bằng chứng, không phải %:** đừng hỏi model "bao nhiêu %" (phun số bừa). Định nghĩa mức gắn với bằng chứng — *cao* = có cả tương quan thời gian lẫn cơ chế nhân quả rõ; *trung bình* = chỉ tương quan thời gian; *thấp* = suy đoán.
3. **"Chưa đủ bằng chứng" là kết cục hợp lệ**, không phải thất bại. Một agent khiêm tốn đúng lúc gây ấn tượng hơn agent luôn quả quyết.
4. **Phân biệt lỗi-gốc / lỗi-lan:** với giả thuyết hàng đầu, hỏi "đây là nơi lỗi *phát sinh* hay *lộ ra*?" và đi ngược dependency. Chống cái bẫy chốt nhầm vào service kêu to nhất / thấy đầu tiên.

## Đánh giá (lồng vào engine)

Vì biết root cause cài sẵn của mỗi kịch bản, và verdict trỏ về bằng chứng cụ thể → kiểm được agent đúng vì lý do đúng hay đúng do may.

- **"Đúng" nhiều mức, không nhị phân:** (a) chốt đúng root cause, (b) đúng nhưng không xếp số một, (c) đúng hướng nhưng dừng sớm, (d) sai.
- **Chạy lặp lại (N=5-10 lần/kịch bản)** vì agent là xác suất. "8/10 lần đúng" là phát biểu mạnh và trung thực; "chạy một lần thấy đúng" là ảo tưởng.
- **Là vòng phản hồi khi dev:** chạy → thấy chỗ sai → chỉnh (thường là description/prompt) → đo lại. Cách *biết* mình tiến bộ thay vì đoán.
- **KHÔNG cần eval framework** (LangSmith/promptfoo) cho 2 kịch bản — một script chạy N lần đếm kết quả là đủ. Framework = roadmap.
- Dữ liệu chấm chính là **trace event** engine vốn đã ghi (`09`). Trace phục vụ 4 việc: debug, demo, đánh giá, audit.

> Mọi quyết định engine xoay quanh **state giữ giả thuyết liên kết bằng chứng**. Loop adaptive cập nhật nó, logic dừng đọc nó, verdict trình bày lại nó, đánh giá kiểm nó.
