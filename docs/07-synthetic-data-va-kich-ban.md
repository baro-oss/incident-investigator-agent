# 07 — Synthetic Data & Hai kịch bản

> **Data là sân khấu.** Engine giỏi tới đâu, data phẳng thì cuộc điều tra không có đường đi, demo nhạt. Đây là chỗ đáng đổ công, không phải làm cho xong.

## Nguyên tắc nền: thiết kế NGƯỢC từ cuộc điều tra mong muốn

Sai lầm phổ biến: đổ log ngẫu nhiên rồi mong agent tìm ra gì đó. Không được. Hình dung trước *cuộc điều tra lý tưởng* (agent đi bước nào, thấy gì mỗi bước, chốt ra sao), rồi *gieo data để đúng cuộc điều tra đó khả thi*. **Data là hệ quả của kịch bản, không phải nguyên nhân.**

## Tín hiệu trên nền nhiễu

- Chỉ có tín hiệu (toàn lỗi liên quan) → điều tra quá dễ, trông dàn dựng.
- Quá nhiều nhiễu → agent tầm trung lạc.
- **Cân bằng:** nền nhiễu thực tế (lỗi vặt bình thường, warning vô hại) đủ để agent phải *phân biệt* tín hiệu thật khỏi nhiễu — đó là lúc nó giống điều tra thật — nhưng tín hiệu chính đủ mạnh và nhất quán để lần ra. Tỷ lệ này tinh chỉnh bằng vòng đánh giá (`05`); đừng kỳ vọng đúng ngay lần đầu.

## Schema ba nguồn (mức ý niệm)

- **logs:** timestamp · service · level · message · error_type · **trace_id (có thể null — chỗ cài đứt)**.
- **metrics:** timestamp · service · tên metric · giá trị. **Phải có dữ liệu baseline** (khoảng "bình thường" trước sự cố) để tool so sánh được.
- **deploys:** timestamp · service · version · trạng thái.

Quyết định xuyên suốt: **mọi nguồn gắn vào trục thời gian chung** — tương quan thời gian là chất keo nối ba nguồn, và là bằng chứng dự phòng khi trace đứt.

## Kịch bản 1 — nguyên nhân đơn, một service (ca "sạch")

**Mục tiêu:** chứng minh điều tra cơ bản đúng. **Root cause:** deploy v2.3.1 lúc 14:03 → timeout ở payment-gateway.

**Đường điều tra lý tưởng:** breakdown thấy 87% timeout → metric thấy latency tăng vọt lúc 14:05 → deploy thấy v2.3.1 lúc 14:03 ngay trước → chốt **độ tin CAO** (có cả tương quan thời gian *lẫn* cơ chế).

**Data cần gieo:** timeout tăng đột biến sau 14:05 ở gateway · latency lệch baseline cùng lúc · một bản ghi deploy đúng mốc · nền nhiễu nhẹ. Agent nên giải gọn trong ít bước.

## Kịch bản 2 — lỗi dây chuyền, có trace đứt (ca "khó")

**Mục tiêu:** chứng minh 3 thứ cùng lúc — điều tra xuyên service, phân biệt gốc/lan, xử lý trace đứt. **Root cause:** third-party-provider sập → provider lỗi → lan ngược lên gateway. Gateway là nơi lỗi *lộ ra*, KHÔNG phải gốc. Cài **trace đứt** tại đoạn gateway→provider.

**Đường điều tra lý tưởng:** breakdown ở gateway thấy lỗi → nhưng metric/deploy gateway **bình thường** (manh mối: gốc không ở đây) → đi dependency, thấy gateway phụ thuộc provider → trace_request lần tới đó thì **mất dấu** → bắc cầu bằng tương quan thời gian: provider lỗi cùng khoảng → chốt provider là gốc **độ tin VỪA** (đoạn cuối dựa trên tương quan, không phải trace liền), nói rõ gateway chỉ là nơi lộ ra.

**Data cần gieo:** lỗi ở cả gateway lẫn provider cùng cửa sổ · **metric gateway KHÔNG lệch** (để loại trừ gateway là gốc) · trace_id liền tới một điểm rồi null sau đó · dependency catalog nối gateway→provider.

> **Tín hiệu âm tính** (cái đáng lẽ lệch mà lại không lệch — metric gateway bình thường) là dạng bằng chứng tinh tế. Agent dùng được nó là dấu hiệu điều tra thật. **Phải gieo có chủ đích** — dễ quên vì bản năng chỉ gieo cái bất thường.

## Hai kịch bản rẽ khác nhau ngay từ bước hai

Đây là chủ đích chống-hardcode: KB1 metric *lệch* → đi tới deploy. KB2 metric *không lệch* → loại trừ gateway, đi sang dependency. Đường điều tra khác hẳn → bằng chứng sống agent không hardcode khi giám khảo vặn.

## Khối lượng & cách sinh

- **Đừng làm thật cỡ GB.** Mục tiêu là demo điều tra, không phải test hiệu năng. Vài nghìn dòng/kịch bản, đủ có nhiễu + tín hiệu, là quá đủ. GB log chỉ làm chậm vòng dev của chính bạn.
- **Muốn chứng minh quy mô:** cho tool báo `total_count` lớn (giả lập, vd "14203 lỗi") trong khi bảng thật chỉ vài trăm dòng đại diện.
- **Script sinh tham số hóa** (cửa sổ thời gian, service lỗi, loại lỗi, mốc deploy, chỗ cài trace đứt). Lợi ích kép: tinh chỉnh kịch bản nhanh khi vòng đánh giá báo quá dễ/khó, và *sinh thêm biến thể ngay trước mặt giám khảo* nếu bị nghi hardcode. Cũng là chỗ kiểm soát tỷ lệ tín hiệu/nhiễu.

## Service catalog (file tĩnh)

3-5 service, mỗi cái: tên · mô tả ngắn · dependency trực tiếp · baseline cho metric chính. Đủ dựng chuỗi gateway → auth → provider cho KB2. **Đừng phình thành service mesh discovery** — chỉ cần đủ topology để điều tra dây chuyền có đường đi.
