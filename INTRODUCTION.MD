# Agent điều tra nguyên nhân sự cố

## Vấn đề

Khi một microservice gặp sự cố, kỹ sư on-call phải lục song song qua log lỗi, metrics, lịch sử deploy và source code, rồi tự ghép các dấu hiệu rời rạc thành nguyên nhân gốc rễ. Quá trình này thường mất 20–60 phút — phần khó không phải thiếu dữ liệu, mà là biết nhìn vào đúng nguồn theo đúng thứ tự. Áp lực giờ cao điểm dễ dẫn tới kết luận vội và sửa nhầm chỗ.

## Người dùng mục tiêu

Đội **DevOps / SRE** và **kỹ sư on-call** vận hành hệ microservice; mở rộng cho team **Platform** và **Data/Finance** cần điều tra bất thường trên hệ thống của họ.

## Cách agent giải quyết

- **Input:** một sự cố — log error, alert, hoặc mô tả thủ công. Nhận qua chat hoặc webhook từ Grafana, Prometheus, Sentry, PagerDuty, OpsGenie.
- **Xử lý:** engine sinh các giả thuyết đối lập, rồi qua từng bước adaptive tự chọn tool thu thập bằng chứng (logs, metrics, deploy history, source code, traces), loại trừ dần từng khả năng, và chỉ kết luận khi bằng chứng đủ vững.
- **Output:** verdict gắn bằng chứng cụ thể (root cause · độ tin cậy · chuỗi bằng chứng truy ngược được), đẩy về Telegram, Gmail, Teams hoặc Slack.

Agent triển khai trên **GreenNode AgentBase** (container single-instance, expose API qua endpoint runtime), nhận webhook và phục vụ dashboard trace realtime ngay trên nền tảng.

## Giá trị mang lại

Chạy hàng ngày, agent rút thời gian khoanh vùng từ hàng chục phút xuống vài phút, bỏ tra cứu thủ công lặp lại, và giảm sai sót do kết luận vội — mỗi verdict gắn bằng chứng thật và xem lại được từng bước suy luận.
