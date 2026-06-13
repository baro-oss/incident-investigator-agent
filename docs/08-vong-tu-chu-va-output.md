# 08 — Vòng tự chủ & Output

> Tuân đúng hai nguyên tắc đã xuyên suốt: **async từ biên nhận**, và **một nguồn structured, nhiều renderer**. Không có tư tưởng mới — chỉ áp lại nguyên tắc cũ lên đầu ra.

## Quyết định nền: tách bạch ba giai đoạn

Vòng đầy đủ: **nhận → điều tra → báo**. Đừng để dính vào nhau trong một handler đồng bộ. Ranh giới quan trọng nhất là **đường biên async giữa "nhận" và "điều tra"**: intake ack rồi giao việc, không ôm.

## Intake — là một lớp chuẩn hóa, không phải một endpoint

Đây là chỗ ý "intake API đa nguồn" sống.

- Nhận payload **đa dạng** từ nhiều nguồn cảnh báo.
- Việc đầu tiên: **chuẩn hóa về một `symptom` thống nhất** (service, time_window, loại lỗi, mô tả). Mọi thứ sau đường biên này chỉ thấy symptom đã chuẩn hóa.
- **Giữ payload gốc trong phiên** (để trace/debug, để verdict tham chiếu "alert gốc nói gì").
- **Bản thi:** một intake schema tổng quát + **một** mapper ví dụ. "Thêm nguồn = thêm mapper" để dạng câu chuyện.

## Cơ chế async — tối giản, KHÔNG broker

- **Không Kafka.** Background task trong tiến trình (asyncio task / background task của framework web) là đủ.
- **Dedup khi nhiều trigger tới gần nhau:** trước khi khởi tạo phiên mới, kiểm có phiên nào *đang điều tra cùng (service + loại lỗi + cửa sổ)* không; có thì gộp/bỏ qua. MVP chỉ cần dedup đơn giản theo khóa đó; correlation đầy đủ = roadmap. **Đừng bỏ hẳn** — lúc demo lỡ bắn trigger 2 lần ra 2 cuộc điều tra song song thì luộm thuộm.

## Verdict formatter — một verdict, nhiều cách trình bày

- Verdict *nội bộ* là dữ liệu có cấu trúc (giả thuyết + bằng chứng + độ tin = state đọc lại).
- Từ đó **render** ra nhiều dạng tùy kênh: bản đầy đủ cho trace/demo; bản cô đọng cho Telegram.
- **Quyết định:** giữ verdict structured là nguồn, mỗi kênh một renderer riêng (y hệt observation `04`). Đừng sinh thẳng text Telegram từ engine. Thêm email/Teams sau = thêm renderer, không đụng engine.

## Telegram adapter — quyết định nội dung, không phải kỹ thuật

Phần kỹ thuật (bot API) tầm thường. Phần đáng nghĩ là tin nhắn chứa gì:

- **Đọc-được-trong-3-giây trên màn hình điện thoại.** Dồn cái quan trọng nhất lên đầu (nguyên nhân nghi ngờ + độ tin), bằng chứng gọn 2-3 gạch, gợi ý xử lý.
- **Gắn cờ độ tin rõ ràng:** "khả năng cao là X" khác hẳn "chưa chắc, mới có manh mối Y". Người trực cần biết tin tới đâu trước khi hành động. Nối thẳng vào verdict trung thực (`05`) — độ tin phải *hiện ra* trên tin nhắn.
- Tin nhắn cô đọng cũng thể hiện agent biết *tổng hợp*, không chỉ *báo*.

## Đừng để vòng tự chủ "chết im lặng"

Mọi nhánh kết thúc (thành công / timeout / engine lỗi / bí không kết luận) đều **phải dẫn tới một tin Telegram**. "Đã nhận sự cố ở gateway nhưng chưa kết luận trong giới hạn thời gian, đây là những gì thu được" tốt hơn vô hạn so với im lặng — im lặng khiến người trực không biết agent có nhận trigger không. Đây là khác biệt giữa hệ đáng tin và hệ thỉnh thoảng biến mất.

## Webhook trigger cho demo

- Chỉ là cách bắn một payload alert vào intake — một nút / lệnh curl.
- **Phải chọn được** bắn kịch bản 1 hay 2 lúc demo (để chứng minh không-hardcode). Đừng cứng vào một kịch bản.
