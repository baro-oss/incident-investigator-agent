# 03 — Kế hoạch 5 ngày

## Ràng buộc & nguyên tắc

- ~4-5 tiếng/ngày, tổng ~22 tiếng. Hạ tầng đã sẵn → ngày 1 nhảy thẳng vào việc.
- **Code đóng băng cuối ngày 4.** Ngày 5 chỉ khóa sổ + quay video, không sửa code.
- **Mỗi ngày kết thúc phải có một trạng thái chạy được.** Không dồn rủi ro vào cuối.
- Ba mốc nặng nhất: synthetic data (ngày 1), engine (ngày 2), vòng tự chủ + demo (ngày 4).

## Ngày 1 — Dựng thế giới + hợp đồng tool

Tận dụng giờ tiết kiệm từ setup để **làm data cho sâu**, đừng tranh thủ làm engine sớm.

- [ ] Thiết kế schema SQLite: bảng logs / metrics / deploys (xem `07`, `09`). Index timestamp, service, trace_id, error_type. Bật WAL.
- [ ] Script sinh data tham số hóa. Sinh **kịch bản 1** (deploy v2.3.1 → timeout ở payment-gateway) kèm nền nhiễu nhẹ và dữ liệu baseline.
- [ ] Service catalog (3-5 service, dependency, baseline) — file/bảng tĩnh.
- [ ] Định nghĩa hợp đồng tool + Observation schema (xem `04`).
- [ ] Viết 2 tool đầu (`get_error_breakdown`, `get_metrics`) dạng function nội bộ.

**Cổng cuối ngày:** gọi tool bằng tay trả về Observation gọn, có cấu trúc (summary diễn giải sẵn), không phải log dump thô.

## Ngày 2 — Engine (lõi, dành nhiều tâm sức nhất)

- [ ] Định nghĩa `InvestigationState` (dataclass): symptom, time_window, hypotheses ↔ evidence, steps/budget.
- [ ] Viết loop adaptive dưới dạng hàm pure: `decide_next_action(state)` → `run_tool` → `update_state`.
- [ ] Prompt chọn tool: đưa state đã tổng hợp (không phải lịch sử thô), hỏi "tool nào / hay đủ rồi?".
- [ ] Stop logic (4 điều kiện) + step budget + phát hiện lặp.
- [ ] Emit trace event structured mỗi bước (xem `09`).
- [ ] Hoàn thiện 3 tool còn lại (`get_recent_deploys`, `get_dependencies`, `trace_request`).

**Cổng cuối ngày (MỐC QUAN TRỌNG NHẤT):** gõ một câu hỏi → agent tự chạy hết kịch bản 1 và nhả verdict thô, end-to-end. Qua được mốc này coi như đã có bài.

## Ngày 3 — Chất lượng verdict + kịch bản 2 (chống hardcode)

- [ ] Verdict structured: giả thuyết xếp theo độ tin, mỗi cái **neo bằng chứng**, độ tin **theo loại bằng chứng**, có nhánh "chưa đủ bằng chứng" (xem `05`).
- [ ] Bước phân biệt lỗi-gốc / lỗi-lan (đi ngược dependency).
- [ ] Siết loop: mô tả tool sắc hơn, logic dừng tốt hơn.
- [ ] Sinh **kịch bản 2** (provider sập → lỗi dây chuyền, có **trace đứt** ở gateway→provider, metric gateway **không lệch**).
- [ ] Viết script đánh giá: chạy mỗi kịch bản N lần, đếm tìm-đúng-root-cause / hạng / số bước / có bịa không.

**Cổng cuối ngày:** agent giải đúng **cả hai** kịch bản khác nguyên nhân gốc. Đường điều tra rẽ khác hẳn. → **Quay một bản demo nháp 2 phút** làm lưới an toàn + phát hiện sớm chỗ demo khựng.

## Ngày 4 — Đóng băng: lớp nhìn thấy + vòng tự chủ + platform proof

Gói trọn mọi thứ còn lại. Cuối ngày = deadline thật.

- [ ] Bề mặt demo: stream trace event ra dạng "điều tra trực quan" (agent suy nghĩ ra mặt).
- [ ] Output: verdict renderer cho Telegram (đọc-được-3-giây, gắn cờ độ tin) + Telegram adapter.
- [ ] Intake: webhook + chuẩn hóa symptom + dedup đơn giản + chọn được kịch bản khi trigger.
- [ ] Async: webhook ack ngay → background task → Telegram. Timeout + verdict-một-phần (không chết im lặng).
- [ ] MCP hot-plug: bọc 1 tool *bổ trợ* (không phải breakdown) qua MCP server tối giản. **Cắt được nếu hụt.**

**Cổng cuối ngày:** vòng đầy đủ chạy mượt cả hai kịch bản — trigger → điều tra → Telegram đến kèm chẩn đoán gọn.

## Ngày 5 — Khóa sổ + quay video

- [ ] Nửa đầu (~3.5h): KHÔNG code mới. Chạy thử nhiều lần cho chắc. Chuẩn bị môi trường quay (terminal sạch, Telegram mở sẵn trên điện thoại). Chốt kịch bản kể chuyện demo.
- [ ] Quay video (theo kịch bản demo).

> Quay video tốn thời gian thật (kịch bản, quay vài lần, dựng nhẹ). Đừng để code tràn sang ngày 5 làm video vội — đó là thứ giám khảo *nhìn thấy*.

## Thứ tự cắt nếu hụt giờ (cắt từ trên xuống)

1. **MCP hot-plug** — cắt đầu tiên, thay bằng kể-bằng-lời + mock. Câu chuyện platform vẫn đứng nhờ hợp đồng trừu tượng đã có trong code.
2. **Kịch bản 2** — ráng giữ (là lá chắn chống hardcode). Chỉ cắt khi buộc phải.
3. **Bề mặt demo đẹp** — lùi về CLI stream sạch, vẫn thấy mạch điều tra, chỉ kém lung linh.

## Hai chỗ dễ bị đánh giá thấp (đừng làm vội)

- **Dataset synthetic đủ "thật"** để cuộc điều tra có chỗ mà đi (data phẳng → demo nhạt). → Ngày 1.
- **Mô tả tool đủ sắc** để model tầm trung định tuyến đúng (chọn sai tool = description mơ hồ, không phải model kém). → Ngày 1-2.
