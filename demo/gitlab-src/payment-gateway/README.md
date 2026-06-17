# payment-gateway

Xử lý giao dịch thanh toán. Gọi `auth-service` để xác thực và `third-party-provider`
để thực hiện charge. Quản lý connection downstream qua `src/db/pool.py`.

> Repo demo cho hệ thống điều tra sự cố — source được agent đọc qua GitLab code MCP (READ-ONLY).
